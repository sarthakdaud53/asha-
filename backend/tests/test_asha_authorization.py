from datetime import date, timedelta


def test_asha_village_territory_isolation(client):
    # ASHA 1 (Sunita - assigned to Rampur Village, ID: 1)
    asha1_login = client.post("/api/auth/login", json={"username": "asha_sunita", "password": "asha123"})
    asha1_token = asha1_login.json()["access_token"]
    asha1_headers = {"Authorization": f"Bearer {asha1_token}"}

    # ASHA 2 (Rekha - assigned to Belur Village, ID: 2)
    asha2_login = client.post("/api/auth/login", json={"username": "asha_rekha", "password": "asha123"})
    asha2_token = asha2_login.json()["access_token"]
    asha2_headers = {"Authorization": f"Bearer {asha2_token}"}

    # Sunita accesses Rampur child (Child 1 - Aarav) -> 200 OK
    res_rampur = client.get("/api/children/1", headers=asha1_headers)
    assert res_rampur.status_code == 200

    # Sunita attempts to access Belur child (Child 3 - Vihaan) -> 403 Forbidden!
    res_belur_forbidden = client.get("/api/children/3", headers=asha1_headers)
    assert res_belur_forbidden.status_code == 403
    assert "jurisdiction" in res_belur_forbidden.json()["detail"].lower()

    # Rekha accesses Belur child (Child 3 - Vihaan) -> 200 OK
    res_belur_ok = client.get("/api/children/3", headers=asha2_headers)
    assert res_belur_ok.status_code == 200


def test_asha_cannot_administer_dose_in_unassigned_village(client):
    # ASHA 1 (Sunita - Rampur)
    asha1_login = client.post("/api/auth/login", json={"username": "asha_sunita", "password": "asha123"})
    token = asha1_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Belur child (Child 3) has vaccine records. Admin gets Child 3 detail
    admin_login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    admin_token = admin_login.json()["access_token"]
    child3_detail = client.get("/api/children/3", headers={"Authorization": f"Bearer {admin_token}"}).json()

    pending_rec = [r for r in child3_detail["immunizations"] if r["status"] != "administered"][0]

    # Sunita attempts to administer vaccine to Belur child -> 403 Forbidden!
    adm_payload = {
        "administered_date": date.today().isoformat(),
        "batch_number": "ILLEGAL-CROSS-VILLAGE",
        "session_site": "Rampur Health Post"
    }

    cross_res = client.post(f"/api/immunizations/{pending_rec['id']}/administer", json=adm_payload, headers=headers)
    assert cross_res.status_code == 403
    assert "jurisdiction" in cross_res.json()["detail"].lower()


def test_asha_dashboard_and_priority_followups(client):
    # Login as Sunita (Rampur ASHA)
    asha_login = client.post("/api/auth/login", json={"username": "asha_sunita", "password": "asha123"})
    token = asha_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Test 8 Dashboard Cards
    dash_res = client.get("/api/asha/dashboard", headers=headers)
    assert dash_res.status_code == 200
    d = dash_res.json()
    assert d["village_name"] == "Rampur"
    assert "total_families" in d
    assert "total_children" in d
    assert "vaccinations_completed" in d
    assert "vaccinations_due" in d
    assert "vaccinations_overdue" in d
    assert "upcoming_vaccinations" in d
    assert "pending_verification" in d
    assert "todays_followups" in d

    # 2. Test Priority Follow-ups (categorized into HIGH, MEDIUM, LOW)
    pf_res = client.get("/api/asha/priority-follow-ups", headers=headers)
    assert pf_res.status_code == 200
    items = pf_res.json()
    assert len(items) > 0
    for item in items:
        assert item["priority"] in ["HIGH", "MEDIUM", "LOW"]
        assert "child_name" in item
        assert "parent_name" in item
        assert "village_name" in item
        assert "reason" in item
        assert "due_date" in item
        assert "whatsapp_message" in item

    # 3. Test Priority Filter: HIGH
    high_res = client.get("/api/asha/priority-follow-ups?priority=HIGH", headers=headers)
    assert high_res.status_code == 200
    for item in high_res.json():
        assert item["priority"] == "HIGH"

    # 4. Test Families endpoint
    fam_res = client.get("/api/asha/families", headers=headers)
    assert fam_res.status_code == 200
    assert len(fam_res.json()) > 0

    # 5. Test Verification
    verify_res = client.post("/api/children/1/verify", headers=headers)
    assert verify_res.status_code == 200
    assert verify_res.json()["is_verified"] is True


def test_house_visit_management_lifecycle(client):
    # Login as Sunita (Rampur ASHA)
    asha_login = client.post("/api/auth/login", json={"username": "asha_sunita", "password": "asha123"})
    token = asha_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    today = date.today()

    # 1. Create a scheduled house visit
    visit_payload = {
        "child_id": 1,
        "visit_date": today.isoformat(),
        "reason": "Vaccination overdue",
        "remarks": "Counseling mother on overdue vaccination dose",
        "status": "scheduled"
    }

    create_res = client.post("/api/asha/house-visits", json=visit_payload, headers=headers)
    assert create_res.status_code == 201
    v = create_res.json()
    assert v["child_id"] == 1
    assert v["priority"] == "HIGH"  # Auto-computed priority for overdue vaccine!
    assert v["status"] == "scheduled"
    visit_id = v["id"]

    # 2. Get counts
    counts_res = client.get("/api/asha/house-visits/counts", headers=headers)
    assert counts_res.status_code == 200
    counts = counts_res.json()
    assert "today" in counts
    assert "upcoming" in counts
    assert "pending" in counts
    assert "completed" in counts

    # 3. Filter by category 'today'
    today_res = client.get("/api/asha/house-visits?category=today", headers=headers)
    assert today_res.status_code == 200
    assert any(item["id"] == visit_id for item in today_res.json())

    # 4. Reschedule visit to tomorrow
    tomorrow = (today + timedelta(days=1)).isoformat()
    resched_res = client.put(f"/api/asha/house-visits/{visit_id}/reschedule?new_visit_date={tomorrow}&reason=Family+requested+evening+time", headers=headers)
    assert resched_res.status_code == 200
    assert resched_res.json()["status"] == "rescheduled"
    assert resched_res.json()["visit_date"] == tomorrow

    # 5. Mark visit completed with observations and action taken
    comp_res = client.put(
        f"/api/asha/house-visits/{visit_id}/complete?remarks=Visited+family+mother+agreed+to+bring+child&action_taken=Issued+Anganwadi+session+slip",
        headers=headers
    )
    assert comp_res.status_code == 200
    comp_data = comp_res.json()
    assert comp_data["status"] == "completed"
    assert comp_data["completed_at"] is not None
    assert comp_data["action_taken"] == "Issued Anganwadi session slip"

    # 6. Test Smart Visit Planner
    plan_res = client.post("/api/asha/house-visits/smart-plan", headers=headers)
    assert plan_res.status_code == 200
    plan_data = plan_res.json()
    assert "created_visits" in plan_data
    assert "unnecessary_visits_saved" in plan_data
