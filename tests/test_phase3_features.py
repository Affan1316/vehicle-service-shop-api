import uuid
import datetime
import pytest
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import engine
from app.services import EmailService


def generate_vin() -> str:
    return "1FA6P8CF" + str(uuid.uuid4().hex[:9]).upper()


@pytest.mark.asyncio
async def test_password_reset_flow(
    client: httpx.AsyncClient
):
    # 1. Register a test user
    username = f"reset_user_{uuid.uuid4().hex[:6]}"
    email = f"{username}@example.com"
    reg_resp = await client.post("/auth/register", json={
        "username": username,
        "email": email,
        "password": "InitialPassword123!",
        "role": "customer"
    })
    assert reg_resp.status_code == 201

    # 2. Request password reset
    forgot_resp = await client.post("/auth/forgot-password", json={"email": email})
    assert forgot_resp.status_code == 200

    # 3. Create a known reset token using AuthService directly
    from app.services import AuthService
    async with AsyncSession(engine) as session:
        user_obj, raw_token = await AuthService.request_password_reset(session, email)
        await session.commit()
    assert raw_token is not None

    # 4. Confirm password reset with new password
    reset_resp = await client.post("/auth/reset-password", json={
        "token": raw_token,
        "new_password": "NewSecurePassword456!"
    })
    assert reset_resp.status_code == 200

    # 5. Log in with new password
    login_resp = await client.post("/auth/token", data={
        "username": username,
        "password": "NewSecurePassword456!"
    })
    assert login_resp.status_code == 200
    assert "access_token" in login_resp.json()

    # 6. Reusing same token should fail
    reuse_resp = await client.post("/auth/reset-password", json={
        "token": raw_token,
        "new_password": "AnotherPassword789!"
    })
    assert reuse_resp.status_code == 400


@pytest.mark.asyncio
async def test_admin_password_reset_and_change_password(
    client: httpx.AsyncClient,
    manager_headers: dict
):
    # 1. Register user
    username = f"admin_reset_{uuid.uuid4().hex[:6]}"
    email = f"{username}@example.com"
    reg_resp = await client.post("/auth/register", json={
        "username": username,
        "email": email,
        "password": "TempPassword123!",
        "role": "technician"
    })
    assert reg_resp.status_code == 201
    user_id = reg_resp.json()["user_id"]

    # 2. Manager force password reset
    admin_reset_resp = await client.post(
        f"/auth/users/{user_id}/reset-password",
        json={"new_password": "ManagerAssignedPassword999!"},
        headers=manager_headers
    )
    assert admin_reset_resp.status_code == 200

    # 3. Log in with manager assigned password
    login_resp = await client.post("/auth/token", data={
        "username": username,
        "password": "ManagerAssignedPassword999!"
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {token}"}

    # 4. User self-service change password
    change_resp = await client.post("/auth/change-password", json={
        "current_password": "ManagerAssignedPassword999!",
        "new_password": "UserChosenPassword777!"
    }, headers=user_headers)
    assert change_resp.status_code == 200

    # 5. Verify new password works
    new_login = await client.post("/auth/token", data={
        "username": username,
        "password": "UserChosenPassword777!"
    })
    assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_user_administration(
    client: httpx.AsyncClient,
    manager_headers: dict,
    advisor_headers: dict
):
    # 1. List users (Manager only)
    adv_list = await client.get("/auth/users", headers=advisor_headers)
    assert adv_list.status_code == 403

    mgr_list = await client.get("/auth/users", headers=manager_headers)
    assert mgr_list.status_code == 200
    users = mgr_list.json()
    assert len(users) >= 1

    # 2. Create customer and user, link user to customer
    cust_resp = await client.post("/customers", json={
        "name": "Link Target Customer",
        "customer_type": "individual",
        "tax_exempt": False
    }, headers=manager_headers)
    cust_id = cust_resp.json()["customer_id"]

    username = f"link_user_{uuid.uuid4().hex[:6]}"
    reg_resp = await client.post("/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": "Password123!",
        "role": "customer"
    })
    user_id = reg_resp.json()["user_id"]

    update_resp = await client.put(
        f"/auth/users/{user_id}",
        json={"customer_id": cust_id, "is_active": False},
        headers=manager_headers
    )
    assert update_resp.status_code == 200
    updated_user = update_resp.json()
    assert updated_user["customer_id"] == cust_id
    assert updated_user["is_active"] is False

    # 3. Deactivated user login should fail
    inactive_login = await client.post("/auth/token", data={
        "username": username,
        "password": "Password123!"
    })
    assert inactive_login.status_code == 401


@pytest.mark.asyncio
async def test_email_service_noop_mode():
    # Verify EmailService methods execute cleanly when EMAIL_ENABLED=False
    quote_id = uuid.uuid4()
    wo_id = uuid.uuid4()

    res1 = await EmailService.send_quote_ready("customer@example.com", "John Doe", quote_id, 350.0)
    assert res1 is True

    res2 = await EmailService.send_vehicle_ready("customer@example.com", "John Doe", "2021 Toyota Camry", wo_id)
    assert res2 is True

    res3 = await EmailService.send_appointment_reminder("customer@example.com", "John Doe", "2026-08-20 10:00", "2021 Toyota Camry")
    assert res3 is True

    res4 = await EmailService.send_password_reset("customer@example.com", "johndoe", "dummy-token-xyz")
    assert res4 is True


@pytest.mark.asyncio
async def test_file_upload_download_and_delete(
    client: httpx.AsyncClient,
    manager_headers: dict,
    advisor_headers: dict
):
    # 1. Create work order
    cust_resp = await client.post("/customers", json={
        "name": "File Upload Customer",
        "customer_type": "individual",
        "tax_exempt": True
    }, headers=advisor_headers)
    cust_id = cust_resp.json()["customer_id"]

    vin = generate_vin()
    await client.post("/vehicles", json={
        "vin": vin,
        "customer_id": cust_id,
        "make": "Porsche",
        "model": "911",
        "year": 2023
    }, headers=advisor_headers)

    quote_resp = await client.post("/quotes", json={
        "customer_id": cust_id,
        "vehicle_id": vin,
        "total_amount": 800.0,
        "valid_until": str(datetime.date.today() + datetime.timedelta(days=30))
    }, headers=advisor_headers)
    quote_id = quote_resp.json()["quote_id"]
    await client.put(f"/quotes/{quote_id}", json={"status": "approved"}, headers=manager_headers)

    wo_resp = await client.post("/work-orders", json={
        "quote_id": quote_id,
        "vehicle_id": vin,
        "customer_id": cust_id,
        "authorized_amount": 800.0,
        "status": "active"
    }, headers=manager_headers)
    wo_id = wo_resp.json()["work_order_id"]

    # 2. Upload photo attachment
    fake_image_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    files = {"file": ("inspection_front_bumper.png", fake_image_bytes, "image/png")}
    data = {"description": "Front bumper scratch before repair"}

    upload_resp = await client.post(
        f"/files/work_order/{wo_id}",
        files=files,
        data=data,
        headers=advisor_headers
    )
    assert upload_resp.status_code == 201
    file_info = upload_resp.json()
    file_id = file_info["file_id"]
    assert file_info["original_filename"] == "inspection_front_bumper.png"
    assert file_info["entity_type"] == "work_order"
    assert file_info["entity_id"] == wo_id
    assert file_info["description"] == "Front bumper scratch before repair"

    # 3. List attachments
    list_resp = await client.get(f"/files/work_order/{wo_id}", headers=advisor_headers)
    assert list_resp.status_code == 200
    att_list = list_resp.json()
    assert len(att_list) >= 1
    assert any(a["file_id"] == file_id for a in att_list)

    # 4. Download attachment
    down_resp = await client.get(f"/files/download/{file_id}", headers=advisor_headers)
    assert down_resp.status_code == 200
    assert down_resp.content == fake_image_bytes

    # 5. Delete attachment
    del_resp = await client.delete(f"/files/{file_id}", headers=manager_headers)
    assert del_resp.status_code == 200

    # 6. Verify deleted
    down_deleted = await client.get(f"/files/download/{file_id}", headers=advisor_headers)
    assert down_deleted.status_code == 404


@pytest.mark.asyncio
async def test_file_upload_validation(
    client: httpx.AsyncClient,
    advisor_headers: dict
):
    entity_id = str(uuid.uuid4())

    # 1. Reject invalid file extension
    bad_file = {"file": ("script.exe", b"malicious content", "application/x-msdownload")}
    resp1 = await client.post(f"/files/work_order/{entity_id}", files=bad_file, headers=advisor_headers)
    assert resp1.status_code == 400
    assert "not allowed" in resp1.json()["detail"]

    # 2. Reject invalid entity type
    good_file = {"file": ("photo.jpg", b"valid photo bytes", "image/jpeg")}
    resp2 = await client.post(f"/files/invalid_entity_type/{entity_id}", files=good_file, headers=advisor_headers)
    assert resp2.status_code == 400
    assert "Invalid entity type" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_audit_trail_lifecycle(
    client: httpx.AsyncClient,
    manager_headers: dict,
    advisor_headers: dict
):
    # 1. Create a customer (triggers audit log)
    cust_resp = await client.post("/customers", json={
        "name": "Audit Test Customer",
        "customer_type": "individual",
        "tax_exempt": False
    }, headers=manager_headers)
    cust_id = cust_resp.json()["customer_id"]

    # 2. Update customer (triggers audit log with diff)
    await client.put(f"/customers/{cust_id}", json={
        "phone": "+1-555-888-9999",
        "notes": "VIP Client"
    }, headers=manager_headers)

    # 3. Query entity audit history (Manager only)
    audit_resp = await client.get(f"/audit/customer/{cust_id}", headers=manager_headers)
    assert audit_resp.status_code == 200
    logs = audit_resp.json()
    assert len(logs) >= 2
    actions = [log["action"] for log in logs]
    assert "create" in actions
    assert "update" in actions

    # Verify field changes in update log
    update_log = next(log for log in logs if log["action"] == "update")
    assert update_log["changes"]["phone"] == "+1-555-888-9999"

    # 4. Query recent audit logs
    recent_resp = await client.get("/audit/recent?limit=10", headers=manager_headers)
    assert recent_resp.status_code == 200
    assert len(recent_resp.json()) >= 1
