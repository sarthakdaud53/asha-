from datetime import date, timedelta


def test_child_registration_and_schedule_generation(client):
    # 1. Login as parent
    login_res = client.post(
        "/api/auth/login",
        json={"username": "parent_priya", "password": "parent123"}
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Register child born 45 days ago
    dob = (date.today() - timedelta(days=45)).isoformat()
    child_payload = {
        "full_name": "Rohan Kumar",
        "date_of_birth": dob,
        "gender": "Male",
        "birth_weight_kg": 3.2,
        "blood_group": "A+",
        "birth_place": "Rampur PHC",
        "mother_name": "Priya Kumari",
        "father_name": "Ramesh Kumar",
        "village_id": 1,
        "house_number": "12"
    }

    create_res = client.post("/api/children", json=child_payload, headers=headers)
    assert create_res.status_code == 201
    child_data = create_res.json()
    assert child_data["full_name"] == "Rohan Kumar"
    assert len(child_data["immunizations"]) >= 27  # Full UIP series generated from DB!
    assert child_data["total_vaccines"] >= 27

    # 3. Check Birth vaccines status
    birth_vacs = [im for im in child_data["immunizations"] if im["category"] == "Birth"]
    assert len(birth_vacs) == 3
    for b_vac in birth_vacs:
        # Since child is 45 days old and birth dose wasn't logged, it's overdue (>28d)
        assert b_vac["status"] == "overdue"


def test_vaccination_timeline_and_filters(client):
    # 1. Login as parent
    login_res = client.post(
        "/api/auth/login",
        json={"username": "parent_priya", "password": "parent123"}
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Query timeline for child 1 (Aarav)
    res = client.get("/api/immunizations/timeline/1", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["child_id"] == 1
    assert "timeline" in data
    assert "metrics" in data
    assert data["schedule_source"] == "vaccination_schedules (database)"

    # Test filtering by status
    res_due = client.get("/api/immunizations/timeline/1?status_filter=due", headers=headers)
    assert res_due.status_code == 200
    for item in res_due.json()["timeline"]:
        assert item["status"] == "due"

    res_overdue = client.get("/api/immunizations/timeline/1?status_filter=overdue", headers=headers)
    assert res_overdue.status_code == 200
    for item in res_overdue.json()["timeline"]:
        assert item["status"] == "overdue"


def test_administer_vaccine_flow_and_audit(client):
    # 1. Login as ASHA Worker (Sunita in Rampur village 1)
    login_res = client.post(
        "/api/auth/login",
        json={"username": "asha_sunita", "password": "asha123"}
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get Child 1's timeline to pick a pending vaccine record
    timeline_res = client.get("/api/immunizations/timeline/1", headers=headers)
    pending_records = [t for t in timeline_res.json()["timeline"] if t["status"] != "administered"]
    assert len(pending_records) > 0
    rec_id = pending_records[0]["record_id"]

    # 3. Administer the dose
    adm_payload = {
        "administered_date": date.today().isoformat(),
        "batch_number": "COV-BATCH-9988",
        "session_site": "Rampur Anganwadi 1",
        "aefi_reported": False,
        "notes": "Administered during Village Health & Nutrition Day"
    }

    adm_res = client.post(f"/api/immunizations/{rec_id}/administer", json=adm_payload, headers=headers)
    assert adm_res.status_code == 200
    adm_data = adm_res.json()
    assert adm_data["status"] == "administered"
    assert adm_data["batch_number"] == "COV-BATCH-9988"
    assert adm_data["administered_by_name"] is not None


def test_admin_configurable_vaccine_schedule(client):
    # 1. Login as Admin
    login_res = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"}
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Admin adds a new government-approved vaccine dynamically to master schedule
    new_vaccine_payload = {
        "vaccine_name": "Human Papillomavirus Vaccine",
        "code": "HPV-1",
        "dose_number": 1,
        "recommended_age_days": 3285,  # 9 years
        "recommended_timing": "9 Years",
        "category": "9-14 Years",
        "route": "Intramuscular",
        "site": "Left Upper Arm",
        "dose_amount": "0.5 ml",
        "prevents_diseases": "Cervical Cancer",
        "description": "National HPV Initiative",
        "is_active": True,
        "order_index": 28
    }

    create_res = client.post("/api/vaccines", json=new_vaccine_payload, headers=headers)
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["vaccine_name"] == "Human Papillomavirus Vaccine"
    assert created["code"] == "HPV-1"

    # 3. Verify it shows up in public/app master schedule endpoint
    all_vacs = client.get("/api/vaccines").json()
    hpv = next((v for v in all_vacs if v["code"] == "HPV-1"), None)
    assert hpv is not None
