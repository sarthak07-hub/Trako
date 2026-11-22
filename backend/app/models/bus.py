from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base, utc_now

class Bus(Base):
    __tablename__ = "buses"

    id = Column(Integer, primary_key=True, index=True)
    operator_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    registration_number = Column(String(50), unique=True, index=True, nullable=False)
    bus_name = Column(String(100), nullable=False)
    bus_type = Column(String(50), default="AC Semi-Sleeper", nullable=False)  # AC Sleeper, AC Semi-Sleeper, Luxury Seater
    seating_capacity = Column(Integer, default=36, nullable=False)
    layout_type = Column(String(20), default="2+2", nullable=False)  # 2+2 or 2+1
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    operator = relationship("User", back_populates="buses", foreign_keys=[operator_id])
    seats = relationship("Seat", back_populates="bus", cascade="all, delete-orphan", order_by="Seat.seat_number")
    trips = relationship("Trip", back_populates="bus")
    device_assignments = relationship("DeviceAssignment", back_populates="bus")

class Seat(Base):
    __tablename__ = "seats"

    id = Column(Integer, primary_key=True, index=True)
    bus_id = Column(Integer, ForeignKey("buses.id", ondelete="CASCADE"), nullable=False, index=True)
    seat_number = Column(String(10), nullable=False, index=True)  # e.g., "1A", "1B", "12"
    deck = Column(String(10), default="LOWER", nullable=False)  # LOWER, UPPER
    row_num = Column(Integer, default=1, nullable=False)
    col_num = Column(Integer, default=1, nullable=False)
    seat_type = Column(String(20), default="WINDOW", nullable=False)  # WINDOW, AISLE, MIDDLE, SLEEPER_LOWER, SLEEPER_UPPER
    qr_code_identifier = Column(String(100), nullable=True, unique=True, index=True)  # Unique identifier for physical QR

    created_at = Column(DateTime, default=utc_now)

    __table_args__ = (
        UniqueConstraint('bus_id', 'seat_number', name='uq_bus_seat_number'),
    )

    # Relationships
    bus = relationship("Bus", back_populates="seats")
    bookings = relationship("Booking", back_populates="seat")
