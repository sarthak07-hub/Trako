from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class StopBase(BaseModel):
    name: str = Field(..., example="Panaji KTC Bus Stand")
    city: str = Field(..., example="Panaji")
    state: str = Field("Goa", example="Goa")
    latitude: float = Field(..., example=15.4989)
    longitude: float = Field(..., example=73.8278)
    landmark: Optional[str] = None
    is_terminal: bool = False

class StopCreate(StopBase):
    pass

class StopResponse(StopBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class RouteStopInput(BaseModel):
    stop_id: int
    stop_sequence: int
    distance_from_origin_km: float = 0.0
    duration_from_origin_minutes: int = 0
    halt_duration_minutes: int = 5
    fare_from_origin: float = 0.0

class RouteStopResponse(BaseModel):
    id: int
    stop_id: int
    stop_sequence: int
    distance_from_origin_km: float
    duration_from_origin_minutes: int
    halt_duration_minutes: int
    fare_from_origin: float
    stop: StopResponse

    class Config:
        from_attributes = True

class RouteCreate(BaseModel):
    route_code: str = Field(..., example="RT-GOA-RAT-01")
    name: str = Field(..., example="Panaji to Ratnagiri Express")
    origin_stop_id: int
    destination_stop_id: int
    total_distance_km: float
    estimated_duration_minutes: int
    stops: List[RouteStopInput]

class RouteResponse(BaseModel):
    id: int
    operator_id: int
    route_code: str
    name: str
    origin_stop_id: int
    destination_stop_id: int
    total_distance_km: float
    estimated_duration_minutes: int
    is_active: bool
    created_at: datetime
    origin_stop: Optional[StopResponse] = None
    destination_stop: Optional[StopResponse] = None
    route_stops: List[RouteStopResponse] = []

    class Config:
        from_attributes = True
