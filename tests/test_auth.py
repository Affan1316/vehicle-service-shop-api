import pytest
import httpx

@pytest.mark.asyncio
async def test_register_user_success(client: httpx.AsyncClient):
    resp = await client.post("/auth/register", json={
        "username": "test_newuser",
        "email": "newuser@test.com",
        "password": "testpassword",
        "role": "customer"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "test_newuser"
    assert data["email"] == "newuser@test.com"
    assert "user_id" in data

@pytest.mark.asyncio
async def test_register_user_duplicate(client: httpx.AsyncClient):
    payload = {
        "username": "test_dupuser",
        "email": "dupuser@test.com",
        "password": "testpassword",
        "role": "customer"
    }
    # Register once
    resp1 = await client.post("/auth/register", json=payload)
    assert resp1.status_code == 201
    
    # Register twice
    resp2 = await client.post("/auth/register", json=payload)
    assert resp2.status_code == 400
    assert resp2.json()["detail"] == "Username or email already registered."

@pytest.mark.asyncio
async def test_login_success_and_refresh(client: httpx.AsyncClient):
    # 1. Register user
    await client.post("/auth/register", json={
        "username": "test_loginuser",
        "email": "loginuser@test.com",
        "password": "loginpassword123",
        "role": "manager"
    })

    # 2. Login to get token
    login_resp = await client.post("/auth/token", data={
        "username": "test_loginuser",
        "password": "loginpassword123"
    })
    assert login_resp.status_code == 200
    token_data = login_resp.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    assert token_data["token_type"] == "bearer"

    # 3. Test /auth/me profile route
    headers = {"Authorization": f"Bearer {token_data['access_token']}"}
    me_resp = await client.get("/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "test_loginuser"

    # 4. Wait for 1.1 seconds so the JWT expiration second ticks over, guaranteeing a new signature
    import asyncio
    await asyncio.sleep(1.1)

    # 5. Use refresh token to get a new pair
    refresh_resp = await client.post("/auth/refresh", json={
        "refresh_token": token_data["refresh_token"]
    })
    assert refresh_resp.status_code == 200
    new_token_data = refresh_resp.json()
    assert "access_token" in new_token_data
    assert "refresh_token" in new_token_data
    assert new_token_data["access_token"] != token_data["access_token"]

@pytest.mark.asyncio
async def test_login_invalid_credentials(client: httpx.AsyncClient):
    login_resp = await client.post("/auth/token", data={
        "username": "test_nonexistent",
        "password": "wrongpassword"
    })
    assert login_resp.status_code == 401
    assert login_resp.json()["detail"] == "Incorrect username or password"
