import pytest
import httpx
import uuid
import datetime
import random
import string

def generate_vin() -> str:
    return "1FA6P8CF" + "".join(random.choices(string.ascii_uppercase + string.digits, k=9))

@pytest.mark.asyncio
async def test_appointment_lifecycle(client: httpx.AsyncClient, manager_headers: dict, advisor_headers: dict):
    # 1. Create a customer & vehicle first
    cust_resp = await client.post("/customers", json={
        "name": "Appt Customer",
        "customer_type": "individual"
    }, headers=advisor_headers)
    assert cust_resp.status_code == 201
    cust_id = cust_resp.json()["customer_id"]

    vin = generate_vin()
    veh_resp = await client.post("/vehicles", json={
        "vin": vin,
        "customer_id": cust_id,
        "make": "Honda",
        "model": "Civic",
        "year": 2018
    }, headers=advisor_headers)
    assert veh_resp.status_code == 201

    # 2. Create Appointment (success)
    appt_resp = await client.post("/appointments", json={
        "customer_id": cust_id,
        "vehicle_id": vin,
        "requested_date": str(datetime.date.today() + datetime.timedelta(days=1)),
        "status": "requested"
    }, headers=advisor_headers)
    assert appt_resp.status_code == 201
    appt_data = appt_resp.json()
    assert appt_data["status"] == "requested"
    appt_id = appt_data["appointment_id"]

    # 3. Create Appointment with invalid customer (400)
    bad_appt_resp = await client.post("/appointments", json={
        "customer_id": str(uuid.uuid4()),
        "vehicle_id": vin,
        "requested_date": str(datetime.date.today()),
        "status": "requested"
    }, headers=advisor_headers)
    assert bad_appt_resp.status_code == 400

    # 4. List Appointments
    list_resp = await client.get("/appointments", headers=advisor_headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    # 5. Update Appointment (confirm status & date)
    confirm_date = str(datetime.date.today() + datetime.timedelta(days=1))
    update_resp = await client.put(f"/appointments/{appt_id}", json={
        "confirmed_date": confirm_date,
        "status": "confirmed"
    }, headers=advisor_headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "confirmed"
    assert update_resp.json()["confirmed_date"] == confirm_date


@pytest.mark.asyncio
async def test_visit_lifecycle(client: httpx.AsyncClient, manager_headers: dict, advisor_headers: dict):
    # 1. Create a customer & vehicle
    cust_resp = await client.post("/customers", json={
        "name": "Visit Customer",
        "customer_type": "individual"
    }, headers=advisor_headers)
    assert cust_resp.status_code == 201
    cust_id = cust_resp.json()["customer_id"]

    vin = generate_vin()
    veh_resp = await client.post("/vehicles", json={
        "vin": vin,
        "customer_id": cust_id,
        "make": "Toyota",
        "model": "Prius",
        "year": 2015
    }, headers=advisor_headers)
    assert veh_resp.status_code == 201

    # 2. Create Visit (success)
    visit_resp = await client.post("/visits", json={
        "customer_id": cust_id,
        "vehicle_id": vin
    }, headers=advisor_headers)
    assert visit_resp.status_code == 201
    visit_data = visit_resp.json()
    assert visit_data["status"] == "checked_in"
    assert visit_data["is_active"] is True
    visit_id = visit_data["visit_id"]

    # 3. Create Visit with invalid vehicle (400)
    bad_visit_resp = await client.post("/visits", json={
        "customer_id": cust_id,
        "vehicle_id": "INVALIDVIN1234567"
    }, headers=advisor_headers)
    assert bad_visit_resp.status_code == 400

    # 4. List Visits
    list_resp = await client.get("/visits", headers=advisor_headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    # 5. Invalid transition: checked_in -> completed directly by setting checked_out_at (400)
    checkout_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
    bad_transition_resp = await client.put(f"/visits/{visit_id}", json={
        "checked_out_at": checkout_time
    }, headers=advisor_headers)
    assert bad_transition_resp.status_code == 400

    # 6. Valid transition part 1: checked_in -> awaiting_quote
    transition_resp1 = await client.put(f"/visits/{visit_id}", json={
        "status": "awaiting_quote"
    }, headers=advisor_headers)
    assert transition_resp1.status_code == 200
    assert transition_resp1.json()["status"] == "awaiting_quote"

    # 7. Valid transition part 2: awaiting_quote -> completed via checked_out_at (success)
    transition_resp2 = await client.put(f"/visits/{visit_id}", json={
        "checked_out_at": checkout_time
    }, headers=advisor_headers)
    assert transition_resp2.status_code == 200
    assert transition_resp2.json()["status"] == "completed"
    assert transition_resp2.json()["is_active"] is False
