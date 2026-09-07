def test_admin_provision_asha_worker(client):
    # Admin login
    admin_login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    token = admin_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Provision new ASHA for Chandpur Village (ID: 3)
    payload = {
        "username": "asha_kamla",
        "phone": "9811223344",
        "full_name": "Kamla Bai (ASHA)",
        "password": "secureashapass",
        "assigned_village_id": 3,
        "qualification": "Graduate",
        "experience_years": 3
    }

    res = client.post("/api/admin/asha-workers", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert data["full_name"] == "Kamla Bai (ASHA)"
    assert "ASHA-CHA" in data["worker_code"]

    # Newly provisioned ASHA can now log in
    new_login = client.post("/api/auth/login", json={"username": "asha_kamla", "password": "secureashapass"})
    assert new_login.status_code == 200
    assert new_login.json()["role"] == "asha"

def test_admin_view_audit_logs(client):
    admin_login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    token = admin_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/api/admin/audit-logs", headers=headers)
    assert res.status_code == 200
    logs = res.json()
    assert len(logs) > 0
    assert "action" in logs[0]
