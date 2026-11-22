from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class SeatBase(BaseModel):
    seat_number: str
    deck: str = "LOWER"
    row_num: int = 1
    col_num: int = 1
    seat_type: str = "WINDOW"
    qr_code_identifier: Optional[str] = None

class SeatResponse(SeatBase):
    id: int
    bus_id: int

    class Config:
        from_attributes = True

class BusCreate(BaseModel):
    registration_number: str = Field(..., example="GA-03-Z-9842")
    bus_name: str = Field(..., example="TRAKO Super Express")
    bus_type: str = Field("AC Semi-Sleeper", example="AC Semi-Sleeper")  # AC Sleeper, AC Semi-Sleeper, Luxury Seater
    seating_capacity: int = Field(36, ge=10, le=60)
    layout_type: str = Field("2+2", example="2+2")  # 2+2 or 2+1

class BusUpdate(BaseModel):
    bus_name: Optional[str] = None
    bus_type: Optional[str] = None
    is_active: Optional[bool] = None

class BusResponse(BaseModel):
    id: int
    operator_id: int
    registration_number: str
    bus_name: str
    bus_type: str
    seating_capacity: int
    layout_type: str
    is_active: bool
    created_at: datetime
    seats: List[SeatResponse] = []

    class Config:
        from_attributes = True
