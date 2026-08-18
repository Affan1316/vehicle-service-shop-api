import pytest
import httpx
import uuid
import datetime
import random
import string

def generate_vin() -> str:
    return "1FA6P8CF" + "".join(random.choices(string.ascii_uppercase + string.digits, k=9))

@pytest.mark.asyncio
async def test_billing_and_financials_lifecycle(client: httpx.AsyncClient, manager_headers: dict, advisor_headers: dict):
    # 1. Create customer & vehicle
    cust_resp = await client.post("/customers", json={
        "name": "Billing Customer",
        "customer_type": "individual"
    }, headers=advisor_headers)
    assert cust_resp.status_code == 201
    cust_id = cust_resp.json()["customer_id"]

    vin = generate_vin()
    veh_resp = await client.post("/vehicles", json={
        "vin": vin,
        "customer_id": cust_id,
        "make": "Ford",
        "model": "Explorer",
        "year": 2019
    }, headers=advisor_headers)
    assert veh_resp.status_code == 201

    # 2. Quote: Create, List, Update
    quote_resp = await client.post("/quotes", json={
        "customer_id": cust_id,
        "vehicle_id": vin,
        "total_amount": 1000.0,
        "valid_until": str(datetime.date.today() + datetime.timedelta(days=30))
    }, headers=advisor_headers)
    assert quote_resp.status_code == 201
    quote_id = quote_resp.json()["quote_id"]

    q_list_resp = await client.get("/quotes", headers=advisor_headers)
    assert q_list_resp.status_code == 200
    assert q_list_resp.json()["total"] >= 1

    q_update_resp = await client.put(f"/quotes/{quote_id}", json={
        "status": "approved"
    }, headers=manager_headers)
    assert q_update_resp.status_code == 200
    assert q_update_resp.json()["status"] == "approved"


    # 3. Work Order (required to generate Invoice)
    wo_resp = await client.post("/work-orders", json={
        "quote_id": quote_id,
        "vehicle_id": vin,
        "customer_id": cust_id,
        "authorized_amount": 1000.0,
        "status": "closed"
    }, headers=advisor_headers)
    assert wo_resp.status_code == 201
    wo_id = wo_resp.json()["work_order_id"]


    # 4. Invoice: Create, List, Get, Update
    inv_resp = await client.post("/invoices", json={
        "work_order_id": wo_id,
        "customer_id": cust_id,
        "amount_due": 1000.0,
        "status": "issued",
        "issued_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }, headers=advisor_headers)
    assert inv_resp.status_code == 201
    inv_id = inv_resp.json()["invoice_id"]
    assert float(inv_resp.json()["amount_due"]) == 1000.0

    inv_list_resp = await client.get("/invoices", headers=advisor_headers)
    assert inv_list_resp.status_code == 200
    assert inv_list_resp.json()["total"] >= 1

    inv_get_resp = await client.get(f"/invoices/{inv_id}", headers=advisor_headers)
    assert inv_get_resp.status_code == 200
    assert inv_get_resp.json()["invoice_id"] == inv_id

    inv_update_resp = await client.put(f"/invoices/{inv_id}", json={
        "status": "disputed"
    }, headers=advisor_headers)
    assert inv_update_resp.status_code == 200
    assert inv_update_resp.json()["status"] == "disputed"

    # 5. Deposit: Create
    dep_resp = await client.post("/deposits", json={
        "quote_id": quote_id,
        "customer_id": cust_id,
        "work_order_id": wo_id,
        "amount": 250.0,
        "status": "collected",
        "collected_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }, headers=advisor_headers)
    assert dep_resp.status_code == 201
    assert float(dep_resp.json()["amount"]) == 250.0

    # 6. Payment: Create
    pay_resp = await client.post("/payments", json={
        "invoice_id": inv_id,
        "amount": 750.0,
        "method": "credit_card",
        "collected_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }, headers=advisor_headers)
    assert pay_resp.status_code == 201
    assert float(pay_resp.json()["amount"]) == 750.0
