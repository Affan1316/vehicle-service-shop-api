import pytest
import httpx
import uuid

@pytest.mark.asyncio
async def test_customer_crud_and_rbac(client: httpx.AsyncClient, manager_headers: dict, advisor_headers: dict, customer_headers: dict):
    # 1. Create Customer (success via advisor)
    create_resp = await client.post("/customers", json={
        "name": "Acme Fleet",
        "customer_type": "fleet",
        "billing_address": "123 Main St",
        "tax_exempt": True
    }, headers=advisor_headers)
    assert create_resp.status_code == 201
    cust_data = create_resp.json()
    assert cust_data["name"] == "Acme Fleet"
    assert cust_data["customer_type"] == "fleet"
    assert "customer_id" in cust_data
    cust_id = cust_data["customer_id"]

    # 2. Create Customer (validation error: invalid type)
    bad_resp = await client.post("/customers", json={
        "name": "Invalid Customer",
        "customer_type": "invalid_type",
    }, headers=advisor_headers)
    assert bad_resp.status_code in (400, 422)

    # 3. Create Customer (RBAC error: customer role cannot create customer)
    no_auth_resp = await client.post("/customers", json={
        "name": "Sneaky Customer",
        "customer_type": "individual",
    }, headers=customer_headers)
    assert no_auth_resp.status_code == 403

    # 4. List Customers (success via manager)
    list_resp = await client.get("/customers", headers=manager_headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    # 5. Get Customer Detail
    get_resp = await client.get(f"/customers/{cust_id}", headers=advisor_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Acme Fleet"

    # 6. Get non-existent Customer (404)
    rand_uuid = str(uuid.uuid4())
    get_resp_404 = await client.get(f"/customers/{rand_uuid}", headers=advisor_headers)
    assert get_resp_404.status_code == 404

    # 7. Update Customer (success via advisor)
    update_resp = await client.put(f"/customers/{cust_id}", json={
        "name": "Acme Fleet Updated",
        "tax_exempt": False
    }, headers=advisor_headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Acme Fleet Updated"
    assert update_resp.json()["tax_exempt"] is False

    # 8. Delete Customer (RBAC error via advisor)
    del_adv_resp = await client.delete(f"/customers/{cust_id}", headers=advisor_headers)
    assert del_adv_resp.status_code == 403

    # 9. Delete Customer (success via manager)
    del_resp = await client.delete(f"/customers/{cust_id}", headers=manager_headers)
    assert del_resp.status_code == 200
    assert "deleted successfully" in del_resp.json()["message"]


@pytest.mark.asyncio
async def test_vehicle_crud_and_rbac(client: httpx.AsyncClient, manager_headers: dict, advisor_headers: dict):
    # 1. Create a customer to link the vehicle to
    cust_resp = await client.post("/customers", json={
        "name": "Vehicle Owner",
        "customer_type": "individual"
    }, headers=advisor_headers)
    assert cust_resp.status_code == 201
    cust_id = cust_resp.json()["customer_id"]

    # 2. Create Vehicle (success)
    vin = f"1FA6P8CF0H{uuid.uuid4().hex[:7].upper()}" # 17 chars
    veh_resp = await client.post("/vehicles", json={
        "vin": vin,
        "customer_id": cust_id,
        "make": "Ford",
        "model": "Mustang",
        "year": 2017,
        "current_mileage": 45000
    }, headers=advisor_headers)
    assert veh_resp.status_code == 201
    veh_data = veh_resp.json()
    assert veh_data["vin"] == vin
    assert veh_data["make"] == "Ford"

    # 3. Create Vehicle (non-existent customer id)
    bad_vin = f"1FA6P8CF9H{uuid.uuid4().hex[:7].upper()}"
    bad_veh_resp = await client.post("/vehicles", json={
        "vin": bad_vin,
        "customer_id": str(uuid.uuid4()),
        "make": "Ford",
        "model": "F-150",
        "year": 2020
    }, headers=advisor_headers)
    assert bad_veh_resp.status_code == 400


    # 4. List Vehicles
    list_resp = await client.get("/vehicles", headers=advisor_headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    # 5. Get Vehicle
    get_resp = await client.get(f"/vehicles/{vin}", headers=advisor_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["model"] == "Mustang"

    # 6. Update Vehicle
    update_resp = await client.put(f"/vehicles/{vin}", json={
        "current_mileage": 48000
    }, headers=advisor_headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["current_mileage"] == 48000

    # 7. Delete Vehicle (RBAC error via advisor)
    del_adv_resp = await client.delete(f"/vehicles/{vin}", headers=advisor_headers)
    assert del_adv_resp.status_code == 403

    # 8. Delete Vehicle (success via manager)
    del_resp = await client.delete(f"/vehicles/{vin}", headers=manager_headers)
    assert del_resp.status_code == 200
    assert "deleted successfully" in del_resp.json()["message"]
