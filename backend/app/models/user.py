from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base, utc_now

class UserRole:
    PASSENGER = "PASSENGER"
    OPERATOR = "OPERATOR"
    DRIVER = "DRIVER"
    CONDUCTOR = "CONDUCTOR"
    ADMIN = "ADMIN"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(150), nullable=False)
    phone = Column(String(30), nullable=True)
    role = Column(String(20), default=UserRole.PASSENGER, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Operator specific fields
    company_name = Column(String(150), nullable=True)
    operator_license = Column(String(100), nullable=True)
    
    # Driver / Conductor specific fields
    employee_id = Column(String(50), nullable=True)
    driving_license_number = Column(String(100), nullable=True)
    operator_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    buses = relationship("Bus", back_populates="operator", foreign_keys="Bus.operator_id")
    routes = relationship("Route", back_populates="operator", foreign_keys="Route.operator_id")
    schedules = relationship("Schedule", back_populates="operator", foreign_keys="Schedule.operator_id")
    trips_as_operator = relationship("Trip", back_populates="operator", foreign_keys="Trip.operator_id")
    trips_as_driver = relationship("Trip", back_populates="driver", foreign_keys="Trip.driver_id")
    trips_as_conductor = relationship("Trip", back_populates="conductor", foreign_keys="Trip.conductor_id")
    bookings = relationship("Booking", back_populates="passenger", foreign_keys="Booking.passenger_id")
    device_assignments = relationship("DeviceAssignment", back_populates="driver", foreign_keys="DeviceAssignment.driver_id")
