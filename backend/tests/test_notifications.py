from datetime import date, timedelta


def test_parent_and_asha_notifications(client):
    # 1. Trigger automatic notification generation across DB
    admin_login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    trigger_res = client.post("/api/notifications/trigger-auto-generation", headers=admin_headers)
    assert trigger_res.status_code == 200
    assert "summary" in trigger_res.json()
    assert trigger_res.json()["status"] == "success"

    # 2. Login as Parent (Priya Kumari)
    parent_login = client.post("/api/auth/login", json={"username": "parent_priya", "password": "parent123"})
    p_token = parent_login.json()["access_token"]
    p_headers = {"Authorization": f"Bearer {p_token}"}

    # Fetch Parent notifications
    p_notifs_res = client.get("/api/notifications", headers=p_headers)
    assert p_notifs_res.status_code == 200
    p_notifs = p_notifs_res.json()
    assert len(p_notifs) > 0

    first_notif = p_notifs[0]
    assert "title" in first_notif
    assert "message" in first_notif
    assert "priority" in first_notif
    assert "is_read" in first_notif

    # 3. Check unread count for Parent
    unread_res = client.get("/api/notifications/unread-count", headers=p_headers)
    assert unread_res.status_code == 200
    assert unread_res.json()["unread_count"] >= 1

    # 4. Mark single notification as read
    notif_id = first_notif["id"]
    read_res = client.post(f"/api/notifications/{notif_id}/read", headers=p_headers)
    assert read_res.status_code == 200
    assert read_res.json()["is_read"] is True

    # 5. Mark all as read
    read_all_res = client.post("/api/notifications/read-all", headers=p_headers)
    assert read_all_res.status_code == 200

    unread_after = client.get("/api/notifications/unread-count", headers=p_headers).json()
    assert unread_after["unread_count"] == 0

    # 6. Login as ASHA Worker (Sunita)
    asha_login = client.post("/api/auth/login", json={"username": "asha_sunita", "password": "asha123"})
    a_token = asha_login.json()["access_token"]
    a_headers = {"Authorization": f"Bearer {a_token}"}

    # Fetch ASHA notifications
    a_notifs_res = client.get("/api/notifications", headers=a_headers)
    assert a_notifs_res.status_code == 200
    a_notifs = a_notifs_res.json()
    assert len(a_notifs) > 0

    # Test filtering by priority HIGH
    high_res = client.get("/api/notifications?priority=HIGH", headers=a_headers)
    assert high_res.status_code == 200
    for n in high_res.json():
        assert n["priority"] == "HIGH"


def test_event_driven_notification_generation(client):
    # Parent logs in and registers a new child
    parent_login = client.post("/api/auth/login", json={"username": "parent_priya", "password": "parent123"})
    p_token = parent_login.json()["access_token"]
    p_headers = {"Authorization": f"Bearer {p_token}"}

    new_child_payload = {
        "full_name": "Baby Ananya",
        "date_of_birth": (date.today() - timedelta(days=45)).isoformat(),
        "gender": "Female",
        "village_id": 1,
        "house_number": "104",
        "parent_contact": "9876543210",
        "birth_weight_kg": 3.1
    }

    reg_res = client.post("/api/children", json=new_child_payload, headers=p_headers)
    assert reg_res.status_code == 201
    child_id = reg_res.json()["id"]

    # Check ASHA worker in Rampur (Sunita) received notification about new registration
    asha_login = client.post("/api/auth/login", json={"username": "asha_sunita", "password": "asha123"})
    a_token = asha_login.json()["access_token"]
    a_headers = {"Authorization": f"Bearer {a_token}"}

    a_notifs = client.get("/api/notifications", headers=a_headers).json()
    reg_notif = [n for n in a_notifs if "Baby Ananya" in n["message"] or "Baby Ananya" in n["title"]]
    assert len(reg_notif) > 0
    assert reg_notif[0]["notification_type"] == "new_child_registration"
    assert reg_notif[0]["priority"] == "HIGH"

    # ASHA verifies the child
    verify_res = client.post(f"/api/children/{child_id}/verify", headers=a_headers)
    assert verify_res.status_code == 200

    # Parent should receive notification that child was verified
    p_notifs = client.get("/api/notifications", headers=p_headers).json()
    verify_notif = [n for n in p_notifs if "Verified" in n["title"] and "Baby Ananya" in n["title"]]
    assert len(verify_notif) > 0
