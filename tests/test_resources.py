import pytest
import httpx

@pytest.mark.asyncio
async def test_create_technician_success(client: httpx.AsyncClient, manager_headers: dict):
    resp = await client.post("/technicians", json={
        "name": "John Doe",
        "hourly_rate": 40.0
    }, headers=manager_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "John Doe"
    assert float(data["hourly_rate"]) == 40.0
    assert "tech_id" in data

@pytest.mark.asyncio
async def test_create_technician_duplicate_error(client: httpx.AsyncClient, manager_headers: dict):
    import uuid
    tech_id = str(uuid.uuid4())
    # First creation
    resp1 = await client.post("/technicians", json={
        "tech_id": tech_id,
        "name": "Jane Smith",
        "hourly_rate": 50.0
    }, headers=manager_headers)
    assert resp1.status_code == 201

    # Duplicate creation with same tech_id
    resp2 = await client.post("/technicians", json={
        "tech_id": tech_id,
        "name": "Jane Smith 2",
        "hourly_rate": 50.0
    }, headers=manager_headers)
    assert resp2.status_code == 400
    assert "already exists" in resp2.json()["detail"]

@pytest.mark.asyncio
async def test_list_technicians(client: httpx.AsyncClient, manager_headers: dict, technician_headers: dict, customer_headers: dict):
    # Create a technician first
    await client.post("/technicians", json={
        "name": "Bob Smith",
        "hourly_rate": 45.0
    }, headers=manager_headers)

    # Manager can list
    resp_mgr = await client.get("/technicians", headers=manager_headers)
    assert resp_mgr.status_code == 200
    assert resp_mgr.json()["total"] >= 1

    # Technician can list
    resp_tech = await client.get("/technicians", headers=technician_headers)
    assert resp_tech.status_code == 200

    # Customer cannot list
    resp_cust = await client.get("/technicians", headers=customer_headers)
    assert resp_cust.status_code == 403

@pytest.mark.asyncio
async def test_create_bay_success(client: httpx.AsyncClient, manager_headers: dict):
    resp = await client.post("/bays", json={
        "bay_type": "standard",
        "status": "available"
    }, headers=manager_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["bay_type"] == "standard"
    assert data["status"] == "available"
    assert "bay_id" in data

@pytest.mark.asyncio
async def test_list_bays(client: httpx.AsyncClient, manager_headers: dict, advisor_headers: dict, customer_headers: dict):
    # Create a bay
    await client.post("/bays", json={
        "bay_type": "diagnostic",
        "status": "available"
    }, headers=manager_headers)

    # Advisor can list
    resp_adv = await client.get("/bays", headers=advisor_headers)
    assert resp_adv.status_code == 200
    assert resp_adv.json()["total"] >= 1

    # Customer cannot list
    resp_cust = await client.get("/bays", headers=customer_headers)
    assert resp_cust.status_code == 403
