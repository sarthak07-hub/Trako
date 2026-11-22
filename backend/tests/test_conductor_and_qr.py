import pytest
from app.models.bus import Seat
from tests.conftest import get_auth_header

def test_physical_seat_qr_flow(client, seeded_env, db_session):
    bus = seeded_env["bus"]
    seat_1a = db_session.query(Seat).filter(Seat.bus_id == bus.id, Seat.seat_number == "1A").first()
    
    # Scanning physical seat QR calls /api/v1/qr/bus-seat-info
    resp = client.get(f"/api/v1/qr/bus-seat-info?bus_id={bus.id}&seat_number=1A")
    assert resp.status_code == 200
    data = resp.json()
    assert data["bus"]["registration_number"] == bus.registration_number
    assert data["seat"]["seat_number"] == "1A"
    assert "available_trips" in data
    assert len(data["available_trips"]) >= 1

def test_conductor_ticket_verification_and_boarding(client, seeded_env, db_session):
    p1 = seeded_env["p1"]
    cnd = seeded_env["conductor"]
    stops = seeded_env["stops"]
    trip = seeded_env["trip"]
    bus = seeded_env["bus"]

    seat_2b = db_session.query(Seat).filter(Seat.bus_id == bus.id, Seat.seat_number == "2B").first()

    # 1. Book a ticket
    book_resp = client.post(
        "/api/v1/passenger/book",
        headers=get_auth_header(p1),
        json={
            "trip_id": trip.id,
            "seat_id": seat_2b.id,
            "boarding_stop_id": stops[0].id,
            "destination_stop_id": stops[2].id,
            "passenger_name": "Test Passenger",
            "passenger_phone": "9812345678"
        }
    )
    assert book_resp.status_code == 201
    booking_data = book_resp.json()
    ticket_token = booking_data["ticket_token"]
    booking_id = booking_data["id"]

    # 2. Conductor scans and verifies ticket
    verify_resp = client.post(
        "/api/v1/conductor/verify-ticket",
        headers=get_auth_header(cnd),
        json={
            "ticket_token_or_ref": ticket_token,
            "trip_id": trip.id
        }
    )
    assert verify_resp.status_code == 200
    vdata = verify_resp.json()
    assert vdata["valid"] is True
    assert vdata["status_code"] == "VALID_FOR_BOARDING"
    assert vdata["passenger_name"] == "Test Passenger"

    # 3. Conductor confirms boarding
    board_resp = client.post(
        "/api/v1/conductor/confirm-boarding",
        headers=get_auth_header(cnd),
        json={
            "booking_id": booking_id,
            "action": "BOARDED",
            "remarks": "Boarded via Platform 1 Gate"
        }
    )
    assert board_resp.status_code == 200
    assert board_resp.json()["status"] == "BOARDED"

    # 4. Verifying ticket again returns ALREADY_BOARDED
    verify_again = client.post(
        "/api/v1/conductor/verify-ticket",
        headers=get_auth_header(cnd),
        json={
            "ticket_token_or_ref": ticket_token,
            "trip_id": trip.id
        }
    )
    assert verify_again.status_code == 200
    assert verify_again.json()["status_code"] == "ALREADY_BOARDED"
