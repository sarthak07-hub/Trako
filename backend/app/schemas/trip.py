from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from app.schemas.bus import BusResponse
from app.schemas.route import RouteResponse

class ScheduleCreate(BaseModel):
    route_id: int
    departure_time: str = Field(..., example="07:30")
    days_of_week: str = "DAILY"
    default_bus_id: Optional[int] = None

class ScheduleResponse(BaseModel):
    id: int
    operator_id: int
    route_id: int
    departure_time: str
    days_of_week: str
    default_bus_id: Optional[int] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class TripCreate(BaseModel):
    route_id: int
    bus_id: int
    trip_date: date
    departure_datetime: datetime
    expected_arrival_datetime: datetime
    base_fare: float = 150.0
    driver_id: Optional[int] = None
    conductor_id: Optional[int] = None
    boarding_deadline_minutes: int = 10

class TripUpdate(BaseModel):
    driver_id: Optional[int] = None
    conductor_id: Optional[int] = None
    status: Optional[str] = None
    actual_arrival_datetime: Optional[datetime] = None

class TripResponse(BaseModel):
    id: int
    trip_code: str
    schedule_id: Optional[int] = None
    operator_id: int
    route_id: int
    bus_id: int
    driver_id: Optional[int] = None
    conductor_id: Optional[int] = None
    trip_date: date
    departure_datetime: datetime
    expected_arrival_datetime: datetime
    actual_arrival_datetime: Optional[datetime] = None
    base_fare: float
    status: str
    boarding_deadline_minutes: int
    
    bus_name: Optional[str] = None
    registration_number: Optional[str] = None
    bus_type: Optional[str] = None
    route_name: Optional[str] = None
    driver_name: Optional[str] = None
    conductor_name: Optional[str] = None
    booked_seats_count: Optional[int] = 0
    total_seats_count: Optional[int] = 0

    class Config:
        from_attributes = True
