from datetime import date
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base, utc_now

class TripStatus:
    SCHEDULED = "SCHEDULED"
    BOARDING = "BOARDING"
    IN_TRANSIT = "IN_TRANSIT"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    operator_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    route_id = Column(Integer, ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True)
    departure_time = Column(String(10), nullable=False)  # HH:MM format e.g. "08:00"
    days_of_week = Column(String(50), default="DAILY", nullable=False)  # DAILY or MON,TUE,WED
    default_bus_id = Column(Integer, ForeignKey("buses.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=utc_now)

    # Relationships
    operator = relationship("User", back_populates="schedules", foreign_keys=[operator_id])
    route = relationship("Route", back_populates="schedules")
    default_bus = relationship("Bus")

class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, index=True)
    trip_code = Column(String(50), unique=True, index=True, nullable=False)
    schedule_id = Column(Integer, ForeignKey("schedules.id", ondelete="SET NULL"), nullable=True)
    operator_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    route_id = Column(Integer, ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True)
    bus_id = Column(Integer, ForeignKey("buses.id", ondelete="CASCADE"), nullable=False, index=True)
    driver_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    conductor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    trip_date = Column(Date, default=date.today, nullable=False, index=True)
    departure_datetime = Column(DateTime, nullable=False)
    expected_arrival_datetime = Column(DateTime, nullable=False)
    actual_arrival_datetime = Column(DateTime, nullable=True)
    
    base_fare = Column(Float, default=150.0, nullable=False)
    status = Column(String(20), default=TripStatus.SCHEDULED, nullable=False, index=True)
    boarding_deadline_minutes = Column(Integer, default=10, nullable=False)
    
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    operator = relationship("User", back_populates="trips_as_operator", foreign_keys=[operator_id])
    route = relationship("Route", back_populates="trips")
    bus = relationship("Bus", back_populates="trips")
    driver = relationship("User", back_populates="trips_as_driver", foreign_keys=[driver_id])
    conductor = relationship("User", back_populates="trips_as_conductor", foreign_keys=[conductor_id])
    bookings = relationship("Booking", back_populates="trip", cascade="all, delete-orphan")
    gps_locations = relationship("GPSLocation", back_populates="trip", cascade="all, delete-orphan", order_by="desc(GPSLocation.recorded_at)")
    device_assignments = relationship("DeviceAssignment", back_populates="trip")
