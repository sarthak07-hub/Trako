from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Tuple
from datetime import datetime, date

class SearchTripsQuery(BaseModel):
    origin: str  # City or Stop Name
    destination: str  # City or Stop Name
    travel_date: date

class AvailableTripItem(BaseModel):
    trip_id: int
    trip_code: str
    bus_name: str
    bus_type: str
    registration_number: str
    origin_stop_name: str
    destination_stop_name: str
    boarding_stop_id: int
    destination_stop_id: int
    boarding_sequence: int
    destination_sequence: int
    departure_time: str
    arrival_time: str
    duration_minutes: int
    available_seats: int
    total_seats: int
    fare: float
    status: str

class SeatAvailabilityItem(BaseModel):
    seat_id: int
    seat_number: str
    deck: str
    row_num: int
    col_num: int
    seat_type: str
    is_available: bool
    current_occupant_segment: Optional[str] = None  # e.g. "Panaji -> Pernem" if booked for another segment

class TripSeatLayoutResponse(BaseModel):
    trip_id: int
    trip_code: str
    bus_id: int
    bus_name: str
    registration_number: str
    bus_type: str
    layout_type: str
    boarding_stop_id: int
    boarding_stop_name: str
    destination_stop_id: int
    destination_stop_name: str
    fare: float
    total_seats: int
    available_seats: int
    seats: List[SeatAvailabilityItem]

class BookingCreate(BaseModel):
    trip_id: int
    seat_id: int
    boarding_stop_id: int
    destination_stop_id: int
    passenger_name: str = Field(..., min_length=2)
    passenger_phone: str = Field(..., min_length=8)
    passenger_email: Optional[EmailStr] = None
    booking_source: str = "WEB"  # WEB, SEAT_QR, COUNTER

class BookingResponse(BaseModel):
    id: int
    booking_reference: str
    trip_id: int
    trip_code: str
    bus_name: str
    registration_number: str
    seat_number: str
    boarding_stop_name: str
    destination_stop_name: str
    departure_datetime: datetime
    fare_amount: float
    status: str
    passenger_name: str
    passenger_phone: str
    ticket_token: str
    qr_data: str
    booked_at: datetime

    class Config:
        from_attributes = True

class TicketDetailsResponse(BaseModel):
    booking_reference: str
    ticket_token: str
    qr_data: str
    passenger_name: str
    passenger_phone: str
    passenger_email: Optional[str] = None
    bus_name: str
    registration_number: str
    bus_type: str
    route_name: str
    seat_number: str
    deck: str
    boarding_stop_name: str
    destination_stop_name: str
    departure_datetime: datetime
    expected_arrival: datetime
    fare_amount: float
    status: str
    is_verified: bool
    verified_at: Optional[datetime] = None
    booking_source: str
    booked_at: datetime

class ConductorPassengerItem(BaseModel):
    booking_id: int
    ticket_id: int
    booking_reference: str
    ticket_token: str
    passenger_name: str
    passenger_phone: str
    seat_number: str
    boarding_stop_id: int
    boarding_stop_name: str
    destination_stop_id: int
    destination_stop_name: str
    boarding_sequence: int
    destination_sequence: int
    status: str  # CONFIRMED, BOARDED, NO_SHOW
    is_potential_no_show: bool = False
    verified_at: Optional[datetime] = None

class TicketVerificationRequest(BaseModel):
    ticket_token_or_ref: str
    trip_id: Optional[int] = None
    current_stop_id: Optional[int] = None

class BoardingActionRequest(BaseModel):
    booking_id: int
    action: str = "BOARDED"  # BOARDED or NO_SHOW_SEAT_RELEASED
    remarks: Optional[str] = None
    stop_id: Optional[int] = None
