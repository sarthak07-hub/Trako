import pytest
from datetime import datetime, date, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from alembic.config import Config
from alembic import command
import os

from app.database import Base
from app.models import (
    User, UserRole,
    Bus, Seat,
    Stop, Route, RouteStop,
    Schedule, Trip, TripStatus,
    Booking, Ticket, BookingStatus,
    GPSLocation, BoardingRecord, DeviceAssignment, GPSStatus
)

TEST_DB_URL = "sqlite:///./test_batch1.db"

@pytest.fixture(scope="module")
def test_db():
    if os.path.exists("./test_batch1.db"):
        os.remove("./test_batch1.db")
        
    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Run Alembic upgrade head to test migration execution on clean database
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", TEST_DB_URL)
    command.upgrade(alembic_cfg, "head")
    
    yield TestingSessionLocal, engine
    
    # Teardown
    engine.dispose()
    if os.path.exists("./test_batch1.db"):
        os.remove("./test_batch1.db")

def test_alembic_migration_schema_and_models(test_db):
    TestingSessionLocal, engine = test_db
    session = TestingSessionLocal()

    # 1. Create Users with different roles
    op_user = User(
        email="operator@trako.goa",
        hashed_password="hashed_secret_pw",
        full_name="Kadamba Transport Corp",
        phone="+918322438000",
        role=UserRole.OPERATOR,
        company_name="Kadamba Transport Corporation Ltd",
        operator_license="GOA-RTO-OP-2026-001"
    )
    driver_user = User(
        email="driver@trako.goa",
        hashed_password="hashed_secret_pw",
        full_name="Ramesh Sawant",
        phone="+919822123456",
        role=UserRole.DRIVER,
        employee_id="KTCL-DRV-102",
        driving_license_number="GA-03-20150001234"
    )
    conductor_user = User(
        email="conductor@trako.goa",
        hashed_password="hashed_secret_pw",
        full_name="Sunil Gaonkar",
        phone="+919822654321",
        role=UserRole.CONDUCTOR,
        employee_id="KTCL-CND-304"
    )
    passenger_user = User(
        email="passenger@trako.goa",
        hashed_password="hashed_secret_pw",
        full_name="Pooja Naik",
        phone="+919822998877",
        role=UserRole.PASSENGER
    )
    session.add_all([op_user, driver_user, conductor_user, passenger_user])
    session.commit()

    assert op_user.id is not None
    assert op_user.role == UserRole.OPERATOR
    assert driver_user.role == UserRole.DRIVER

    # 2. Create Bus and Seats with physical QR identifiers
    bus = Bus(
        operator_id=op_user.id,
        registration_number="GA-03-Z-9901",
        bus_name="Kadamba Panaji-Margao Express",
        bus_type="AC Semi-Sleeper",
        seating_capacity=4,
        layout_type="2+2"
    )
    session.add(bus)
    session.commit()

    seat_1a = Seat(
        bus_id=bus.id,
        seat_number="1A",
        deck="LOWER",
        row_num=1,
        col_num=1,
        seat_type="WINDOW",
        qr_code_identifier=f"TRAKO-BUS-{bus.id}-SEAT-1A"
    )
    seat_1b = Seat(
        bus_id=bus.id,
        seat_number="1B",
        deck="LOWER",
        row_num=1,
        col_num=2,
        seat_type="AISLE",
        qr_code_identifier=f"TRAKO-BUS-{bus.id}-SEAT-1B"
    )
    session.add_all([seat_1a, seat_1b])
    session.commit()

    assert len(bus.seats) == 2
    assert seat_1a.qr_code_identifier == f"TRAKO-BUS-{bus.id}-SEAT-1A"

    # Test Seat unique constraint per bus
    duplicate_seat = Seat(
        bus_id=bus.id,
        seat_number="1A",
        deck="LOWER",
        row_num=1,
        col_num=1,
        seat_type="WINDOW"
    )
    session.add(duplicate_seat)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    # 3. Create Stops, Route and RouteStops with Sequences
    panaji = Stop(
        name="Panaji KTC Bus Stand",
        city="Panaji",
        state="Goa",
        latitude=15.4989,
        longitude=73.8278,
        landmark="Near Mandovi Bridge",
        is_terminal=True
    )
    bambolim = Stop(
        name="Bambolim GMC Cross",
        city="Bambolim",
        state="Goa",
        latitude=15.4542,
        longitude=73.8560,
        landmark="Opposite Goa Medical College",
        is_terminal=False
    )
    margao = Stop(
        name="Margao KTC Bus Terminal",
        city="Margao",
        state="Goa",
        latitude=15.2832,
        longitude=73.9685,
        landmark="Near South Goa Collectorate",
        is_terminal=True
    )
    session.add_all([panaji, bambolim, margao])
    session.commit()

    route = Route(
        operator_id=op_user.id,
        route_code="GOA-EXP-01",
        name="Panaji to Margao Fast Shuttle",
        origin_stop_id=panaji.id,
        destination_stop_id=margao.id,
        total_distance_km=33.5,
        estimated_duration_minutes=50
    )
    session.add(route)
    session.commit()

    # Route Stops with ordered sequences (0, 1, 2)
    rs0 = RouteStop(
        route_id=route.id,
        stop_id=panaji.id,
        stop_sequence=0,
        distance_from_origin_km=0.0,
        duration_from_origin_minutes=0,
        fare_from_origin=0.0
    )
    rs1 = RouteStop(
        route_id=route.id,
        stop_id=bambolim.id,
        stop_sequence=1,
        distance_from_origin_km=7.5,
        duration_from_origin_minutes=15,
        fare_from_origin=25.0
    )
    rs2 = RouteStop(
        route_id=route.id,
        stop_id=margao.id,
        stop_sequence=2,
        distance_from_origin_km=33.5,
        duration_from_origin_minutes=50,
        fare_from_origin=70.0
    )
    session.add_all([rs0, rs1, rs2])
    session.commit()

    assert len(route.route_stops) == 3
    assert route.route_stops[0].stop_sequence == 0
    assert route.route_stops[2].stop_sequence == 2

    # 4. Schedule & Trip
    schedule = Schedule(
        operator_id=op_user.id,
        route_id=route.id,
        departure_time="08:30",
        days_of_week="DAILY",
        default_bus_id=bus.id
    )
    session.add(schedule)
    session.commit()

    now = datetime.now()
    dep_time = now + timedelta(hours=1)
    arr_time = dep_time + timedelta(minutes=50)

    trip = Trip(
        trip_code="TRIP-PNJ-MRG-0830",
        schedule_id=schedule.id,
        operator_id=op_user.id,
        route_id=route.id,
        bus_id=bus.id,
        driver_id=driver_user.id,
        conductor_id=conductor_user.id,
        trip_date=date.today(),
        departure_datetime=dep_time,
        expected_arrival_datetime=arr_time,
        base_fare=70.0,
        status=TripStatus.SCHEDULED,
        boarding_deadline_minutes=10
    )
    session.add(trip)
    session.commit()

    assert trip.id is not None
    assert trip.driver.full_name == "Ramesh Sawant"
    assert trip.conductor.full_name == "Sunil Gaonkar"

    # 5. Booking and Ticket
    booking = Booking(
        booking_reference="TRK-2026-TEST01",
        trip_id=trip.id,
        passenger_id=passenger_user.id,
        seat_id=seat_1a.id,
        boarding_stop_id=panaji.id,
        destination_stop_id=margao.id,
        boarding_sequence=0,
        destination_sequence=2,
        fare_amount=70.0,
        passenger_name="Pooja Naik",
        passenger_phone="+919822998877",
        passenger_email="passenger@trako.goa",
        status=BookingStatus.CONFIRMED,
        booking_source="WEB"
    )
    session.add(booking)
    session.commit()

    ticket = Ticket(
        booking_id=booking.id,
        ticket_token="TKT-SECURE-TOKEN-UUID-001",
        qr_data='{"ref": "TRK-2026-TEST01", "sig": "sha256-signed-hash"}',
        is_verified=False
    )
    session.add(ticket)
    session.commit()

    assert booking.ticket is not None
    assert booking.ticket.ticket_token == "TKT-SECURE-TOKEN-UUID-001"

    # 6. GPS Location, Boarding Record, and Device Assignment
    gps = GPSLocation(
        trip_id=trip.id,
        driver_id=driver_user.id,
        latitude=15.4989,
        longitude=73.8278,
        speed_kmh=24.5,
        heading_degrees=180.0,
        status=GPSStatus.LIVE,
        current_stop_id=panaji.id
    )
    boarding_rec = BoardingRecord(
        ticket_id=ticket.id,
        trip_id=trip.id,
        conductor_id=conductor_user.id,
        stop_id=panaji.id,
        action="BOARDED",
        remarks="Boarded successfully through conductor scanner"
    )
    dev_assign = DeviceAssignment(
        driver_id=driver_user.id,
        bus_id=bus.id,
        trip_id=trip.id,
        device_identifier="DEVICE-MOTO-G84-001",
        is_active=True
    )
    session.add_all([gps, boarding_rec, dev_assign])
    session.commit()

    assert gps.id is not None
    assert len(trip.gps_locations) == 1
    assert boarding_rec.action == "BOARDED"
    assert dev_assign.device_identifier == "DEVICE-MOTO-G84-001"
    
    session.close()

def test_alembic_downgrade_and_upgrade():
    # Test that migrations can cleanly downgrade to base and upgrade back to head in an isolated DB
    downgrade_db_url = "sqlite:///./test_downgrade.db"
    if os.path.exists("./test_downgrade.db"):
        os.remove("./test_downgrade.db")
        
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", downgrade_db_url)
    
    # 1. Upgrade to head
    command.upgrade(alembic_cfg, "head")
    
    # 2. Downgrade to base
    command.downgrade(alembic_cfg, "base")
    
    # 3. Upgrade back to head
    command.upgrade(alembic_cfg, "head")
    
    if os.path.exists("./test_downgrade.db"):
        try:
            os.remove("./test_downgrade.db")
        except Exception:
            pass
