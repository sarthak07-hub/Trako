from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from app.database import Base, engine, SessionLocal
from app.models.user import User, UserRole
from app.models.bus import Bus, Seat
from app.models.route import Stop, Route, RouteStop
from app.models.schedule import Schedule, Trip, TripStatus
from app.models.booking import Booking, Ticket, BookingStatus
from app.models.tracking import GPSLocation, BoardingRecord, GPSStatus
from app.services.auth_service import hash_password
from app.services.booking_engine import generate_booking_reference, generate_ticket_token
from app.services.qr_service import generate_seat_qr_url, generate_ticket_qr_base64
from app.routers.operator import create_default_seats_for_bus

def seed_database():
    db: Session = SessionLocal()
    try:
        print("[*] Checking and seeding TRAKO database...")

        # If data already exists, skip
        if db.query(User).filter(User.email == "ops@coastallines.in").first():
            print("[*] Database already contains demo seed data.")
            return

        print("1. Creating demo accounts...")
        # Operator
        op_user = User(
            email="ops@coastallines.in",
            hashed_password=hash_password("Password123!"),
            full_name="KTC Coastal Travels",
            phone="+91 832 243 8900",
            role=UserRole.OPERATOR,
            company_name="KTC Coastal Travels Pvt Ltd",
            operator_license="GOA-OP-2024-8841",
            is_active=True
        )
        db.add(op_user)
        db.flush()

        # Driver
        driver_user = User(
            email="rajesh.driver@trako.io",
            hashed_password=hash_password("Password123!"),
            full_name="Rajesh Naik",
            phone="+91 982 211 4455",
            role=UserRole.DRIVER,
            employee_id="DRV-409",
            driving_license_number="GA-03-2019-004812",
            operator_id=op_user.id,
            is_active=True
        )
        db.add(driver_user)

        # Conductor
        conductor_user = User(
            email="suresh.conductor@trako.io",
            hashed_password=hash_password("Password123!"),
            full_name="Suresh Gawde",
            phone="+91 982 355 6677",
            role=UserRole.CONDUCTOR,
            employee_id="CND-882",
            operator_id=op_user.id,
            is_active=True
        )
        db.add(conductor_user)

        # Passengers
        p1 = User(
            email="aarav.passenger@trako.io",
            hashed_password=hash_password("Password123!"),
            full_name="Aarav Sharma",
            phone="+91 982 001 2345",
            role=UserRole.PASSENGER,
            is_active=True
        )
        p2 = User(
            email="priya.passenger@trako.io",
            hashed_password=hash_password("Password123!"),
            full_name="Priya Patel",
            phone="+91 982 002 3456",
            role=UserRole.PASSENGER,
            is_active=True
        )
        p3 = User(
            email="rohan.passenger@trako.io",
            hashed_password=hash_password("Password123!"),
            full_name="Rohan Deshmukh",
            phone="+91 982 003 4567",
            role=UserRole.PASSENGER,
            is_active=True
        )
        db.add_all([p1, p2, p3])
        db.flush()

        print("2. Creating bus stands & stations...")
        stops_data = [
            {"name": "Panaji KTC Central Bus Stand", "city": "Panaji", "state": "Goa", "lat": 15.4989, "lng": 73.8278, "landmark": "Near Patto Plaza, Mandovi Riverfront", "terminal": True},
            {"name": "Mapusa Bus Terminal", "city": "Mapusa", "state": "Goa", "lat": 15.5937, "lng": 73.8143, "landmark": "Near Municipal Market", "terminal": True},
            {"name": "Pernem Bus Stand", "city": "Pernem", "state": "Goa", "lat": 15.7175, "lng": 73.7972, "landmark": "National Highway 66 Junction", "terminal": False},
            {"name": "Sawantwadi Bus Depot", "city": "Sawantwadi", "state": "Maharashtra", "lat": 15.9056, "lng": 73.8203, "landmark": "Near Moti Talao Lake", "terminal": True},
            {"name": "Kankavli Bus Depot", "city": "Kankavli", "state": "Maharashtra", "lat": 16.2657, "lng": 73.7089, "landmark": "Sindhudurg Highway Bypass", "terminal": False},
            {"name": "Ratnagiri Central ST Stand", "city": "Ratnagiri", "state": "Maharashtra", "lat": 16.9902, "lng": 73.3120, "landmark": "Maruti Mandir Circle", "terminal": True},
            # Extra nearby stops for testing locator
            {"name": "Margao KTC Bus Terminal", "city": "Margao", "state": "Goa", "lat": 15.2736, "lng": 73.9582, "landmark": "Opposite Fatorda Stadium", "terminal": True},
            {"name": "Vasco da Gama Bus Stand", "city": "Vasco", "state": "Goa", "lat": 15.3991, "lng": 73.8122, "landmark": "Swatantra Path, Near Railway Station", "terminal": True},
            {"name": "Calangute Coastal Stand", "city": "Calangute", "state": "Goa", "lat": 15.5440, "lng": 73.7554, "landmark": "Calangute-Baga Road", "terminal": False}
        ]
        created_stops = []
        for sd in stops_data:
            s = Stop(
                name=sd["name"],
                city=sd["city"],
                state=sd["state"],
                latitude=sd["lat"],
                longitude=sd["lng"],
                landmark=sd["landmark"],
                is_terminal=sd["terminal"],
                is_active=True
            )
            db.add(s)
            created_stops.append(s)
        db.flush()

        print("3. Creating buses & seat layouts...")
        bus1 = Bus(
            operator_id=op_user.id,
            registration_number="GA-03-Z-9842",
            bus_name="TRAKO Coastal Star",
            bus_type="AC Semi-Sleeper",
            seating_capacity=36,
            layout_type="2+2",
            is_active=True
        )
        bus2 = Bus(
            operator_id=op_user.id,
            registration_number="GA-03-Z-7711",
            bus_name="TRAKO Western Express",
            bus_type="Luxury Seater",
            seating_capacity=30,
            layout_type="2+1",
            is_active=True
        )
        db.add_all([bus1, bus2])
        db.flush()

        create_default_seats_for_bus(db, bus1)
        create_default_seats_for_bus(db, bus2)
        db.refresh(bus1)
        db.refresh(bus2)

        print("4. Creating route & ordered stop sequences...")
        panaji = created_stops[0]
        mapusa = created_stops[1]
        pernem = created_stops[2]
        sawantwadi = created_stops[3]
        kankavli = created_stops[4]
        ratnagiri = created_stops[5]

        route1 = Route(
            operator_id=op_user.id,
            route_code="RT-PAN-RAT-01",
            name="Panaji to Ratnagiri Coastal Express",
            origin_stop_id=panaji.id,
            destination_stop_id=ratnagiri.id,
            total_distance_km=195.0,
            estimated_duration_minutes=310,
            is_active=True
        )
        db.add(route1)
        db.flush()

        route_stops_def = [
            (0, panaji.id, 0.0, 0, 0, 0.0),
            (1, mapusa.id, 15.0, 30, 5, 40.0),
            (2, pernem.id, 35.0, 65, 5, 90.0),
            (3, sawantwadi.id, 65.0, 115, 10, 170.0),
            (4, kankavli.id, 115.0, 185, 10, 290.0),
            (5, ratnagiri.id, 195.0, 310, 0, 450.0)
        ]
        for seq, sid, dist, dur, halt, fare in route_stops_def:
            rs = RouteStop(
                route_id=route1.id,
                stop_id=sid,
                stop_sequence=seq,
                distance_from_origin_km=dist,
                duration_from_origin_minutes=dur,
                halt_duration_minutes=halt,
                fare_from_origin=fare
            )
            db.add(rs)
        db.flush()

        print("5. Creating dated trips...")
        today = date.today()
        now = datetime.utcnow()
        trip_dep_today = datetime(today.year, today.month, today.day, 8, 30)
        trip_arr_today = trip_dep_today + timedelta(minutes=310)

        # Trip 1: Active in transit today
        trip1 = Trip(
            trip_code="TRIP-TODAY-001",
            operator_id=op_user.id,
            route_id=route1.id,
            bus_id=bus1.id,
            driver_id=driver_user.id,
            conductor_id=conductor_user.id,
            trip_date=today,
            departure_datetime=trip_dep_today,
            expected_arrival_datetime=trip_arr_today,
            base_fare=450.0,
            status=TripStatus.IN_TRANSIT,
            boarding_deadline_minutes=10
        )

        # Trip 2: Scheduled today evening
        trip2_dep = datetime(today.year, today.month, today.day, 16, 0)
        trip2 = Trip(
            trip_code="TRIP-TODAY-002",
            operator_id=op_user.id,
            route_id=route1.id,
            bus_id=bus2.id,
            driver_id=driver_user.id,
            conductor_id=conductor_user.id,
            trip_date=today,
            departure_datetime=trip2_dep,
            expected_arrival_datetime=trip2_dep + timedelta(minutes=310),
            base_fare=450.0,
            status=TripStatus.SCHEDULED,
            boarding_deadline_minutes=10
        )

        # Trip 3: Scheduled tomorrow
        tomorrow = today + timedelta(days=1)
        trip3_dep = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 9, 0)
        trip3 = Trip(
            trip_code="TRIP-TMRW-001",
            operator_id=op_user.id,
            route_id=route1.id,
            bus_id=bus1.id,
            driver_id=driver_user.id,
            conductor_id=conductor_user.id,
            trip_date=tomorrow,
            departure_datetime=trip3_dep,
            expected_arrival_datetime=trip3_dep + timedelta(minutes=310),
            base_fare=450.0,
            status=TripStatus.SCHEDULED,
            boarding_deadline_minutes=10
        )
        db.add_all([trip1, trip2, trip3])
        db.flush()

        print("6. Creating segment bookings demonstrating non-overlapping multi-passenger seat reuse...")
        seat_1a = db.query(Seat).filter(Seat.bus_id == bus1.id, Seat.seat_number == "1A").first()
        seat_1b = db.query(Seat).filter(Seat.bus_id == bus1.id, Seat.seat_number == "1B").first()

        # Booking A: Passenger Aarav books Seat 1A from Panaji (0) to Pernem (2) -> Status: BOARDED
        ref_a = generate_booking_reference()
        token_a = generate_ticket_token()
        booking_a = Booking(
            booking_reference=ref_a,
            trip_id=trip1.id,
            passenger_id=p1.id,
            seat_id=seat_1a.id,
            boarding_stop_id=panaji.id,
            destination_stop_id=pernem.id,
            boarding_sequence=0,
            destination_sequence=2,
            fare_amount=90.0,
            passenger_name=p1.full_name,
            passenger_phone=p1.phone,
            passenger_email=p1.email,
            status=BookingStatus.BOARDED,
            booking_source="WEB",
            booked_at=datetime.utcnow() - timedelta(days=1)
        )
        db.add(booking_a)
        db.flush()

        ticket_a = Ticket(
            booking_id=booking_a.id,
            ticket_token=token_a,
            qr_data=f"TRAKO:TICKET:{token_a}:{ref_a}",
            issued_at=datetime.utcnow() - timedelta(days=1),
            is_verified=True,
            verified_at=datetime.utcnow() - timedelta(minutes=45),
            verified_by_conductor_id=conductor_user.id,
            verification_notes="Verified & Boarded at Panaji Terminal"
        )
        db.add(ticket_a)

        # Booking B: Passenger Priya books SAME Seat 1A from Pernem (2) to Ratnagiri (5) -> Status: CONFIRMED
        # (This is valid and permitted because [0, 2] and [2, 5] do NOT overlap!)
        ref_b = generate_booking_reference()
        token_b = generate_ticket_token()
        booking_b = Booking(
            booking_reference=ref_b,
            trip_id=trip1.id,
            passenger_id=p2.id,
            seat_id=seat_1a.id,
            boarding_stop_id=pernem.id,
            destination_stop_id=ratnagiri.id,
            boarding_sequence=2,
            destination_sequence=5,
            fare_amount=360.0,
            passenger_name=p2.full_name,
            passenger_phone=p2.phone,
            passenger_email=p2.email,
            status=BookingStatus.CONFIRMED,
            booking_source="SEAT_QR",
            booked_at=datetime.utcnow() - timedelta(hours=3)
        )
        db.add(booking_b)
        db.flush()

        ticket_b = Ticket(
            booking_id=booking_b.id,
            ticket_token=token_b,
            qr_data=f"TRAKO:TICKET:{token_b}:{ref_b}",
            issued_at=datetime.utcnow() - timedelta(hours=3),
            is_verified=False
        )
        db.add(ticket_b)

        # Booking C: Passenger Rohan books Seat 1B from Mapusa (1) to Sawantwadi (3)
        ref_c = generate_booking_reference()
        token_c = generate_ticket_token()
        booking_c = Booking(
            booking_reference=ref_c,
            trip_id=trip1.id,
            passenger_id=p3.id,
            seat_id=seat_1b.id,
            boarding_stop_id=mapusa.id,
            destination_stop_id=sawantwadi.id,
            boarding_sequence=1,
            destination_sequence=3,
            fare_amount=130.0,
            passenger_name=p3.full_name,
            passenger_phone=p3.phone,
            passenger_email=p3.email,
            status=BookingStatus.CONFIRMED,
            booking_source="WEB",
            booked_at=datetime.utcnow() - timedelta(hours=2)
        )
        db.add(booking_c)
        db.flush()

        ticket_c = Ticket(
            booking_id=booking_c.id,
            ticket_token=token_c,
            qr_data=f"TRAKO:TICKET:{token_c}:{ref_c}",
            issued_at=datetime.utcnow() - timedelta(hours=2),
            is_verified=False
        )
        db.add(ticket_c)

        print("7. Adding live GPS location point for active trip...")
        # Live location near Sawantwadi on NH 66
        gps = GPSLocation(
            trip_id=trip1.id,
            driver_id=driver_user.id,
            latitude=15.7830,
            longitude=73.8120,
            speed_kmh=56.0,
            heading_degrees=15.0,
            status=GPSStatus.LIVE,
            current_stop_id=pernem.id,
            recorded_at=datetime.utcnow()
        )
        db.add(gps)

        # Boarding record for Aarav
        rec = BoardingRecord(
            ticket_id=ticket_a.id,
            trip_id=trip1.id,
            conductor_id=conductor_user.id,
            stop_id=panaji.id,
            action="BOARDED",
            timestamp=datetime.utcnow() - timedelta(minutes=45),
            remarks="Boarded at Panaji Platform 3"
        )
        db.add(rec)

        db.commit()
        print("[+] Demo data seeded successfully!")

    except Exception as e:
        db.rollback()
        print(f"[-] Error seeding database: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
