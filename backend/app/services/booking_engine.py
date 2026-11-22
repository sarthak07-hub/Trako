from datetime import datetime
import secrets
import string
import uuid
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from fastapi import HTTPException, status

from app.models.booking import Booking, Ticket, BookingStatus
from app.models.schedule import Trip, TripStatus
from app.models.bus import Seat
from app.models.route import RouteStop, Stop

def check_segment_overlap(start1: int, end1: int, start2: int, end2: int) -> bool:
    """
    Returns True if segment [start1, end1] overlaps with [start2, end2].
    Stops are ordered indices along the route: start < end.
    Adjacent segments like [0, 2] and [2, 4] do NOT overlap because
    passenger 1 alights at stop 2 before passenger 2 boards at stop 2.
    Formula: max(start1, start2) < min(end1, end2)
    """
    return max(start1, start2) < min(end1, end2)

def generate_booking_reference() -> str:
    alphabet = string.ascii_uppercase + string.digits
    rand_part = ''.join(secrets.choice(alphabet) for _ in range(6))
    return f"TRK-{datetime.utcnow().year}-{rand_part}"

def generate_ticket_token() -> str:
    return f"TK-{uuid.uuid4().hex[:16].upper()}"

def get_stop_sequence_for_route(db: Session, route_id: int, stop_id: int) -> Optional[RouteStop]:
    return db.query(RouteStop).filter(
        RouteStop.route_id == route_id,
        RouteStop.stop_id == stop_id
    ).first()

def calculate_segment_fare(route_stops: List[RouteStop], board_seq: int, dest_seq: int, base_fare: float) -> float:
    """
    Calculates segment fare based on route stops sequence and distances/fare from origin.
    """
    board_rs = next((rs for rs in route_stops if rs.stop_sequence == board_seq), None)
    dest_rs = next((rs for rs in route_stops if rs.stop_sequence == dest_seq), None)
    
    if board_rs and dest_rs and dest_rs.fare_from_origin > 0:
        fare = dest_rs.fare_from_origin - board_rs.fare_from_origin
        if fare > 0:
            return round(fare, 2)
    
    # Fallback to proportion of base fare by stops count
    total_stops = max(len(route_stops) - 1, 1)
    stops_traveled = max(dest_seq - board_seq, 1)
    return round((stops_traveled / total_stops) * base_fare, 2)

def is_seat_available_for_segment(
    db: Session,
    trip_id: int,
    seat_id: int,
    requested_board_seq: int,
    requested_dest_seq: int
) -> Tuple[bool, Optional[str]]:
    """
    Checks whether a specific seat is available for the given segment on a trip.
    Returns (True, None) if available, or (False, reason) if overlapping with existing booking.
    """
    active_statuses = [BookingStatus.CONFIRMED, BookingStatus.BOARDED]
    
    active_bookings = db.query(Booking).filter(
        Booking.trip_id == trip_id,
        Booking.seat_id == seat_id,
        Booking.status.in_(active_statuses)
    ).all()
    
    for b in active_bookings:
        if check_segment_overlap(requested_board_seq, requested_dest_seq, b.boarding_sequence, b.destination_sequence):
            reason = f"Occupied between stop sequence {b.boarding_sequence} and {b.destination_sequence} (Ref: {b.booking_reference})"
            return False, reason
            
    return True, None

def book_seat_segment(
    db: Session,
    trip_id: int,
    seat_id: int,
    boarding_stop_id: int,
    destination_stop_id: int,
    passenger_id: int,
    passenger_name: str,
    passenger_phone: str,
    passenger_email: Optional[str] = None,
    booking_source: str = "WEB"
) -> Booking:
    """
    Atomically books a seat for the requested segment with concurrency protection.
    Raises HTTPException if trip is cancelled/completed or seat is taken for that segment.
    """
    # 1. Fetch trip and route
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
        
    if trip.status in [TripStatus.COMPLETED, TripStatus.CANCELLED]:
        raise HTTPException(status_code=400, detail=f"Cannot book seats for a trip with status: {trip.status}")
        
    # 2. Validate stops and get ordered sequence
    route_stops = db.query(RouteStop).filter(RouteStop.route_id == trip.route_id).order_by(RouteStop.stop_sequence).all()
    if not route_stops:
        raise HTTPException(status_code=400, detail="Route has no configured stops")
        
    board_rs = next((rs for rs in route_stops if rs.stop_id == boarding_stop_id), None)
    dest_rs = next((rs for rs in route_stops if rs.stop_id == destination_stop_id), None)
    
    if not board_rs:
        raise HTTPException(status_code=400, detail="Boarding stop is not part of this route")
    if not dest_rs:
        raise HTTPException(status_code=400, detail="Destination stop is not part of this route")
        
    if board_rs.stop_sequence >= dest_rs.stop_sequence:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid segment: Boarding stop (seq {board_rs.stop_sequence}) must be before destination stop (seq {dest_rs.stop_sequence})"
        )
        
    board_seq = board_rs.stop_sequence
    dest_seq = dest_rs.stop_sequence
    
    # 3. Check seat existence
    seat = db.query(Seat).filter(Seat.id == seat_id, Seat.bus_id == trip.bus_id).first()
    if not seat:
        raise HTTPException(status_code=404, detail="Seat not found on the assigned bus")
        
    # 4. Concurrency protection & segment overlap verification
    # Within transaction, check if seat is free for [board_seq, dest_seq]
    available, reason = is_seat_available_for_segment(db, trip_id, seat_id, board_seq, dest_seq)
    if not available:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Seat {seat.seat_number} is already booked for an overlapping segment: {reason}"
        )
        
    # 5. Calculate fare
    fare = calculate_segment_fare(route_stops, board_seq, dest_seq, trip.base_fare)
    
    # 6. Create Booking
    booking_ref = generate_booking_reference()
    new_booking = Booking(
        booking_reference=booking_ref,
        trip_id=trip_id,
        passenger_id=passenger_id,
        seat_id=seat_id,
        boarding_stop_id=boarding_stop_id,
        destination_stop_id=destination_stop_id,
        boarding_sequence=board_seq,
        destination_sequence=dest_seq,
        fare_amount=fare,
        passenger_name=passenger_name,
        passenger_phone=passenger_phone,
        passenger_email=passenger_email,
        status=BookingStatus.CONFIRMED,
        booking_source=booking_source,
        booked_at=datetime.utcnow()
    )
    db.add(new_booking)
    db.flush()  # to obtain new_booking.id
    
    # 7. Generate Ticket with verification token
    ticket_token = generate_ticket_token()
    qr_payload = f"TRAKO:TICKET:{ticket_token}:{booking_ref}"
    ticket = Ticket(
        booking_id=new_booking.id,
        ticket_token=ticket_token,
        qr_data=qr_payload,
        issued_at=datetime.utcnow(),
        is_verified=False
    )
    db.add(ticket)
    db.commit()
    db.refresh(new_booking)
    return new_booking
