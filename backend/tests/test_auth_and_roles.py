import pytest
from tests.conftest import get_auth_header

def test_registration_and_login(client):
    # 1. Register new passenger
    reg_resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "fresh.user@trako.io",
            "password": "Password123!",
            "full_name": "Fresh User",
            "phone": "9811122233",
            "role": "PASSENGER"
        }
    )
    assert reg_resp.status_code == 201
    reg_data = reg_resp.json()
    assert "access_token" in reg_data
    assert reg_data["role"] == "PASSENGER"

    # 2. Duplicate registration rejected
    dup_resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "fresh.user@trako.io",
            "password": "Password123!",
            "full_name": "Fresh User Duplicate"
        }
    )
    assert dup_resp.status_code == 400
    assert "already exists" in dup_resp.json()["detail"]

    # 3. Login with correct credentials
    login_resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": "fresh.user@trako.io",
            "password": "Password123!"
        }
    )
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()

    # 4. Login with bad password
    bad_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "fresh.user@trako.io",
            "password": "WrongPassword!"
        }
    )
    assert bad_login.status_code == 401

def test_role_based_access_control(client, seeded_env):
    p1 = seeded_env["p1"]
    op = seeded_env["op"]

    # Unauthenticated request to operator endpoint
    unauth_resp = client.get("/api/v1/operator/buses")
    assert unauth_resp.status_code == 401

    # Passenger trying to access operator endpoint
    forbidden_resp = client.get(
        "/api/v1/operator/buses",
        headers=get_auth_header(p1)
    )
    assert forbidden_resp.status_code == 403
    assert "Access forbidden" in forbidden_resp.json()["detail"]

    # Operator accessing operator endpoint
    ok_resp = client.get(
        "/api/v1/operator/buses",
        headers=get_auth_header(op)
    )
    assert ok_resp.status_code == 200
    assert isinstance(ok_resp.json(), list)
