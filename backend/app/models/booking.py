from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base, utc_now

class BookingStatus:
    CONFIRMED = "CONFIRMED"
    BOARDED = "BOARDED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    booking_reference = Column(String(30), unique=True, index=True, nullable=False)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    passenger_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    seat_id = Column(Integer, ForeignKey("seats.id", ondelete="CASCADE"), nullable=False, index=True)
    
    boarding_stop_id = Column(Integer, ForeignKey("stops.id"), nullable=False, index=True)
    destination_stop_id = Column(Integer, ForeignKey("stops.id"), nullable=False, index=True)
    
    # Ordered sequence numbers for quick segment overlap checking:
    # Overlap occurs when: requested_from < existing_to AND requested_to > existing_from
    boarding_sequence = Column(Integer, nullable=False, index=True)
    destination_sequence = Column(Integer, nullable=False, index=True)
    
    fare_amount = Column(Float, nullable=False)
    passenger_name = Column(String(150), nullable=False)
    passenger_phone = Column(String(30), nullable=False)
    passenger_email = Column(String(255), nullable=True)
    
    status = Column(String(20), default=BookingStatus.CONFIRMED, nullable=False, index=True)
    booking_source = Column(String(20), default="WEB", nullable=False)  # WEB, SEAT_QR, COUNTER
    booked_at = Column(DateTime, default=utc_now, nullable=False)
    cancelled_at = Column(DateTime, nullable=True)
    cancellation_reason = Column(String(255), nullable=True)

    # Relationships
    trip = relationship("Trip", back_populates="bookings")
    passenger = relationship("User", back_populates="bookings")
    seat = relationship("Seat", back_populates="bookings")
    boarding_stop = relationship("Stop", foreign_keys=[boarding_stop_id])
    destination_stop = relationship("Stop", foreign_keys=[destination_stop_id])
    ticket = relationship("Ticket", back_populates="booking", uselist=False, cascade="all, delete-orphan")

class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    ticket_token = Column(String(100), unique=True, index=True, nullable=False)
    qr_data = Column(Text, nullable=False)  # Secure JSON payload containing signed ticket data
    
    issued_at = Column(DateTime, default=utc_now, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    verified_at = Column(DateTime, nullable=True)
    verified_by_conductor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verification_notes = Column(String(255), nullable=True)

    # Relationships
    booking = relationship("Booking", back_populates="ticket")
    verified_by = relationship("User", foreign_keys=[verified_by_conductor_id])
    boarding_records = relationship("BoardingRecord", back_populates="ticket", cascade="all, delete-orphan")
