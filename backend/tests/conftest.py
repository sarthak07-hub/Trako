import pytest
from datetime import datetime, date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.config import settings
from app.models.user import User, UserRole
from app.models.bus import Bus, Seat
from app.models.route import Stop, Route, RouteStop
from app.models.schedule import Trip, TripStatus
from app.models.booking import Booking, Ticket, BookingStatus
from app.services.auth_service import hash_password, create_access_token
from app.routers.operator import create_default_seats_for_bus

# Use an isolated SQLite test database
TEST_DATABASE_URL = "sqlite:///./test_trako.db"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)

@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def seeded_env(db_session):
    """
    Sets up a clean test environment with operator, driver, conductor, passengers,
    bus, 5-stop route, and a scheduled trip.
    """
    # 1. Users
    op = User(
        email="test.op@trako.io",
        hashed_password=hash_password("Password123!"),
        full_name="Test Operator",
        role=UserRole.OPERATOR,
        is_active=True
    )
    drv = User(
        email="test.driver@trako.io",
        hashed_password=hash_password("Password123!"),
        full_name="Test Driver",
        role=UserRole.DRIVER,
        is_active=True
    )
    cnd = User(
        email="test.conductor@trako.io",
        hashed_password=hash_password("Password123!"),
        full_name="Test Conductor",
        role=UserRole.CONDUCTOR,
        is_active=True
    )
    p1 = User(
        email="test.passenger1@trako.io",
        hashed_password=hash_password("Password123!"),
        full_name="Passenger One",
        role=UserRole.PASSENGER,
        is_active=True
    )
    p2 = User(
        email="test.passenger2@trako.io",
        hashed_password=hash_password("Password123!"),
        full_name="Passenger Two",
        role=UserRole.PASSENGER,
        is_active=True
    )
    p3 = User(
        email="test.passenger3@trako.io",
        hashed_password=hash_password("Password123!"),
        full_name="Passenger Three",
        role=UserRole.PASSENGER,
        is_active=True
    )
    db_session.add_all([op, drv, cnd, p1, p2, p3])
    db_session.flush()

    # 2. Stops (Panaji -> Mapusa -> Pernem -> Sawantwadi -> Ratnagiri)
    stops = [
        Stop(name="Panaji KTC", city="Panaji", state="Goa", latitude=15.4989, longitude=73.8278, is_active=True),
        Stop(name="Mapusa Terminal", city="Mapusa", state="Goa", latitude=15.5937, longitude=73.8143, is_active=True),
        Stop(name="Pernem Stand", city="Pernem", state="Goa", latitude=15.7175, longitude=73.7972, is_active=True),
        Stop(name="Sawantwadi Depot", city="Sawantwadi", state="Maharashtra", latitude=15.9056, longitude=73.8203, is_active=True),
        Stop(name="Ratnagiri Stand", city="Ratnagiri", state="Maharashtra", latitude=16.9902, longitude=73.3120, is_active=True),
    ]
    db_session.add_all(stops)
    db_session.flush()

    # 3. Bus
    bus = Bus(
        operator_id=op.id,
        registration_number="GA-03-TEST-01",
        bus_name="Test Cruiser",
        bus_type="AC Semi-Sleeper",
        seating_capacity=36,
        layout_type="2+2",
        is_active=True
    )
    db_session.add(bus)
    db_session.flush()
    create_default_seats_for_bus(db_session, bus)

    # 4. Route
    route = Route(
        operator_id=op.id,
        route_code="TEST-RT-01",
        name="Panaji to Ratnagiri Test Route",
        origin_stop_id=stops[0].id,
        destination_stop_id=stops[4].id,
        total_distance_km=195.0,
        estimated_duration_minutes=300,
        is_active=True
    )
    db_session.add(route)
    db_session.flush()

    for idx, s in enumerate(stops):
        rs = RouteStop(
            route_id=route.id,
            stop_id=s.id,
            stop_sequence=idx,
            distance_from_origin_km=idx * 40.0,
            duration_from_origin_minutes=idx * 60,
            halt_duration_minutes=5,
            fare_from_origin=idx * 100.0
        )
        db_session.add(rs)
    db_session.flush()

    # 5. Trip
    today = date.today()
    dep = datetime(today.year, today.month, today.day, 10, 0)
    trip = Trip(
        trip_code="TEST-TRIP-01",
        operator_id=op.id,
        route_id=route.id,
        bus_id=bus.id,
        driver_id=drv.id,
        conductor_id=cnd.id,
        trip_date=today,
        departure_datetime=dep,
        expected_arrival_datetime=dep + timedelta(hours=5),
        base_fare=400.0,
        status=TripStatus.SCHEDULED,
        boarding_deadline_minutes=10
    )
    db_session.add(trip)
    db_session.commit()

    return {
        "op": op, "driver": drv, "conductor": cnd,
        "p1": p1, "p2": p2, "p3": p3,
        "stops": stops, "bus": bus, "route": route, "trip": trip
    }

def get_auth_header(user: User) -> dict:
    token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "full_name": user.full_name
    })
    return {"Authorization": f"Bearer {token}"}
