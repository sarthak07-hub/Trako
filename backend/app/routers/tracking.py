from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.schedule import Trip, TripStatus
from app.models.tracking import GPSLocation, GPSStatus
from app.models.route import RouteStop, Stop
from app.schemas.tracking import LiveTrackingResponse, NearbyStopResponse, RouteStopPoint
from app.services.tracking_service import evaluate_gps_status, find_nearby_stops, haversine_distance_km
from app.services.websocket_manager import ws_manager

router = APIRouter(prefix="/tracking", tags=["Live Tracking & Nearby Bus Stands"])

@router.get("/live/{trip_id}", response_model=LiveTrackingResponse)
def get_live_trip_tracking(trip_id: int, db: Session = Depends(get_db)):
    """
    Returns full real-time snapshot of the trip's route, stops, current coordinates,
    speed, heading, status, and seconds since last GPS ping.
    """
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    route = trip.route
    route_stops = db.query(RouteStop).filter(
        RouteStop.route_id == route.id
    ).order_by(RouteStop.stop_sequence).all()

    # Get most recent GPS point
    latest_gps = db.query(GPSLocation).filter(
        GPSLocation.trip_id == trip.id
    ).order_by(GPSLocation.recorded_at.desc()).first()

    status_eval, seconds_ago = evaluate_gps_status(latest_gps)

    # Stops points
    stops_points = []
    for rs in route_stops:
        is_passed = False
        if latest_gps and rs.stop:
            # If bus has already reached or passed this stop distance
            # Check proximity to stop (< 500m)
            dist_to_stop = haversine_distance_km(latest_gps.latitude, latest_gps.longitude, rs.stop.latitude, rs.stop.longitude)
            if dist_to_stop < 0.5:
                is_passed = True

        stops_points.append(RouteStopPoint(
            stop_id=rs.stop_id,
            name=rs.stop.name,
            city=rs.stop.city,
            stop_sequence=rs.stop_sequence,
            latitude=rs.stop.latitude,
            longitude=rs.stop.longitude,
            distance_from_origin_km=rs.distance_from_origin_km,
            duration_from_origin_minutes=rs.duration_from_origin_minutes,
            is_passed=is_passed
        ))

    # Determine next stop
    next_stop_name = None
    if latest_gps and stops_points:
        # Pick the first stop ahead
        for sp in stops_points:
            d = haversine_distance_km(latest_gps.latitude, latest_gps.longitude, sp.latitude, sp.longitude)
            if d > 1.0:
                next_stop_name = f"{sp.name} ({sp.city})"
                break
        if not next_stop_name and stops_points:
            next_stop_name = f"{stops_points[-1].name} ({stops_points[-1].city})"

    return LiveTrackingResponse(
        trip_id=trip.id,
        trip_code=trip.trip_code,
        status=status_eval if trip.status == TripStatus.IN_TRANSIT else trip.status,
        bus_name=trip.bus.bus_name if trip.bus else "TRAKO Coach",
        registration_number=trip.bus.registration_number if trip.bus else "",
        bus_type=trip.bus.bus_type if trip.bus else "Standard",
        driver_name=trip.driver.full_name if trip.driver else "Assigned Driver",
        current_latitude=latest_gps.latitude if latest_gps else (route_stops[0].stop.latitude if route_stops else None),
        current_longitude=latest_gps.longitude if latest_gps else (route_stops[0].stop.longitude if route_stops else None),
        speed_kmh=latest_gps.speed_kmh if latest_gps else 0.0,
        heading_degrees=latest_gps.heading_degrees if latest_gps else 0.0,
        last_updated=latest_gps.recorded_at if latest_gps else None,
        seconds_since_update=seconds_ago,
        route_name=route.name,
        origin_name=f"{route.origin_stop.name} ({route.origin_stop.city})" if route.origin_stop else "",
        destination_name=f"{route.destination_stop.name} ({route.destination_stop.city})" if route.destination_stop else "",
        stops=stops_points,
        next_stop_name=next_stop_name,
        estimated_arrival_minutes=route.estimated_duration_minutes
    )

@router.get("/nearby-stops", response_model=List[NearbyStopResponse])
def get_nearby_stops(
    lat: float = Query(..., description="Passenger latitude"),
    lng: float = Query(..., description="Passenger longitude"),
    radius_km: float = Query(50.0, description="Search radius in kilometers"),
    db: Session = Depends(get_db)
):
    """
    Finds nearest bus stands / terminals given coordinates using the Haversine formula.
    """
    results = find_nearby_stops(db, lat, lng, radius_km)
    return [NearbyStopResponse(**r) for r in results]

# ----------------- WEBSOCKET ENDPOINTS -----------------

@router.websocket("/ws/live/{trip_id}")
async def websocket_live_tracking(websocket: WebSocket, trip_id: int):
    """
    WebSocket endpoint for real-time live tracking of a specific bus trip.
    """
    await ws_manager.connect_trip(trip_id, websocket)
    try:
        while True:
            # Keep connection open and receive any ping from client
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect_trip(trip_id, websocket)

@router.websocket("/ws/fleet/{operator_id}")
async def websocket_fleet_radar(websocket: WebSocket, operator_id: int):
    """
    WebSocket endpoint for streaming entire fleet tracking updates to operator dashboard.
    """
    await ws_manager.connect_operator(operator_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect_operator(operator_id, websocket)
