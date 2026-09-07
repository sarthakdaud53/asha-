from datetime import date

def test_administer_vaccine_as_asha(client):
    # 1. Login as ASHA worker
    asha_login = client.post(
        "/api/auth/login",
        json={"username": "asha_sunita", "password": "asha123"}
    )
    token = asha_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get children in village
    children_res = client.get("/api/children", headers=headers)
    assert children_res.status_code == 200
    children = children_res.json()
    assert len(children) > 0

    target_child = children[0]
    
    # 3. Get child detailed schedule
    detail_res = client.get(f"/api/children/{target_child['id']}", headers=headers)
    child_detail = detail_res.json()
    pending_recs = [r for r in child_detail["immunizations"] if r["status"] != "administered"]
    assert len(pending_recs) > 0
    target_rec = pending_recs[0]

    # 4. Administer vaccine
    administer_payload = {
        "administered_date": date.today().isoformat(),
        "batch_number": "BATCH-TEST-99",
        "session_site": "Anganwadi Center 1",
        "aefi_reported": False,
        "notes": "Administered smoothly without adverse reaction"
    }

    adm_res = client.post(
        f"/api/immunizations/{target_rec['id']}/administer",
        json=administer_payload,
        headers=headers
    )
    assert adm_res.status_code == 200
    updated_rec = adm_res.json()
    assert updated_rec["status"] == "administered"
    assert updated_rec["batch_number"] == "BATCH-TEST-99"

def test_mcp_card_export(client):
    asha_login = client.post(
        "/api/auth/login",
        json={"username": "asha_sunita", "password": "asha123"}
    )
    token = asha_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    mcp_res = client.get("/api/immunizations/mcp-card/1", headers=headers)
    assert mcp_res.status_code == 200
    card_data = mcp_res.json()
    assert "child" in card_data
    assert "grouped_schedule" in card_data
    assert "metrics" in card_data
