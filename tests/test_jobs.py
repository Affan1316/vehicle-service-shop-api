import pytest
import httpx
import uuid
import datetime
import random
import string

def generate_vin() -> str:
    return "1FA6P8CF" + "".join(random.choices(string.ascii_uppercase + string.digits, k=9))

@pytest.mark.asyncio
async def test_work_order_and_line_item_lifecycle(client: httpx.AsyncClient, manager_headers: dict, advisor_headers: dict):
    # 1. Create a customer & vehicle
    cust_resp = await client.post("/customers", json={
        "name": "Jobs Customer",
        "customer_type": "individual"
    }, headers=advisor_headers)
    assert cust_resp.status_code == 201
    cust_id = cust_resp.json()["customer_id"]

    vin = generate_vin()
    veh_resp = await client.post("/vehicles", json={
        "vin": vin,
        "customer_id": cust_id,
        "make": "Chevy",
        "model": "Volt",
        "year": 2016
    }, headers=advisor_headers)
    assert veh_resp.status_code == 201

    # 2. Create a Quote (required for WorkOrder creation)
    quote_resp = await client.post("/quotes", json={
        "customer_id": cust_id,
        "vehicle_id": vin,
        "total_amount": 500.0,
        "valid_until": str(datetime.date.today() + datetime.timedelta(days=30))
    }, headers=advisor_headers)
    assert quote_resp.status_code == 201
    quote_id = quote_resp.json()["quote_id"]

    # 3. Create WorkOrder (success)
    wo_resp = await client.post("/work-orders", json={
        "quote_id": quote_id,
        "vehicle_id": vin,
        "customer_id": cust_id,
        "authorized_amount": 550.0,
        "status": "created"
    }, headers=advisor_headers)
    assert wo_resp.status_code == 201
    wo_data = wo_resp.json()
    assert wo_data["status"] == "created"
    assert float(wo_data["authorized_amount"]) == 550.0
    wo_id = wo_data["work_order_id"]

    # 4. List WorkOrders
    list_resp = await client.get("/work-orders", headers=advisor_headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    # 5. Get WorkOrder Detail
    get_resp = await client.get(f"/work-orders/{wo_id}", headers=advisor_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["work_order_id"] == wo_id

    # 6. Update WorkOrder (change status)
    update_resp = await client.put(f"/work-orders/{wo_id}", json={
        "status": "active"
    }, headers=advisor_headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "active"

    # 7. Create Line Item on WorkOrder (success)
    li_resp = await client.post(f"/work-orders/{wo_id}/line-items", json={
        "work_order_id": wo_id,
        "description": "Engine Oil Change",
        "billing_mode": "flat_rate",
        "price": 60.0,
        "status": "not_started"
    }, headers=advisor_headers)
    assert li_resp.status_code == 201
    li_data = li_resp.json()
    assert li_data["description"] == "Engine Oil Change"
    assert float(li_data["price"]) == 60.0
    li_id = li_data["line_item_id"]

    # 8. Update Line Item
    li_update_resp = await client.put(f"/line-items/{li_id}", json={
        "status": "in_progress",
        "price": 65.0
    }, headers=advisor_headers)
    assert li_update_resp.status_code == 200
    assert li_update_resp.json()["status"] == "in_progress"
    assert float(li_update_resp.json()["price"]) == 65.0
