from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base, utc_now

class Stop(Base):
    __tablename__ = "stops"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, index=True)
    city = Column(String(100), nullable=False, index=True)
    state = Column(String(100), default="Goa", nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    landmark = Column(String(200), nullable=True)
    is_terminal = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=utc_now)

    # Relationships
    route_stops = relationship("RouteStop", back_populates="stop")

class Route(Base):
    __tablename__ = "routes"

    id = Column(Integer, primary_key=True, index=True)
    operator_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    route_code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(150), nullable=False)
    origin_stop_id = Column(Integer, ForeignKey("stops.id"), nullable=False)
    destination_stop_id = Column(Integer, ForeignKey("stops.id"), nullable=False)
    total_distance_km = Column(Float, default=0.0, nullable=False)
    estimated_duration_minutes = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    operator = relationship("User", back_populates="routes")
    origin_stop = relationship("Stop", foreign_keys=[origin_stop_id])
    destination_stop = relationship("Stop", foreign_keys=[destination_stop_id])
    route_stops = relationship("RouteStop", back_populates="route", cascade="all, delete-orphan", order_by="RouteStop.stop_sequence")
    schedules = relationship("Schedule", back_populates="route")
    trips = relationship("Trip", back_populates="route")

class RouteStop(Base):
    __tablename__ = "route_stops"

    id = Column(Integer, primary_key=True, index=True)
    route_id = Column(Integer, ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True)
    stop_id = Column(Integer, ForeignKey("stops.id", ondelete="CASCADE"), nullable=False, index=True)
    stop_sequence = Column(Integer, nullable=False)  # 0, 1, 2, 3... defines the exact segment order
    distance_from_origin_km = Column(Float, default=0.0, nullable=False)
    duration_from_origin_minutes = Column(Integer, default=0, nullable=False)
    halt_duration_minutes = Column(Integer, default=5, nullable=False)
    fare_from_origin = Column(Float, default=0.0, nullable=False)

    __table_args__ = (
        UniqueConstraint('route_id', 'stop_sequence', name='uq_route_stop_sequence'),
        UniqueConstraint('route_id', 'stop_id', name='uq_route_stop_id'),
    )

    # Relationships
    route = relationship("Route", back_populates="route_stops")
    stop = relationship("Stop", back_populates="route_stops")
