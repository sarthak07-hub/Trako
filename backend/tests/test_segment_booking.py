import pytest
from app.services.booking_engine import check_segment_overlap
from app.models.bus import Seat
from tests.conftest import get_auth_header

def test_check_segment_overlap_math():
    """
    Unit test mathematical overlap function: max(s1, s2) < min(e1, e2)
    """
    # Consecutive non-overlapping: [0, 2] and [2, 4]
    assert check_segment_overlap(0, 2, 2, 4) is False
    assert check_segment_overlap(2, 4, 0, 2) is False

    # Disjoint non-overlapping: [0, 1] and [3, 4]
    assert check_segment_overlap(0, 1, 3, 4) is False

    # Overlapping: [0, 2] and [1, 3]
    assert check_segment_overlap(0, 2, 1, 3) is True

    # Exact match: [0, 2] and [0, 2]
    assert check_segment_overlap(0, 2, 0, 2) is True

    # Sub-segment inside larger: [1, 2] inside [0, 4]
    assert check_segment_overlap(1, 2, 0, 4) is True

def test_segment_booking_workflow(client, seeded_env, db_session):
    """
    End-to-end integration test of segment-based booking engine:
    1. Passenger 1 books Seat 1A from Panaji (0) to Pernem (2) -> SUCCESS
    2. Passenger 2 books Seat 1A from Pernem (2) to Ratnagiri (4) -> SUCCESS (Consecutive non-overlapping)
    3. Passenger 3 attempts to book Seat 1A from Mapusa (1) to Sawantwadi (3) -> REJECTED 409 CONFLICT
    4. Passenger 1 cancels booking -> Seat 1A now becomes available for [0, 2]
    """
    p1 = seeded_env["p1"]
    p2 = seeded_env["p2"]
    p3 = seeded_env["p3"]
    stops = seeded_env["stops"]
    trip = seeded_env["trip"]
    bus = seeded_env["bus"]

    panaji = stops[0]
    mapusa = stops[1]
    pernem = stops[2]
    sawantwadi = stops[3]
    ratnagiri = stops[4]

    seat_1a = db_session.query(Seat).filter(Seat.bus_id == bus.id, Seat.seat_number == "1A").first()
    assert seat_1a is not None

    # Step 1: Passenger 1 books Seat 1A: Panaji (0) -> Pernem (2)
    resp1 = client.post(
        "/api/v1/passenger/book",
        headers=get_auth_header(p1),
        json={
            "trip_id": trip.id,
            "seat_id": seat_1a.id,
            "boarding_stop_id": panaji.id,
            "destination_stop_id": pernem.id,
            "passenger_name": "Passenger One",
            "passenger_phone": "9820011111",
            "passenger_email": "p1@test.com"
        }
    )
    assert resp1.status_code == 201, resp1.text
    b1_data = resp1.json()
    assert b1_data["seat_number"] == "1A"
    assert b1_data["status"] == "CONFIRMED"
    booking1_ref = b1_data["booking_reference"]

    # Step 2: Passenger 2 books the SAME Seat 1A: Pernem (2) -> Ratnagiri (4)
    # Consecutive non-overlapping segment -> MUST SUCCEED
    resp2 = client.post(
        "/api/v1/passenger/book",
        headers=get_auth_header(p2),
        json={
            "trip_id": trip.id,
            "seat_id": seat_1a.id,
            "boarding_stop_id": pernem.id,
            "destination_stop_id": ratnagiri.id,
            "passenger_name": "Passenger Two",
            "passenger_phone": "9820022222",
            "passenger_email": "p2@test.com"
        }
    )
    assert resp2.status_code == 201, f"Failed consecutive booking: {resp2.text}"
    b2_data = resp2.json()
    assert b2_data["seat_number"] == "1A"
    assert b2_data["status"] == "CONFIRMED"

    # Step 3: Passenger 3 attempts to book Seat 1A: Mapusa (1) -> Sawantwadi (3)
    # Overlaps with both [0, 2] and [2, 4] -> MUST BE REJECTED WITH 409
    resp3 = client.post(
        "/api/v1/passenger/book",
        headers=get_auth_header(p3),
        json={
            "trip_id": trip.id,
            "seat_id": seat_1a.id,
            "boarding_stop_id": mapusa.id,
            "destination_stop_id": sawantwadi.id,
            "passenger_name": "Passenger Three",
            "passenger_phone": "9820033333",
            "passenger_email": "p3@test.com"
        }
    )
    assert resp3.status_code == 409, f"Expected 409 Conflict, got: {resp3.status_code} - {resp3.text}"
    assert "already booked for an overlapping segment" in resp3.json()["detail"]

    # Step 4: Invalid segment (Boarding after destination) -> MUST BE REJECTED WITH 400
    resp_invalid = client.post(
        "/api/v1/passenger/book",
        headers=get_auth_header(p3),
        json={
            "trip_id": trip.id,
            "seat_id": seat_1a.id,
            "boarding_stop_id": ratnagiri.id,
            "destination_stop_id": panaji.id,
            "passenger_name": "Backwards Passenger",
            "passenger_phone": "9820099999"
        }
    )
    assert resp_invalid.status_code == 400

    # Step 5: Passenger 1 cancels booking -> Seat 1A's [0, 2] segment is freed!
    resp_cancel = client.post(
        f"/api/v1/passenger/bookings/{booking1_ref}/cancel",
        headers=get_auth_header(p1)
    )
    assert resp_cancel.status_code == 200

    # Now Passenger 3 can book Panaji (0) to Pernem (2) on Seat 1A!
    resp_rebook = client.post(
        "/api/v1/passenger/book",
        headers=get_auth_header(p3),
        json={
            "trip_id": trip.id,
            "seat_id": seat_1a.id,
            "boarding_stop_id": panaji.id,
            "destination_stop_id": pernem.id,
            "passenger_name": "Passenger Three",
            "passenger_phone": "9820033333"
        }
    )
    assert resp_rebook.status_code == 201
