import pytest
import httpx

@pytest.mark.asyncio
async def test_paginated_envelope_structure(client: httpx.AsyncClient):
    # 1. Register manager
    await client.post("/auth/register", json={
        "username": "test_pag_user",
        "email": "pag_user@test.com",
        "password": "pagpassword",
        "role": "manager"
    })

    # 2. Get login token
    login_resp = await client.post("/auth/token", data={
        "username": "test_pag_user",
        "password": "pagpassword"
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Call paginated endpoint
    resp = await client.get("/bays?limit=2&offset=1", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert "items" in data
    assert data["limit"] == 2
    assert data["offset"] == 1
    assert isinstance(data["items"], list)

@pytest.mark.asyncio
async def test_pagination_boundaries(client: httpx.AsyncClient):
    # 1. Register manager
    await client.post("/auth/register", json={
        "username": "test_pag_user2",
        "email": "pag_user2@test.com",
        "password": "pagpassword",
        "role": "manager"
    })

    # 2. Get login token
    login_resp = await client.post("/auth/token", data={
        "username": "test_pag_user2",
        "password": "pagpassword"
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Call paginated endpoint with valid limit
    resp = await client.get("/bays?limit=5", headers=headers)
    assert resp.status_code == 200
    # Expecting Pydantic validator to raise error or limit to be capped at 100 via ge=1, le=100
    # Wait, our Query setting was ge=1, le=100.
    # So a limit of 500 should return a 422 validation error!
    # Let's check that. Yes, Query(20, ge=1, le=100) throws a 422 if limit=500.
    # Let's call with limit=500 and verify it returns 422.
    # And call with limit=0 (which is ge=1) and verify it returns 422.
    resp_large = await client.get("/bays?limit=500", headers=headers)
    assert resp_large.status_code == 422

    resp_small = await client.get("/bays?limit=0", headers=headers)
    assert resp_small.status_code == 422
