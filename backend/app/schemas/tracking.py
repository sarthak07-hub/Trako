from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class LocationUpdateRequest(BaseModel):
    trip_id: int
    latitude: float
    longitude: float
    speed_kmh: Optional[float] = 0.0
    heading_degrees: Optional[float] = 0.0
    status: str = "LIVE"  # LIVE, DELAYED, UNAVAILABLE
    current_stop_id: Optional[int] = None

class RouteStopPoint(BaseModel):
    stop_id: int
    name: str
    city: str
    stop_sequence: int
    latitude: float
    longitude: float
    distance_from_origin_km: float
    duration_from_origin_minutes: int
    is_passed: bool = False

class LiveTrackingResponse(BaseModel):
    trip_id: int
    trip_code: str
    status: str  # LIVE, DELAYED, UNAVAILABLE
    bus_name: str
    registration_number: str
    bus_type: str
    driver_name: Optional[str] = None
    
    current_latitude: Optional[float] = None
    current_longitude: Optional[float] = None
    speed_kmh: Optional[float] = 0.0
    heading_degrees: Optional[float] = 0.0
    last_updated: Optional[datetime] = None
    seconds_since_update: Optional[int] = None
    
    route_name: str
    origin_name: str
    destination_name: str
    stops: List[RouteStopPoint] = []
    next_stop_name: Optional[str] = None
    estimated_arrival_minutes: Optional[int] = None

class NearbyStopResponse(BaseModel):
    id: int
    name: str
    city: str
    state: str
    latitude: float
    longitude: float
    landmark: Optional[str] = None
    distance_km: float
    is_terminal: bool
