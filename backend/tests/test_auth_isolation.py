from datetime import date, timedelta

def test_parent_registration_and_login(client):
    # Register new parent
    res = client.post("/api/auth/register", json={
        "username": "test_mother_1",
        "phone": "9811122233",
        "full_name": "Kavita Devi",
        "password": "password123",
        "village_id": 1,
        "address": "House 10, Rampur"
    })
    assert res.status_code == 201
    data = res.json()
    assert data["role"] == "parent"
    assert "access_token" in data

    # Login
    login_res = client.post("/api/auth/login", json={
        "username": "test_mother_1",
        "password": "password123"
    })
    assert login_res.status_code == 200
    assert login_res.json()["role"] == "parent"

def test_parent_isolation_cannot_access_other_parent_child(client):
    # Login as Parent 1 (Priya)
    p1_login = client.post("/api/auth/login", json={"username": "parent_priya", "password": "parent123"})
    p1_token = p1_login.json()["access_token"]
    p1_headers = {"Authorization": f"Bearer {p1_token}"}

    # Login as Parent 2 (Anita)
    p2_login = client.post("/api/auth/login", json={"username": "parent_anita", "password": "parent123"})
    p2_token = p2_login.json()["access_token"]
    p2_headers = {"Authorization": f"Bearer {p2_token}"}

    # Parent 1 gets own child (Child 1 - Aarav) -> 200 OK
    own_res = client.get("/api/children/1", headers=p1_headers)
    assert own_res.status_code == 200
    assert own_res.json()["full_name"] == "Aarav Kumar"

    # Parent 1 attempts to access Parent 2's child (Child 2 - Ananya) -> 403 Forbidden!
    other_res = client.get("/api/children/2", headers=p1_headers)
    assert other_res.status_code == 403
    assert "Access denied" in other_res.json()["detail"]

def test_parent_cannot_access_asha_or_admin_endpoints(client):
    p_login = client.post("/api/auth/login", json={"username": "parent_priya", "password": "parent123"})
    token = p_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Attempt to access ASHA dashboard -> 403
    asha_res = client.get("/api/asha/dashboard", headers=headers)
    assert asha_res.status_code == 403

    # Attempt to access Admin dashboard -> 403
    admin_res = client.get("/api/admin/dashboard", headers=headers)
    assert admin_res.status_code == 403
