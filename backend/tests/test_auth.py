def test_login_parent_success(client):
    response = client.post(
        "/api/auth/login",
        json={"username": "parent_priya", "password": "parent123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["role"] == "parent"
    assert data["full_name"] == "Priya Kumari"

def test_login_asha_success(client):
    response = client.post(
        "/api/auth/login",
        json={"username": "asha_sunita", "password": "asha123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "asha"
    assert "Sunita Devi" in data["full_name"]

def test_login_invalid_credentials(client):
    response = client.post(
        "/api/auth/login",
        json={"username": "parent_priya", "password": "wrongpassword"}
    )
    assert response.status_code == 401

def test_register_new_parent(client):
    response = client.post(
        "/api/auth/register",
        json={
            "username": "new_mother",
            "phone": "9998887777",
            "full_name": "Meena Devi",
            "password": "securepassword",
            "role": "parent",
            "village_id": 1,
            "address": "Ward 4, Rampur"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "new_mother"
    assert data["role"] == "parent"
