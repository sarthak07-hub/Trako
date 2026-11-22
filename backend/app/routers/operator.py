from datetime import datetime, date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.user import User, UserRole
from app.models.bus import Bus, Seat
from app.models.route import Stop, Route, RouteStop
from app.models.schedule import Schedule, Trip, TripStatus
from app.models.booking import Booking, Ticket, BookingStatus
from app.models.tracking import GPSLocation, GPSStatus
from app.schemas.bus import BusCreate, BusUpdate, BusResponse
from app.schemas.route import RouteCreate, RouteResponse, StopResponse
from app.schemas.trip import ScheduleCreate, ScheduleResponse, TripCreate, TripUpdate, TripResponse
from app.services.auth_service import get_current_user, require_role
from app.services.qr_service import generate_seat_qr_base64, generate_seat_qr_url
from app.services.tracking_service import evaluate_gps_status

router = APIRouter(prefix="/operator", tags=["Operator Operations"])

# Guard all operator endpoints
require_operator = require_role([UserRole.OPERATOR, UserRole.ADMIN])

@router.get("/stats")
def get_operator_stats(
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db)
):
    """
    Returns high-level statistics for the operator dashboard overview.
    """
    total_buses = db.query(Bus).filter(Bus.operator_id == current_user.id, Bus.is_active == True).count()
    total_routes = db.query(Route).filter(Route.operator_id == current_user.id, Route.is_active == True).count()
    
    today = date.today()
    today_trips = db.query(Trip).filter(
        Trip.operator_id == current_user.id,
        Trip.trip_date == today
    ).count()
    
    active_in_transit = db.query(Trip).filter(
        Trip.operator_id == current_user.id,
        Trip.status == TripStatus.IN_TRANSIT
    ).count()
    
    # Total bookings and revenue
    bookings_query = db.query(Booking).join(Trip).filter(
        Trip.operator_id == current_user.id,
        Booking.status.in_([BookingStatus.CONFIRMED, BookingStatus.BOARDED])
    )
    total_bookings = bookings_query.count()
    total_revenue = bookings_query.with_entities(func.sum(Booking.fare_amount)).scalar() or 0.0

    return {
        "total_buses": total_buses,
        "total_routes": total_routes,
        "today_trips": today_trips,
        "active_in_transit": active_in_transit,
        "total_bookings": total_bookings,
        "total_revenue": round(float(total_revenue), 2)
    }

# ----------------- BUS MANAGEMENT -----------------

def create_default_seats_for_bus(db: Session, bus: Bus):
    """
    Automatically populates realistic seats based on layout_type and capacity.
    For 2+2 layout: columns A, B (left aisle), C, D (right aisle).
    For 2+1 layout: columns A, B (left aisle), C (right aisle).
    """
    letters = ["A", "B", "C", "D"] if bus.layout_type == "2+2" else ["A", "B", "C"]
    cols_per_row = len(letters)
    num_rows = (bus.seating_capacity + cols_per_row - 1) // cols_per_row

    seat_count = 0
    for r in range(1, num_rows + 1):
        for c_idx, letter in enumerate(letters):
            if seat_count >= bus.seating_capacity:
                break
            seat_num = f"{r}{letter}"
            stype = "WINDOW" if c_idx in [0, len(letters) - 1] else "AISLE"
            
            seat = Seat(
                bus_id=bus.id,
                seat_number=seat_num,
                deck="LOWER",
                row_num=r,
                col_num=c_idx + 1,
                seat_type=stype,
                qr_code_identifier=f"BUS-{bus.id}-SEAT-{seat_num}"
            )
            db.add(seat)
            seat_count += 1
    db.commit()

@router.get("/buses")
def list_buses(current_user: User = Depends(require_operator), db: Session = Depends(get_db)):
    buses = db.query(Bus).filter(Bus.operator_id == current_user.id).order_by(Bus.id.desc()).all()
    results = []
    for b in buses:
        results.append({
            "id": b.id,
            "registration_number": b.registration_number,
            "bus_name": b.bus_name,
            "bus_type": b.bus_type,
            "seating_capacity": b.seating_capacity,
            "layout_type": b.layout_type,
            "is_active": b.is_active,
            "seat_count": len(b.seats),
            "created_at": b.created_at
        })
    return results

@router.post("/buses", status_code=status.HTTP_201_CREATED)
def add_bus(bus_in: BusCreate, current_user: User = Depends(require_operator), db: Session = Depends(get_db)):
    reg_clean = bus_in.registration_number.strip().upper()
    existing = db.query(Bus).filter(Bus.registration_number == reg_clean).first()
    if existing:
        raise HTTPException(status_code=400, detail="A bus with this registration number already exists")

    bus = Bus(
        operator_id=current_user.id,
        registration_number=reg_clean,
        bus_name=bus_in.bus_name.strip(),
        bus_type=bus_in.bus_type,
        seating_capacity=bus_in.seating_capacity,
        layout_type=bus_in.layout_type,
        is_active=True
    )
    db.add(bus)
    db.commit()
    db.refresh(bus)

    # Automatically generate seats
    create_default_seats_for_bus(db, bus)
    db.refresh(bus)
    return {"message": "Bus added successfully with seats initialized", "bus_id": bus.id}

@router.get("/buses/{bus_id}/seats")
def get_bus_seats_with_qr(
    bus_id: int,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db)
):
    bus = db.query(Bus).filter(Bus.id == bus_id, Bus.operator_id == current_user.id).first()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found")

    seats = db.query(Seat).filter(Seat.bus_id == bus_id).order_by(Seat.row_num, Seat.col_num).all()
    output = []
    for s in seats:
        qr_url = generate_seat_qr_url(bus.id, s.seat_number)
        qr_b64 = generate_seat_qr_base64(bus.id, s.seat_number)
        output.append({
            "seat_id": s.id,
            "seat_number": s.seat_number,
            "deck": s.deck,
            "row_num": s.row_num,
            "col_num": s.col_num,
            "seat_type": s.seat_type,
            "booking_url": qr_url,
            "qr_code_image": qr_b64
        })
    return {"bus_id": bus.id, "bus_name": bus.bus_name, "registration_number": bus.registration_number, "seats": output}

@router.delete("/buses/{bus_id}")
def delete_bus(bus_id: int, current_user: User = Depends(require_operator), db: Session = Depends(get_db)):
    bus = db.query(Bus).filter(Bus.id == bus_id, Bus.operator_id == current_user.id).first()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found")
    bus.is_active = False
    db.commit()
    return {"message": "Bus deactivated successfully"}

# ----------------- ROUTE MANAGEMENT -----------------

@router.get("/routes")
def list_routes(current_user: User = Depends(require_operator), db: Session = Depends(get_db)):
    routes = db.query(Route).filter(Route.operator_id == current_user.id).order_by(Route.id.desc()).all()
    output = []
    for r in routes:
        stops = []
        for rs in r.route_stops:
            stops.append({
                "sequence": rs.stop_sequence,
                "stop_id": rs.stop_id,
                "name": rs.stop.name,
                "city": rs.stop.city,
                "distance_km": rs.distance_from_origin_km,
                "duration_min": rs.duration_from_origin_minutes,
                "fare": rs.fare_from_origin
            })
        output.append({
            "id": r.id,
            "route_code": r.route_code,
            "name": r.name,
            "origin": f"{r.origin_stop.name} ({r.origin_stop.city})" if r.origin_stop else "",
            "destination": f"{r.destination_stop.name} ({r.destination_stop.city})" if r.destination_stop else "",
            "total_distance_km": r.total_distance_km,
            "estimated_duration_minutes": r.estimated_duration_minutes,
            "is_active": r.is_active,
            "stops_count": len(r.route_stops),
            "stops": stops
        })
    return output

@router.post("/routes", status_code=status.HTTP_201_CREATED)
def create_route(route_in: RouteCreate, current_user: User = Depends(require_operator), db: Session = Depends(get_db)):
    existing = db.query(Route).filter(Route.route_code == route_in.route_code.strip().upper()).first()
    if existing:
        raise HTTPException(status_code=400, detail="A route with this code already exists")

    new_route = Route(
        operator_id=current_user.id,
        route_code=route_in.route_code.strip().upper(),
        name=route_in.name.strip(),
        origin_stop_id=route_in.origin_stop_id,
        destination_stop_id=route_in.destination_stop_id,
        total_distance_km=route_in.total_distance_km,
        estimated_duration_minutes=route_in.estimated_duration_minutes,
        is_active=True
    )
    db.add(new_route)
    db.flush()

    # Add stops in sequence
    for st in route_in.stops:
        rs = RouteStop(
            route_id=new_route.id,
            stop_id=st.stop_id,
            stop_sequence=st.stop_sequence,
            distance_from_origin_km=st.distance_from_origin_km,
            duration_from_origin_minutes=st.duration_from_origin_minutes,
            halt_duration_minutes=st.halt_duration_minutes,
            fare_from_origin=st.fare_from_origin
        )
        db.add(rs)

    db.commit()
    return {"message": "Route created successfully", "route_id": new_route.id}

# ----------------- SCHEDULES & TRIPS -----------------

@router.get("/schedules")
def list_schedules(current_user: User = Depends(require_operator), db: Session = Depends(get_db)):
    schedules = db.query(Schedule).filter(Schedule.operator_id == current_user.id).all()
    output = []
    for s in schedules:
        output.append({
            "id": s.id,
            "route_id": s.route_id,
            "route_name": s.route.name if s.route else "",
            "departure_time": s.departure_time,
            "days_of_week": s.days_of_week,
            "default_bus_id": s.default_bus_id,
            "default_bus_name": s.default_bus.bus_name if s.default_bus else None,
            "is_active": s.is_active
        })
    return output

@router.post("/schedules", status_code=status.HTTP_201_CREATED)
def create_schedule(sched_in: ScheduleCreate, current_user: User = Depends(require_operator), db: Session = Depends(get_db)):
    schedule = Schedule(
        operator_id=current_user.id,
        route_id=sched_in.route_id,
        departure_time=sched_in.departure_time,
        days_of_week=sched_in.days_of_week,
        default_bus_id=sched_in.default_bus_id,
        is_active=True
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return {"message": "Schedule created", "schedule_id": schedule.id}

@router.get("/trips")
def list_trips(
    trip_date: Optional[date] = None,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db)
):
    query = db.query(Trip).filter(Trip.operator_id == current_user.id)
    if trip_date:
        query = query.filter(Trip.trip_date == trip_date)
    trips = query.order_by(Trip.departure_datetime.desc()).all()

    output = []
    for t in trips:
        seats_booked = db.query(Booking).filter(
            Booking.trip_id == t.id,
            Booking.status.in_([BookingStatus.CONFIRMED, BookingStatus.BOARDED])
        ).count()
        total_seats = len(t.bus.seats) if t.bus else 0

        output.append({
            "id": t.id,
            "trip_code": t.trip_code,
            "trip_date": str(t.trip_date),
            "departure_datetime": t.departure_datetime,
            "expected_arrival_datetime": t.expected_arrival_datetime,
            "route_id": t.route_id,
            "route_name": t.route.name if t.route else "",
            "bus_id": t.bus_id,
            "bus_name": t.bus.bus_name if t.bus else "",
            "registration_number": t.bus.registration_number if t.bus else "",
            "driver_id": t.driver_id,
            "driver_name": t.driver.full_name if t.driver else "Unassigned",
            "conductor_id": t.conductor_id,
            "conductor_name": t.conductor.full_name if t.conductor else "Unassigned",
            "base_fare": t.base_fare,
            "status": t.status,
            "booked_seats_count": seats_booked,
            "total_seats_count": total_seats
        })
    return output

@router.post("/trips", status_code=status.HTTP_201_CREATED)
def create_trip(trip_in: TripCreate, current_user: User = Depends(require_operator), db: Session = Depends(get_db)):
    # Auto-generate unique trip code
    code = f"TRIP-{trip_in.trip_date.strftime('%Y%m%d')}-{trip_in.route_id}-{trip_in.bus_id}"
    existing = db.query(Trip).filter(Trip.trip_code == code).first()
    if existing:
        code = f"{code}-{int(datetime.utcnow().timestamp()) % 1000}"

    trip = Trip(
        trip_code=code,
        operator_id=current_user.id,
        route_id=trip_in.route_id,
        bus_id=trip_in.bus_id,
        driver_id=trip_in.driver_id,
        conductor_id=trip_in.conductor_id,
        trip_date=trip_in.trip_date,
        departure_datetime=trip_in.departure_datetime,
        expected_arrival_datetime=trip_in.expected_arrival_datetime,
        base_fare=trip_in.base_fare,
        status=TripStatus.SCHEDULED,
        boarding_deadline_minutes=trip_in.boarding_deadline_minutes
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return {"message": "Trip created successfully", "trip_id": trip.id, "trip_code": trip.trip_code}

@router.put("/trips/{trip_id}")
def update_trip(trip_id: int, update_in: TripUpdate, current_user: User = Depends(require_operator), db: Session = Depends(get_db)):
    trip = db.query(Trip).filter(Trip.id == trip_id, Trip.operator_id == current_user.id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    if update_in.driver_id is not None:
        trip.driver_id = update_in.driver_id
    if update_in.conductor_id is not None:
        trip.conductor_id = update_in.conductor_id
    if update_in.status is not None:
        trip.status = update_in.status
    if update_in.actual_arrival_datetime is not None:
        trip.actual_arrival_datetime = update_in.actual_arrival_datetime

    trip.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Trip updated successfully"}

# ----------------- OPERATOR BOOKING MANAGEMENT -----------------

@router.get("/bookings")
def list_operator_bookings(
    trip_id: Optional[int] = None,
    current_user: User = Depends(require_operator),
    db: Session = Depends(get_db)
):
    query = db.query(Booking).join(Trip).filter(Trip.operator_id == current_user.id)
    if trip_id:
        query = query.filter(Booking.trip_id == trip_id)
        
    bookings = query.order_by(Booking.booked_at.desc()).limit(100).all()
    output = []
    for b in bookings:
        output.append({
            "id": b.id,
            "booking_reference": b.booking_reference,
            "trip_code": b.trip.trip_code if b.trip else "",
            "passenger_name": b.passenger_name,
            "passenger_phone": b.passenger_phone,
            "bus_name": b.trip.bus.bus_name if b.trip and b.trip.bus else "",
            "seat_number": b.seat.seat_number if b.seat else "",
            "boarding_stop": f"{b.boarding_stop.name} ({b.boarding_stop.city})" if b.boarding_stop else "",
            "destination_stop": f"{b.destination_stop.name} ({b.destination_stop.city})" if b.destination_stop else "",
            "fare_amount": b.fare_amount,
            "status": b.status,
            "booking_source": b.booking_source,
            "booked_at": b.booked_at
        })
    return output

# ----------------- FLEET MANAGEMENT RADAR -----------------

@router.get("/fleet-radar")
def get_fleet_radar(current_user: User = Depends(require_operator), db: Session = Depends(get_db)):
    """
    Returns live coordinates and status for all active buses owned by this operator.
    """
    active_trips = db.query(Trip).filter(
        Trip.operator_id == current_user.id,
        Trip.status.in_([TripStatus.IN_TRANSIT, TripStatus.BOARDING, TripStatus.SCHEDULED])
    ).all()

    fleet = []
    for t in active_trips:
        latest_gps = db.query(GPSLocation).filter(
            GPSLocation.trip_id == t.id
        ).order_by(GPSLocation.recorded_at.desc()).first()

        gps_status, seconds_ago = evaluate_gps_status(latest_gps)

        fleet.append({
            "trip_id": t.id,
            "trip_code": t.trip_code,
            "trip_status": t.status,
            "bus_id": t.bus_id,
            "bus_name": t.bus.bus_name if t.bus else "",
            "registration_number": t.bus.registration_number if t.bus else "",
            "route_name": t.route.name if t.route else "",
            "driver_name": t.driver.full_name if t.driver else "Unassigned",
            "gps_status": gps_status,
            "latitude": latest_gps.latitude if latest_gps else None,
            "longitude": latest_gps.longitude if latest_gps else None,
            "speed_kmh": latest_gps.speed_kmh if latest_gps else 0.0,
            "heading_degrees": latest_gps.heading_degrees if latest_gps else 0.0,
            "seconds_since_update": seconds_ago,
            "last_updated": latest_gps.recorded_at if latest_gps else None
        })
    return fleet

@router.get("/crew")
def list_crew(current_user: User = Depends(require_operator), db: Session = Depends(get_db)):
    """
    Returns list of drivers and conductors belonging to this operator.
    """
    drivers = db.query(User).filter(User.role == UserRole.DRIVER).all()
    conductors = db.query(User).filter(User.role == UserRole.CONDUCTOR).all()
    return {
        "drivers": [{"id": d.id, "name": d.full_name, "phone": d.phone} for d in drivers],
        "conductors": [{"id": c.id, "name": c.full_name, "phone": c.phone} for c in conductors]
    }
