from datetime import datetime, date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.database import get_db
from app.models.user import User, UserRole
from app.models.bus import Bus, Seat
from app.models.route import Stop, Route, RouteStop
from app.models.schedule import Trip, TripStatus
from app.models.booking import Booking, Ticket, BookingStatus
from app.schemas.booking import (
    AvailableTripItem, SeatAvailabilityItem, TripSeatLayoutResponse,
    BookingCreate, BookingResponse, TicketDetailsResponse
)
from app.services.auth_service import get_current_user
from app.services.booking_engine import (
    check_segment_overlap, calculate_segment_fare,
    is_seat_available_for_segment, book_seat_segment
)
from app.services.qr_service import generate_ticket_qr_base64

router = APIRouter(prefix="/passenger", tags=["Passenger Operations"])

@router.get("/stops")
def get_available_stops(db: Session = Depends(get_db)):
    """
    Returns list of stops and cities for search inputs.
    """
    stops = db.query(Stop).filter(Stop.is_active == True).order_by(Stop.city, Stop.name).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "city": s.city,
            "state": s.state,
            "latitude": s.latitude,
            "longitude": s.longitude,
            "is_terminal": s.is_terminal
        }
        for s in stops
    ]

@router.get("/search", response_model=List[AvailableTripItem])
def search_buses(
    origin: str = Query(..., description="Origin stop name or city"),
    destination: str = Query(..., description="Destination stop name or city"),
    travel_date: date = Query(..., description="Date of travel (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Searches available bus trips for the requested origin and destination.
    Computes segment-based availability and dynamic fare for the segment.
    """
    origin_clean = origin.strip().lower()
    dest_clean = destination.strip().lower()
    
    # 1. Find matching origin stops and destination stops
    origin_stops = db.query(Stop).filter(
        or_(Stop.name.ilike(f"%{origin_clean}%"), Stop.city.ilike(f"%{origin_clean}%")),
        Stop.is_active == True
    ).all()
    
    dest_stops = db.query(Stop).filter(
        or_(Stop.name.ilike(f"%{dest_clean}%"), Stop.city.ilike(f"%{dest_clean}%")),
        Stop.is_active == True
    ).all()
    
    if not origin_stops or not dest_stops:
        return []
        
    origin_stop_ids = {s.id for s in origin_stops}
    dest_stop_ids = {s.id for s in dest_stops}
    
    # 2. Find trips on travel_date
    trips = db.query(Trip).filter(
        Trip.trip_date == travel_date,
        Trip.status.in_([TripStatus.SCHEDULED, TripStatus.BOARDING, TripStatus.IN_TRANSIT])
    ).all()
    
    results: List[AvailableTripItem] = []
    
    for trip in trips:
        route_stops = db.query(RouteStop).filter(
            RouteStop.route_id == trip.route_id
        ).order_by(RouteStop.stop_sequence).all()
        
        # Check if route has an origin stop before a destination stop
        board_rs = None
        dest_rs = None
        for rs in route_stops:
            if not board_rs and rs.stop_id in origin_stop_ids:
                board_rs = rs
            elif board_rs and rs.stop_id in dest_stop_ids:
                dest_rs = rs
                break
                
        if not board_rs or not dest_rs:
            continue
            
        board_seq = board_rs.stop_sequence
        dest_seq = dest_rs.stop_sequence
        
        # Count available seats for this specific segment
        seats = db.query(Seat).filter(Seat.bus_id == trip.bus_id).all()
        total_seats = len(seats)
        available_count = 0
        
        for seat in seats:
            avail, _ = is_seat_available_for_segment(db, trip.id, seat.id, board_seq, dest_seq)
            if avail:
                available_count += 1
                
        fare = calculate_segment_fare(route_stops, board_seq, dest_seq, trip.base_fare)
        
        # Stop names
        b_stop = db.query(Stop).filter(Stop.id == board_rs.stop_id).first()
        d_stop = db.query(Stop).filter(Stop.id == dest_rs.stop_id).first()
        
        duration = max(dest_rs.duration_from_origin_minutes - board_rs.duration_from_origin_minutes, 30)
        
        results.append(AvailableTripItem(
            trip_id=trip.id,
            trip_code=trip.trip_code,
            bus_name=trip.bus.bus_name if trip.bus else "TRAKO Express",
            bus_type=trip.bus.bus_type if trip.bus else "Standard",
            registration_number=trip.bus.registration_number if trip.bus else "N/A",
            origin_stop_name=f"{b_stop.name} ({b_stop.city})" if b_stop else "Origin",
            destination_stop_name=f"{d_stop.name} ({d_stop.city})" if d_stop else "Destination",
            boarding_stop_id=board_rs.stop_id,
            destination_stop_id=dest_rs.stop_id,
            boarding_sequence=board_seq,
            destination_sequence=dest_seq,
            departure_time=trip.departure_datetime.strftime("%H:%M"),
            arrival_time=trip.expected_arrival_datetime.strftime("%H:%M"),
            duration_minutes=duration,
            available_seats=available_count,
            total_seats=total_seats,
            fare=fare,
            status=trip.status
        ))
        
    return results

@router.get("/trips/{trip_id}/seat-layout", response_model=TripSeatLayoutResponse)
def get_trip_seat_layout(
    trip_id: int,
    boarding_stop_id: int = Query(...),
    destination_stop_id: int = Query(...),
    db: Session = Depends(get_db)
):
    """
    Returns the bus seat layout for a trip, calculating whether each seat
    is available for the specified boarding and destination stops segment.
    """
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
        
    route_stops = db.query(RouteStop).filter(RouteStop.route_id == trip.route_id).order_by(RouteStop.stop_sequence).all()
    board_rs = next((rs for rs in route_stops if rs.stop_id == boarding_stop_id), None)
    dest_rs = next((rs for rs in route_stops if rs.stop_id == destination_stop_id), None)
    
    if not board_rs or not dest_rs:
        raise HTTPException(status_code=400, detail="Invalid stops for this trip route")
    if board_rs.stop_sequence >= dest_rs.stop_sequence:
        raise HTTPException(status_code=400, detail="Boarding stop must precede destination stop")
        
    board_seq = board_rs.stop_sequence
    dest_seq = dest_rs.stop_sequence
    
    fare = calculate_segment_fare(route_stops, board_seq, dest_seq, trip.base_fare)
    
    seats = db.query(Seat).filter(Seat.bus_id == trip.bus_id).order_by(Seat.row_num, Seat.col_num).all()
    
    seat_items: List[SeatAvailabilityItem] = []
    available_count = 0
    
    for seat in seats:
        avail, reason = is_seat_available_for_segment(db, trip.id, seat.id, board_seq, dest_seq)
        if avail:
            available_count += 1
            occupant_info = None
        else:
            occupant_info = reason
            
        seat_items.append(SeatAvailabilityItem(
            seat_id=seat.id,
            seat_number=seat.seat_number,
            deck=seat.deck,
            row_num=seat.row_num,
            col_num=seat.col_num,
            seat_type=seat.seat_type,
            is_available=avail,
            current_occupant_segment=occupant_info
        ))
        
    b_stop = db.query(Stop).filter(Stop.id == boarding_stop_id).first()
    d_stop = db.query(Stop).filter(Stop.id == destination_stop_id).first()
    
    return TripSeatLayoutResponse(
        trip_id=trip.id,
        trip_code=trip.trip_code,
        bus_id=trip.bus_id,
        bus_name=trip.bus.bus_name if trip.bus else "TRAKO Bus",
        registration_number=trip.bus.registration_number if trip.bus else "N/A",
        bus_type=trip.bus.bus_type if trip.bus else "Standard",
        layout_type=trip.bus.layout_type if trip.bus else "2+2",
        boarding_stop_id=boarding_stop_id,
        boarding_stop_name=f"{b_stop.name} ({b_stop.city})" if b_stop else "Boarding",
        destination_stop_id=destination_stop_id,
        destination_stop_name=f"{d_stop.name} ({d_stop.city})" if d_stop else "Destination",
        fare=fare,
        total_seats=len(seats),
        available_seats=available_count,
        seats=seat_items
    )

@router.post("/book", response_model=BookingResponse, status_code=status.HTTP_201_CREATED)
def create_booking(
    booking_in: BookingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Executes a segment-based seat booking with transaction isolation.
    """
    booking = book_seat_segment(
        db=db,
        trip_id=booking_in.trip_id,
        seat_id=booking_in.seat_id,
        boarding_stop_id=booking_in.boarding_stop_id,
        destination_stop_id=booking_in.destination_stop_id,
        passenger_id=current_user.id,
        passenger_name=booking_in.passenger_name.strip(),
        passenger_phone=booking_in.passenger_phone.strip(),
        passenger_email=booking_in.passenger_email or current_user.email,
        booking_source=booking_in.booking_source
    )
    
    ticket = booking.ticket
    qr_b64 = generate_ticket_qr_base64(ticket.ticket_token, booking.booking_reference)
    
    return BookingResponse(
        id=booking.id,
        booking_reference=booking.booking_reference,
        trip_id=booking.trip_id,
        trip_code=booking.trip.trip_code,
        bus_name=booking.trip.bus.bus_name,
        registration_number=booking.trip.bus.registration_number,
        seat_number=booking.seat.seat_number,
        boarding_stop_name=f"{booking.boarding_stop.name} ({booking.boarding_stop.city})",
        destination_stop_name=f"{booking.destination_stop.name} ({booking.destination_stop.city})",
        departure_datetime=booking.trip.departure_datetime,
        fare_amount=booking.fare_amount,
        status=booking.status,
        passenger_name=booking.passenger_name,
        passenger_phone=booking.passenger_phone,
        ticket_token=ticket.ticket_token,
        qr_data=qr_b64,
        booked_at=booking.booked_at
    )

@router.get("/bookings")
def get_user_bookings(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Returns all upcoming and completed bookings for the logged-in passenger.
    """
    bookings = db.query(Booking).filter(
        Booking.passenger_id == current_user.id
    ).order_by(Booking.booked_at.desc()).all()
    
    output = []
    for b in bookings:
        ticket = b.ticket
        output.append({
            "id": b.id,
            "booking_reference": b.booking_reference,
            "trip_id": b.trip_id,
            "trip_code": b.trip.trip_code if b.trip else "",
            "bus_name": b.trip.bus.bus_name if b.trip and b.trip.bus else "TRAKO",
            "registration_number": b.trip.bus.registration_number if b.trip and b.trip.bus else "",
            "route_name": b.trip.route.name if b.trip and b.trip.route else "",
            "seat_number": b.seat.seat_number if b.seat else "",
            "boarding_stop": f"{b.boarding_stop.name} ({b.boarding_stop.city})" if b.boarding_stop else "",
            "destination_stop": f"{b.destination_stop.name} ({b.destination_stop.city})" if b.destination_stop else "",
            "departure_datetime": b.trip.departure_datetime if b.trip else None,
            "fare_amount": b.fare_amount,
            "status": b.status,
            "ticket_token": ticket.ticket_token if ticket else "",
            "is_verified": ticket.is_verified if ticket else False,
            "booked_at": b.booked_at
        })
    return output

@router.get("/tickets/{booking_ref}", response_model=TicketDetailsResponse)
def get_ticket_details(
    booking_ref: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves complete digital ticket information with verification QR code.
    """
    booking = db.query(Booking).filter(Booking.booking_reference == booking_ref).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
        
    # Passengers can view only their tickets; Operators/Conductors can view any
    if current_user.role == UserRole.PASSENGER and booking.passenger_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized access to this ticket")
        
    ticket = booking.ticket
    qr_b64 = generate_ticket_qr_base64(ticket.ticket_token, booking.booking_reference)
    
    return TicketDetailsResponse(
        booking_reference=booking.booking_reference,
        ticket_token=ticket.ticket_token,
        qr_data=qr_b64,
        passenger_name=booking.passenger_name,
        passenger_phone=booking.passenger_phone,
        passenger_email=booking.passenger_email,
        bus_name=booking.trip.bus.bus_name,
        registration_number=booking.trip.bus.registration_number,
        bus_type=booking.trip.bus.bus_type,
        route_name=booking.trip.route.name,
        seat_number=booking.seat.seat_number,
        deck=booking.seat.deck,
        boarding_stop_name=f"{booking.boarding_stop.name} ({booking.boarding_stop.city})",
        destination_stop_name=f"{booking.destination_stop.name} ({booking.destination_stop.city})",
        departure_datetime=booking.trip.departure_datetime,
        expected_arrival=booking.trip.expected_arrival_datetime,
        fare_amount=booking.fare_amount,
        status=booking.status,
        is_verified=ticket.is_verified,
        verified_at=ticket.verified_at,
        booking_source=booking.booking_source,
        booked_at=booking.booked_at
    )

@router.post("/bookings/{booking_ref}/cancel")
def cancel_booking(
    booking_ref: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancels a booking and immediately frees the segment for other passengers.
    """
    booking = db.query(Booking).filter(Booking.booking_reference == booking_ref).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
        
    if current_user.role == UserRole.PASSENGER and booking.passenger_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized to cancel this booking")
        
    if booking.status == BookingStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Booking is already cancelled")
        
    if booking.status == BookingStatus.BOARDED:
        raise HTTPException(status_code=400, detail="Cannot cancel a ticket that has already been boarded")
        
    booking.status = BookingStatus.CANCELLED
    booking.cancelled_at = datetime.utcnow()
    booking.cancellation_reason = f"Cancelled by {current_user.full_name}"
    db.commit()
    return {"message": "Booking cancelled successfully. Seat segment has been freed."}
