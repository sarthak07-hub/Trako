import math
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.schedule import Trip, TripStatus
from app.models.route import Stop, RouteStop
from app.models.tracking import GPSLocation, GPSStatus
from app.config import settings

def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on the earth in kilometers.
    """
    r = 6371.0  # Earth's radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(r * c, 2)

def validate_driver_for_trip(db: Session, driver_id: int, trip_id: int) -> Trip:
    """
    Ensures that the driver is assigned to the trip and the trip is authorized/active.
    Security requirement: Do not track a driver outside an authorized active trip.
    """
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
        
    if trip.driver_id != driver_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: You are not the assigned driver for this trip"
        )
        
    if trip.status not in [TripStatus.IN_TRANSIT, TripStatus.BOARDING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"GPS tracking rejected: Trip is currently '{trip.status}', not in an active tracking state"
        )
        
    return trip

def evaluate_gps_status(latest_loc: Optional[GPSLocation]) -> Tuple[str, Optional[int]]:
    """
    Determines status: LIVE, DELAYED, or UNAVAILABLE based on freshness.
    Never display stale GPS data as live.
    """
    if not latest_loc:
        return GPSStatus.UNAVAILABLE, None
        
    seconds_ago = int((datetime.utcnow() - latest_loc.recorded_at).total_seconds())
    
    if seconds_ago > settings.GPS_STALE_THRESHOLD_SECONDS:
        return GPSStatus.UNAVAILABLE, seconds_ago
        
    return latest_loc.status or GPSStatus.LIVE, seconds_ago

def find_nearby_stops(db: Session, user_lat: float, user_lon: float, max_radius_km: float = 50.0) -> List[dict]:
    """
    Computes distance to all active stops and returns ordered list of nearest stops.
    """
    stops = db.query(Stop).filter(Stop.is_active == True).all()
    results = []
    
    for s in stops:
        dist = haversine_distance_km(user_lat, user_lon, s.latitude, s.longitude)
        if dist <= max_radius_km:
            results.append({
                "id": s.id,
                "name": s.name,
                "city": s.city,
                "state": s.state,
                "latitude": s.latitude,
                "longitude": s.longitude,
                "landmark": s.landmark,
                "is_terminal": s.is_terminal,
                "distance_km": dist
            })
            
    # Sort by nearest first
    results.sort(key=lambda x: x["distance_km"])
    return results
