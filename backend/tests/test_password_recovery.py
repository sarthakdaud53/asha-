def test_forgot_password_and_reset_flow(client):
    # 1. Request forgot password token for parent_priya
    req_res = client.post("/api/auth/forgot-password", json={"username_or_phone": "parent_priya"})
    assert req_res.status_code == 200
    data = req_res.json()
    reset_token = data["reset_token"]
    assert reset_token is not None

    # 2. Reset password using valid token
    reset_res = client.post("/api/auth/reset-password", json={
        "token": reset_token,
        "new_password": "brand_new_password_2026"
    })
    assert reset_res.status_code == 200

    # 3. Old password fails
    old_login = client.post("/api/auth/login", json={"username": "parent_priya", "password": "parent123"})
    assert old_login.status_code == 401

    # 4. New password succeeds
    new_login = client.post("/api/auth/login", json={"username": "parent_priya", "password": "brand_new_password_2026"})
    assert new_login.status_code == 200
    assert new_login.json()["full_name"] == "Priya Kumari"

    # Reset back to parent123 for other tests
    req_res2 = client.post("/api/auth/forgot-password", json={"username_or_phone": "parent_priya"})
    token2 = req_res2.json()["reset_token"]
    client.post("/api/auth/reset-password", json={"token": token2, "new_password": "parent123"})

def test_reset_password_with_invalid_token(client):
    res = client.post("/api/auth/reset-password", json={
        "token": "invalid_fake_token_123",
        "new_password": "some_password"
    })
    assert res.status_code == 400

def test_authenticated_change_password(client):
    # Login as Anita
    login_res = client.post("/api/auth/login", json={"username": "parent_anita", "password": "parent123"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Wrong current password -> 400
    fail_res = client.post("/api/auth/change-password", json={
        "current_password": "incorrect_current",
        "new_password": "anita_new_password"
    }, headers=headers)
    assert fail_res.status_code == 400

    # Correct current password -> 200
    ok_res = client.post("/api/auth/change-password", json={
        "current_password": "parent123",
        "new_password": "anita_new_password"
    }, headers=headers)
    assert ok_res.status_code == 200

    # Verify new password login
    new_login = client.post("/api/auth/login", json={"username": "parent_anita", "password": "anita_new_password"})
    assert new_login.status_code == 200

    # Reset back to parent123
    new_token = new_login.json()["access_token"]
    client.post("/api/auth/change-password", json={
        "current_password": "anita_new_password",
        "new_password": "parent123"
    }, headers={"Authorization": f"Bearer {new_token}"})
