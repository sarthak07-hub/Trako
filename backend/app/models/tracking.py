from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base, utc_now

class GPSStatus:
    LIVE = "LIVE"
    DELAYED = "DELAYED"
    UNAVAILABLE = "UNAVAILABLE"

class GPSLocation(Base):
    __tablename__ = "gps_locations"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    driver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    speed_kmh = Column(Float, default=0.0, nullable=True)
    heading_degrees = Column(Float, default=0.0, nullable=True)
    status = Column(String(20), default=GPSStatus.LIVE, nullable=False)
    
    current_stop_id = Column(Integer, ForeignKey("stops.id", ondelete="SET NULL"), nullable=True)
    recorded_at = Column(DateTime, default=utc_now, nullable=False, index=True)

    # Relationships
    trip = relationship("Trip", back_populates="gps_locations")
    driver = relationship("User", foreign_keys=[driver_id])
    current_stop = relationship("Stop", foreign_keys=[current_stop_id])

class BoardingRecord(Base):
    __tablename__ = "boarding_records"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    conductor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    stop_id = Column(Integer, ForeignKey("stops.id", ondelete="SET NULL"), nullable=True, index=True)
    
    action = Column(String(30), nullable=False)  # BOARDED, NO_SHOW_SEAT_RELEASED, MANUAL_OVERRIDE
    timestamp = Column(DateTime, default=utc_now, nullable=False)
    remarks = Column(Text, nullable=True)

    # Relationships
    ticket = relationship("Ticket", back_populates="boarding_records")
    trip = relationship("Trip")
    conductor = relationship("User", foreign_keys=[conductor_id])
    stop = relationship("Stop", foreign_keys=[stop_id])

class DeviceAssignment(Base):
    __tablename__ = "device_assignments"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    bus_id = Column(Integer, ForeignKey("buses.id", ondelete="CASCADE"), nullable=False, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id", ondelete="SET NULL"), nullable=True, index=True)
    device_identifier = Column(String(100), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    assigned_at = Column(DateTime, default=utc_now, nullable=False)

    # Relationships
    driver = relationship("User", back_populates="device_assignments", foreign_keys=[driver_id])
    bus = relationship("Bus", back_populates="device_assignments", foreign_keys=[bus_id])
    trip = relationship("Trip", back_populates="device_assignments", foreign_keys=[trip_id])
