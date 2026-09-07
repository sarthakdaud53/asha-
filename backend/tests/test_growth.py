from datetime import date

def test_record_growth_sam_detection(client):
    # Login as ASHA
    asha_login = client.post(
        "/api/auth/login",
        json={"username": "asha_sunita", "password": "asha123"}
    )
    token = asha_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Record low MUAC (11.0 cm -> SAM)
    growth_payload = {
        "recorded_date": date.today().isoformat(),
        "weight_kg": 5.2,
        "height_cm": 65.0,
        "muac_cm": 11.0,
        "notes": "Low MUAC detected during home visit"
    }

    res = client.post("/api/growth/1", json=growth_payload, headers=headers)
    assert res.status_code == 201
    data = res.json()
    assert "SAM" in data["nutritional_status"]

def test_asha_dashboard_metrics(client):
    asha_login = client.post(
        "/api/auth/login",
        json={"username": "asha_sunita", "password": "asha123"}
    )
    token = asha_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    dash_res = client.get("/api/asha/dashboard", headers=headers)
    assert dash_res.status_code == 200
    stats = dash_res.json()
    assert stats["village_name"] == "Rampur"
    assert stats["total_registered_children"] > 0

def test_asha_follow_up_planner(client):
    asha_login = client.post(
        "/api/auth/login",
        json={"username": "asha_sunita", "password": "asha123"}
    )
    token = asha_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    planner_res = client.get("/api/asha/follow-ups", headers=headers)
    assert planner_res.status_code == 200
    roster = planner_res.json()
    assert isinstance(roster, list)
    if len(roster) > 0:
        first_item = roster[0]
        assert "child_name" in first_item
        assert "parent_phone" in first_item
        assert "whatsapp_message" in first_item
