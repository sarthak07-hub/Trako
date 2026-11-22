from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.bus import Bus, Seat
from app.models.schedule import Trip, TripStatus
from app.models.route import RouteStop, Stop
from app.models.booking import Ticket
from app.services.qr_service import generate_seat_qr_base64, generate_ticket_qr_base64, generate_seat_qr_url
from app.services.booking_engine import is_seat_available_for_segment, calculate_segment_fare

router = APIRouter(prefix="/qr", tags=["QR Code System"])

@router.get("/bus-seat-info")
def get_bus_seat_info_for_qr(
    bus_id: int = Query(...),
    seat_number: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Public entry point when passenger scans a physical bus seat QR code.
    Identifies the bus and seat, and returns available upcoming trips with their stops.
    """
    bus = db.query(Bus).filter(Bus.id == bus_id, Bus.is_active == True).first()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found or inactive")

    seat = db.query(Seat).filter(Seat.bus_id == bus_id, Seat.seat_number == seat_number.strip().upper()).first()
    if not seat:
        raise HTTPException(status_code=404, detail=f"Seat {seat_number} not found on bus {bus.registration_number}")

    # Fetch scheduled or active trips for this bus today or upcoming
    today = date.today()
    trips = db.query(Trip).filter(
        Trip.bus_id == bus.id,
        Trip.trip_date >= today,
        Trip.status.in_([TripStatus.SCHEDULED, TripStatus.BOARDING, TripStatus.IN_TRANSIT])
    ).order_by(Trip.departure_datetime).all()

    trip_list = []
    for t in trips:
        route_stops = db.query(RouteStop).filter(
            RouteStop.route_id == t.route_id
        ).order_by(RouteStop.stop_sequence).all()

        stops_data = [
            {
                "stop_id": rs.stop_id,
                "sequence": rs.stop_sequence,
                "name": rs.stop.name,
                "city": rs.stop.city,
                "fare_from_origin": rs.fare_from_origin
            }
            for rs in route_stops
        ]

        trip_list.append({
            "trip_id": t.id,
            "trip_code": t.trip_code,
            "trip_date": str(t.trip_date),
            "departure_datetime": t.departure_datetime,
            "route_name": t.route.name if t.route else "",
            "base_fare": t.base_fare,
            "status": t.status,
            "stops": stops_data
        })

    return {
        "bus": {
            "id": bus.id,
            "bus_name": bus.bus_name,
            "registration_number": bus.registration_number,
            "bus_type": bus.bus_type,
            "layout_type": bus.layout_type
        },
        "seat": {
            "id": seat.id,
            "seat_number": seat.seat_number,
            "deck": seat.deck,
            "seat_type": seat.seat_type
        },
        "available_trips": trip_list
    }

@router.get("/generate-seat-qr")
def generate_seat_qr(
    bus_id: int = Query(...),
    seat_number: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Returns base64 image and target booking URL for a physical seat QR code.
    """
    seat = db.query(Seat).filter(Seat.bus_id == bus_id, Seat.seat_number == seat_number.strip().upper()).first()
    if not seat:
        raise HTTPException(status_code=404, detail="Seat not found")

    url = generate_seat_qr_url(bus_id, seat.seat_number)
    qr_b64 = generate_seat_qr_base64(bus_id, seat.seat_number)
    return {
        "bus_id": bus_id,
        "seat_number": seat.seat_number,
        "target_url": url,
        "qr_image_base64": qr_b64
    }

@router.get("/generate-ticket-qr")
def generate_ticket_qr(
    ticket_token: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Generates a secure digital ticket QR code image given a valid ticket token.
    """
    ticket = db.query(Ticket).filter(Ticket.ticket_token == ticket_token).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    booking_ref = ticket.booking.booking_reference if ticket.booking else "REF"
    qr_b64 = generate_ticket_qr_base64(ticket.ticket_token, booking_ref)
    return {
        "ticket_token": ticket.ticket_token,
        "booking_reference": booking_ref,
        "qr_image_base64": qr_b64
    }
