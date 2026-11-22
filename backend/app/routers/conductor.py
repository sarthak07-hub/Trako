from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.models.schedule import Trip, TripStatus
from app.models.booking import Booking, Ticket, BookingStatus
from app.models.tracking import BoardingRecord
from app.schemas.booking import ConductorPassengerItem, TicketVerificationRequest, BoardingActionRequest
from app.services.auth_service import get_current_user, require_role

router = APIRouter(prefix="/conductor", tags=["Conductor Operations"])

require_conductor = require_role([UserRole.CONDUCTOR, UserRole.ADMIN])

@router.get("/assigned-trips")
def get_assigned_trips(current_user: User = Depends(require_conductor), db: Session = Depends(get_db)):
    """
    Returns all trips assigned to the logged-in conductor.
    """
    trips = db.query(Trip).filter(
        Trip.conductor_id == current_user.id
    ).order_by(Trip.departure_datetime.desc()).all()

    output = []
    for t in trips:
        total_bookings = db.query(Booking).filter(
            Booking.trip_id == t.id,
            Booking.status.in_([BookingStatus.CONFIRMED, BookingStatus.BOARDED])
        ).count()
        boarded_count = db.query(Booking).filter(
            Booking.trip_id == t.id,
            Booking.status == BookingStatus.BOARDED
        ).count()

        output.append({
            "id": t.id,
            "trip_code": t.trip_code,
            "trip_date": str(t.trip_date),
            "departure_datetime": t.departure_datetime,
            "status": t.status,
            "bus_name": t.bus.bus_name if t.bus else "",
            "registration_number": t.bus.registration_number if t.bus else "",
            "route_name": t.route.name if t.route else "",
            "boarding_deadline_minutes": t.boarding_deadline_minutes,
            "total_bookings": total_bookings,
            "boarded_count": boarded_count
        })
    return output

@router.get("/trips/{trip_id}/manifest", response_model=List[ConductorPassengerItem])
def get_trip_manifest(
    trip_id: int,
    current_user: User = Depends(require_conductor),
    db: Session = Depends(get_db)
):
    """
    Returns passenger manifest for a trip, calculating potential no-shows based
    on departure time + trip boarding deadline.
    """
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    bookings = db.query(Booking).filter(
        Booking.trip_id == trip_id,
        Booking.status != BookingStatus.CANCELLED
    ).order_by(Booking.boarding_sequence, Booking.seat_id).all()

    now = datetime.utcnow()
    deadline_threshold = trip.departure_datetime + timedelta(minutes=trip.boarding_deadline_minutes)

    manifest = []
    for b in bookings:
        ticket = b.ticket
        is_potential_no_show = False
        if b.status == BookingStatus.CONFIRMED and now > deadline_threshold:
            is_potential_no_show = True

        manifest.append(ConductorPassengerItem(
            booking_id=b.id,
            ticket_id=ticket.id if ticket else 0,
            booking_reference=b.booking_reference,
            ticket_token=ticket.ticket_token if ticket else "",
            passenger_name=b.passenger_name,
            passenger_phone=b.passenger_phone,
            seat_number=b.seat.seat_number if b.seat else "",
            boarding_stop_id=b.boarding_stop_id,
            boarding_stop_name=f"{b.boarding_stop.name} ({b.boarding_stop.city})" if b.boarding_stop else "",
            destination_stop_id=b.destination_stop_id,
            destination_stop_name=f"{b.destination_stop.name} ({b.destination_stop.city})" if b.destination_stop else "",
            boarding_sequence=b.boarding_sequence,
            destination_sequence=b.destination_sequence,
            status=b.status,
            is_potential_no_show=is_potential_no_show,
            verified_at=ticket.verified_at if ticket else None
        ))

    return manifest

@router.post("/verify-ticket")
def verify_scanned_ticket(
    req: TicketVerificationRequest,
    current_user: User = Depends(require_conductor),
    db: Session = Depends(get_db)
):
    """
    Verifies a digital ticket QR payload (or manual code).
    Supports token format 'TRAKO:TICKET:{token}:{ref}' or pure token or booking reference.
    """
    raw = req.ticket_token_or_ref.strip()
    # Extract token if formatted like TRAKO:TICKET:TK-XXX:REF
    parts = raw.split(":")
    token_candidate = parts[2] if len(parts) >= 3 and parts[0] == "TRAKO" else raw

    ticket = db.query(Ticket).join(Booking).filter(
        (Ticket.ticket_token == token_candidate) | (Booking.booking_reference == token_candidate)
    ).first()

    if not ticket:
        raise HTTPException(
            status_code=404,
            detail="Ticket not recognized. Invalid QR code or booking reference."
        )

    booking = ticket.booking
    trip = booking.trip

    # If trip_id is specified in verification request, verify it matches
    if req.trip_id and trip.id != req.trip_id:
        return {
            "valid": False,
            "status_code": "WRONG_TRIP",
            "message": f"This ticket belongs to another trip ({trip.trip_code}), not the selected trip.",
            "booking_reference": booking.booking_reference,
            "passenger_name": booking.passenger_name,
            "bus_name": trip.bus.bus_name if trip.bus else "",
            "route_name": trip.route.name if trip.route else ""
        }

    if booking.status == BookingStatus.CANCELLED:
        return {
            "valid": False,
            "status_code": "CANCELLED",
            "message": "This booking has been CANCELLED and is no longer valid.",
            "booking_reference": booking.booking_reference,
            "passenger_name": booking.passenger_name
        }

    if booking.status == BookingStatus.NO_SHOW:
        return {
            "valid": False,
            "status_code": "NO_SHOW",
            "message": "This booking was marked as NO-SHOW and the seat was released.",
            "booking_reference": booking.booking_reference,
            "passenger_name": booking.passenger_name
        }

    already_boarded = (booking.status == BookingStatus.BOARDED)

    return {
        "valid": True,
        "status_code": "ALREADY_BOARDED" if already_boarded else "VALID_FOR_BOARDING",
        "message": "Passenger already boarded" if already_boarded else "Ticket is VALID. Ready for boarding confirmation.",
        "booking_id": booking.id,
        "ticket_id": ticket.id,
        "booking_reference": booking.booking_reference,
        "ticket_token": ticket.ticket_token,
        "passenger_name": booking.passenger_name,
        "passenger_phone": booking.passenger_phone,
        "seat_number": booking.seat.seat_number if booking.seat else "",
        "boarding_stop": f"{booking.boarding_stop.name} ({booking.boarding_stop.city})" if booking.boarding_stop else "",
        "destination_stop": f"{booking.destination_stop.name} ({booking.destination_stop.city})" if booking.destination_stop else "",
        "fare_amount": booking.fare_amount,
        "status": booking.status,
        "departure_datetime": trip.departure_datetime,
        "is_verified": ticket.is_verified,
        "verified_at": ticket.verified_at
    }

@router.post("/confirm-boarding")
def confirm_boarding(
    req: BoardingActionRequest,
    current_user: User = Depends(require_conductor),
    db: Session = Depends(get_db)
):
    """
    Conductor confirms passenger boarding after ticket verification.
    """
    booking = db.query(Booking).filter(Booking.id == req.booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.status == BookingStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Cannot board a cancelled ticket")

    booking.status = BookingStatus.BOARDED
    ticket = booking.ticket
    if ticket:
        ticket.is_verified = True
        ticket.verified_at = datetime.utcnow()
        ticket.verified_by_conductor_id = current_user.id
        ticket.verification_notes = req.remarks or f"Boarded confirmed by {current_user.full_name}"

    record = BoardingRecord(
        ticket_id=ticket.id if ticket else 0,
        trip_id=booking.trip_id,
        conductor_id=current_user.id,
        stop_id=req.stop_id or booking.boarding_stop_id,
        action="BOARDED",
        timestamp=datetime.utcnow(),
        remarks=req.remarks
    )
    db.add(record)
    db.commit()

    return {
        "message": f"Boarding confirmed for {booking.passenger_name} (Seat {booking.seat.seat_number})",
        "booking_reference": booking.booking_reference,
        "status": booking.status
    }

@router.post("/declare-no-show")
def declare_no_show(
    req: BoardingActionRequest,
    current_user: User = Depends(require_conductor),
    db: Session = Depends(get_db)
):
    """
    Conductor explicitly confirms passenger did not show up after boarding deadline.
    Releases the seat segment for future bookings and records the decision.
    """
    booking = db.query(Booking).filter(Booking.id == req.booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.status == BookingStatus.BOARDED:
        raise HTTPException(status_code=400, detail="Cannot mark an already boarded passenger as no-show")

    booking.status = BookingStatus.NO_SHOW
    booking.cancellation_reason = f"Marked NO_SHOW by conductor {current_user.full_name}"
    
    ticket = booking.ticket
    record = BoardingRecord(
        ticket_id=ticket.id if ticket else 0,
        trip_id=booking.trip_id,
        conductor_id=current_user.id,
        stop_id=req.stop_id or booking.boarding_stop_id,
        action="NO_SHOW_SEAT_RELEASED",
        timestamp=datetime.utcnow(),
        remarks=req.remarks or "Passenger failed to board before departure deadline. Seat segment released."
    )
    db.add(record)
    db.commit()

    return {
        "message": f"Passenger {booking.passenger_name} marked as NO-SHOW. Seat {booking.seat.seat_number} is now released.",
        "booking_reference": booking.booking_reference,
        "status": booking.status
    }
