from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User, UserRole
from app.models.schedule import Trip, TripStatus
from app.models.tracking import GPSLocation, GPSStatus
from app.schemas.tracking import LocationUpdateRequest
from app.services.auth_service import get_current_user, require_role
from app.services.tracking_service import validate_driver_for_trip, evaluate_gps_status
from app.services.websocket_manager import ws_manager

router = APIRouter(prefix="/driver", tags=["Driver Operations"])

require_driver = require_role([UserRole.DRIVER, UserRole.ADMIN])

@router.get("/assigned-trips")
def get_assigned_trips(current_user: User = Depends(require_driver), db: Session = Depends(get_db)):
    """
    Returns all trips assigned to the logged-in driver.
    """
    trips = db.query(Trip).filter(
        Trip.driver_id == current_user.id
    ).order_by(Trip.departure_datetime.desc()).all()

    output = []
    for t in trips:
        stops = []
        for rs in t.route.route_stops:
            stops.append({
                "sequence": rs.stop_sequence,
                "name": rs.stop.name,
                "city": rs.stop.city,
                "lat": rs.stop.latitude,
                "lng": rs.stop.longitude,
                "duration_min": rs.duration_from_origin_minutes
            })

        latest_gps = db.query(GPSLocation).filter(
            GPSLocation.trip_id == t.id
        ).order_by(GPSLocation.recorded_at.desc()).first()

        gps_status, _ = evaluate_gps_status(latest_gps)

        output.append({
            "id": t.id,
            "trip_code": t.trip_code,
            "trip_date": str(t.trip_date),
            "departure_datetime": t.departure_datetime,
            "expected_arrival_datetime": t.expected_arrival_datetime,
            "status": t.status,
            "bus_name": t.bus.bus_name if t.bus else "",
            "registration_number": t.bus.registration_number if t.bus else "",
            "route_name": t.route.name if t.route else "",
            "gps_status": gps_status,
            "stops": stops
        })
    return output

@router.post("/trips/{trip_id}/start")
def start_trip(trip_id: int, current_user: User = Depends(require_driver), db: Session = Depends(get_db)):
    """
    Driver starts an authorized trip. Trip status is updated to IN_TRANSIT.
    """
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    if trip.driver_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Unauthorized: You are not assigned to this trip")

    if trip.status == TripStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Cannot restart a completed trip")

    trip.status = TripStatus.IN_TRANSIT
    trip.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Trip started successfully. GPS location sharing is now active.", "status": trip.status}

@router.post("/trips/{trip_id}/end")
def end_trip(trip_id: int, current_user: User = Depends(require_driver), db: Session = Depends(get_db)):
    """
    Driver finishes the trip. Trip status updated to COMPLETED. Location sharing stops.
    """
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    if trip.driver_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Unauthorized: You are not assigned to this trip")

    trip.status = TripStatus.COMPLETED
    trip.actual_arrival_datetime = datetime.utcnow()
    trip.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Trip ended. GPS tracking disabled.", "status": trip.status}

@router.post("/location")
async def update_gps_location(
    loc_in: LocationUpdateRequest,
    current_user: User = Depends(require_driver),
    db: Session = Depends(get_db)
):
    """
    Receives smartphone GPS coordinates from authorized driver during an active trip.
    Validates assignment and active status, saves coordinate record, and broadcasts via WebSockets.
    """
    # Security validation
    trip = validate_driver_for_trip(db, current_user.id, loc_in.trip_id)

    # Save to database
    gps_entry = GPSLocation(
        trip_id=trip.id,
        driver_id=current_user.id,
        latitude=loc_in.latitude,
        longitude=loc_in.longitude,
        speed_kmh=loc_in.speed_kmh or 0.0,
        heading_degrees=loc_in.heading_degrees or 0.0,
        status=loc_in.status or GPSStatus.LIVE,
        current_stop_id=loc_in.current_stop_id,
        recorded_at=datetime.utcnow()
    )
    db.add(gps_entry)
    db.commit()

    # Real-time WebSocket broadcast payload
    broadcast_data = {
        "type": "GPS_UPDATE",
        "trip_id": trip.id,
        "trip_code": trip.trip_code,
        "bus_name": trip.bus.bus_name if trip.bus else "",
        "registration_number": trip.bus.registration_number if trip.bus else "",
        "latitude": loc_in.latitude,
        "longitude": loc_in.longitude,
        "speed_kmh": loc_in.speed_kmh or 0.0,
        "heading_degrees": loc_in.heading_degrees or 0.0,
        "status": loc_in.status or GPSStatus.LIVE,
        "recorded_at": gps_entry.recorded_at.isoformat()
    }

    # Broadcast to passenger tracking listeners and operator fleet listeners
    await ws_manager.broadcast_trip_location(trip.id, broadcast_data)
    await ws_manager.broadcast_operator_fleet(trip.operator_id, broadcast_data)

    return {"message": "Location updated and broadcasted successfully", "recorded_at": gps_entry.recorded_at}
