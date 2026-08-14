import pytest
import httpx

@pytest.mark.asyncio
async def test_unauthenticated_request(client: httpx.AsyncClient):
    resp = await client.get("/technicians")
    assert resp.status_code == 401
    assert "detail" in resp.json()

@pytest.mark.asyncio
async def test_unauthorized_role_request(client: httpx.AsyncClient):
    # 1. Register customer
    await client.post("/auth/register", json={
        "username": "test_cust_rbac",
        "email": "cust_rbac@test.com",
        "password": "custpassword",
        "role": "customer"
    })

    # 2. Get login token
    login_resp = await client.post("/auth/token", data={
        "username": "test_cust_rbac",
        "password": "custpassword"
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Customer tries to create a technician (should get 403)
    resp = await client.post("/technicians", json={
        "name": "Should Fail Tech",
        "hourly_rate": 35.0
    }, headers=headers)
    assert resp.status_code == 403

@pytest.mark.asyncio
async def test_authorized_role_request(client: httpx.AsyncClient):
    # 1. Register manager
    await client.post("/auth/register", json={
        "username": "test_mgr_rbac",
        "email": "mgr_rbac@test.com",
        "password": "mgrpassword",
        "role": "manager"
    })

    # 2. Get login token
    login_resp = await client.post("/auth/token", data={
        "username": "test_mgr_rbac",
        "password": "mgrpassword"
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Manager creates technician (should succeed)
    resp = await client.post("/technicians", json={
        "name": "Succeeding Tech",
        "hourly_rate": 45.0
    }, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["name"] == "Succeeding Tech"
