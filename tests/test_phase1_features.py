import pytest
import httpx
import uuid
import datetime


@pytest.mark.asyncio
async def test_customer_contact_info(client: httpx.AsyncClient, advisor_headers: dict):
    # 1. Create customer with all contact info
    resp = await client.post("/customers", json={
        "name": "Jane Receptionist-Test",
        "customer_type": "individual",
        "billing_address": "456 Elm St",
        "tax_exempt": False,
        "phone": "+1-555-123-4567",
        "email": "jane.doe@example.com",
        "secondary_phone": "+1-555-987-6543",
        "notes": "Prefers text message updates"
    }, headers=advisor_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["phone"] == "+1-555-123-4567"
    assert data["email"] == "jane.doe@example.com"
    assert data["secondary_phone"] == "+1-555-987-6543"
    assert data["notes"] == "Prefers text message updates"
    cust_id = data["customer_id"]

    # 2. Update customer contact info
    update_resp = await client.put(f"/customers/{cust_id}", json={
        "phone": "+1-555-000-1111",
        "notes": "Updated note: gate code 1234"
    }, headers=advisor_headers)
    assert update_resp.status_code == 200
    updated_data = update_resp.json()
    assert updated_data["phone"] == "+1-555-000-1111"
    assert updated_data["email"] == "jane.doe@example.com"
    assert updated_data["notes"] == "Updated note: gate code 1234"

    # 3. Validation: invalid email format
    bad_email_resp = await client.post("/customers", json={
        "name": "Bad Email User",
        "customer_type": "individual",
        "email": "not-an-email"
    }, headers=advisor_headers)
    assert bad_email_resp.status_code == 422


@pytest.mark.asyncio
async def test_vehicle_license_plate(client: httpx.AsyncClient, advisor_headers: dict):
    # Create customer
    cust_resp = await client.post("/customers", json={
        "name": "Vehicle Owner Plate Test",
        "customer_type": "individual"
    }, headers=advisor_headers)
    cust_id = cust_resp.json()["customer_id"]

    # Create vehicle with license plate
    vin = "1FA6P8CF" + str(uuid.uuid4().hex[:9]).upper()
    veh_resp = await client.post("/vehicles", json={
        "vin": vin,
        "customer_id": cust_id,
        "make": "Toyota",
        "model": "Camry",
        "year": 2022,
        "current_mileage": 15000,
        "license_plate": "7XYZ890"
    }, headers=advisor_headers)
    assert veh_resp.status_code == 201
    veh_data = veh_resp.json()
    assert veh_data["license_plate"] == "7XYZ890"

    # Update license plate
    up_resp = await client.put(f"/vehicles/{vin}", json={
        "license_plate": "8ABC123"
    }, headers=advisor_headers)
    assert up_resp.status_code == 200
    assert up_resp.json()["license_plate"] == "8ABC123"


@pytest.mark.asyncio
async def test_search_endpoints(client: httpx.AsyncClient, advisor_headers: dict):
    # 1. Create a searchable customer
    unique_phone = "555-9988-SEARCH"
    cust_resp = await client.post("/customers", json={
        "name": "Sherlock Holmes UniqueSearch",
        "customer_type": "individual",
        "phone": unique_phone,
        "email": "sherlock@bakerst.com"
    }, headers=advisor_headers)
    assert cust_resp.status_code == 201
    cust_id = cust_resp.json()["customer_id"]

    # 2. Search customer by name
    search_name = await client.get("/customers/search?q=Sherlock", headers=advisor_headers)
    assert search_name.status_code == 200
    results = search_name.json()
    assert len(results) >= 1
    assert any(c["name"] == "Sherlock Holmes UniqueSearch" for c in results)

    # 3. Search customer by phone
    search_phone = await client.get(f"/customers/search?q={unique_phone}", headers=advisor_headers)
    assert search_phone.status_code == 200
    assert any(c["phone"] == unique_phone for c in search_phone.json())

    # 4. Search customer by email
    search_email = await client.get("/customers/search?q=bakerst.com", headers=advisor_headers)
    assert search_email.status_code == 200
    assert any(c["email"] == "sherlock@bakerst.com" for c in search_email.json())

    # 5. Create a searchable vehicle
    unique_vin = "1FA6P8CF" + str(uuid.uuid4().hex[:9]).upper()
    unique_plate = "SHERLK1"
    veh_resp = await client.post("/vehicles", json={
        "vin": unique_vin,
        "customer_id": cust_id,
        "make": "Aston Martin",
        "model": "DB5",
        "year": 1964,
        "license_plate": unique_plate
    }, headers=advisor_headers)
    assert veh_resp.status_code == 201

    # 6. Search vehicle by license plate
    search_plate = await client.get(f"/vehicles/search?q={unique_plate}", headers=advisor_headers)
    assert search_plate.status_code == 200
    assert any(v["license_plate"] == unique_plate for v in search_plate.json())

    # 7. Search vehicle by customer name
    search_veh_by_owner = await client.get("/vehicles/search?q=Sherlock", headers=advisor_headers)
    assert search_veh_by_owner.status_code == 200
    assert any(v["vin"] == unique_vin for v in search_veh_by_owner.json())


@pytest.mark.asyncio
async def test_part_pricing_and_search(client: httpx.AsyncClient, advisor_headers: dict):
    # 1. Create Part with pricing
    part_num = "TEST-BRAKE-" + str(uuid.uuid4().hex[:6]).upper()
    resp = await client.post("/parts", json={
        "name": "Premium Ceramic Brake Pads",
        "part_number": part_num,
        "description": "Front ceramic pads with hardware kit",
        "category": "Brakes",
        "cost_price": 25.00,
        "retail_price": 65.00,
        "quantity_on_hand": 20,
        "is_returnable": True,
        "warranty_required": True
    }, headers=advisor_headers)
    assert resp.status_code == 201
    part_data = resp.json()
    assert part_data["name"] == "Premium Ceramic Brake Pads"
    assert float(part_data["cost_price"]) == 25.00
    assert float(part_data["retail_price"]) == 65.00
    assert float(part_data["markup_percent"]) == 160.00  # (65-25)/25 * 100
    part_id = part_data["part_id"]

    # 2. Search parts by name
    search_part = await client.get("/parts/search?q=Ceramic Brake", headers=advisor_headers)
    assert search_part.status_code == 200
    assert any(p["part_id"] == part_id for p in search_part.json())

    # 3. Search parts by part number
    search_num = await client.get(f"/parts/search?q={part_num}", headers=advisor_headers)
    assert search_num.status_code == 200
    assert any(p["part_number"] == part_num for p in search_num.json())

    # 4. Get single part
    get_part_resp = await client.get(f"/parts/{part_id}", headers=advisor_headers)
    assert get_part_resp.status_code == 200
    assert get_part_resp.json()["name"] == "Premium Ceramic Brake Pads"

    # 5. Update part pricing
    update_resp = await client.put(f"/parts/{part_id}", json={
        "retail_price": 75.00
    }, headers=advisor_headers)
    assert update_resp.status_code == 200
    assert float(update_resp.json()["retail_price"]) == 75.00
    assert float(update_resp.json()["markup_percent"]) == 200.00  # (75-25)/25 * 100


@pytest.mark.asyncio
async def test_invoice_tax_calculation(client: httpx.AsyncClient, manager_headers: dict, advisor_headers: dict):
    # 1. Non-exempt Customer -> Tax Calculated
    cust_resp = await client.post("/customers", json={
        "name": "Tax Paying Customer",
        "customer_type": "individual",
        "tax_exempt": False
    }, headers=advisor_headers)
    cust_id = cust_resp.json()["customer_id"]

    vin = "1FA6P8CF" + str(uuid.uuid4().hex[:9]).upper()
    await client.post("/vehicles", json={
        "vin": vin,
        "customer_id": cust_id,
        "make": "Honda",
        "model": "Civic",
        "year": 2020
    }, headers=advisor_headers)

    quote_resp = await client.post("/quotes", json={
        "customer_id": cust_id,
        "vehicle_id": vin,
        "total_amount": 500.0,
        "valid_until": str(datetime.date.today() + datetime.timedelta(days=30))
    }, headers=advisor_headers)
    quote_id = quote_resp.json()["quote_id"]
    await client.put(f"/quotes/{quote_id}", json={"status": "approved"}, headers=manager_headers)

    wo_resp = await client.post("/work-orders", json={
        "quote_id": quote_id,
        "vehicle_id": vin,
        "customer_id": cust_id,
        "authorized_amount": 500.0,
        "status": "closed"
    }, headers=manager_headers)
    wo_id = wo_resp.json()["work_order_id"]

    inv_resp = await client.post("/invoices", json={
        "work_order_id": wo_id,
        "customer_id": cust_id,
        "amount_due": 500.0
    }, headers=advisor_headers)
    assert inv_resp.status_code == 201
    inv_data = inv_resp.json()
    assert float(inv_data["amount_due"]) == 500.0
    assert float(inv_data["tax_rate"]) == 0.07  # default 7%
    assert float(inv_data["tax_amount"]) == 35.00  # 500 * 0.07
    assert float(inv_data["total_balance"]) == 535.00  # 500 + 35
    inv_id = inv_data["invoice_id"]

    # Pay full with tax
    pay_resp = await client.post("/payments", json={
        "invoice_id": inv_id,
        "amount": 535.00,
        "method": "credit_card",
        "collected_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }, headers=advisor_headers)
    assert pay_resp.status_code == 201

    # Check invoice is now paid
    inv_get = await client.get(f"/invoices/{inv_id}", headers=advisor_headers)
    assert inv_get.json()["status"] == "paid"
    assert float(inv_get.json()["total_balance"]) == 0.00

    # 2. Tax-exempt Customer -> 0 Tax
    cust_exempt_resp = await client.post("/customers", json={
        "name": "Fleet Tax Exempt Corp",
        "customer_type": "fleet",
        "tax_exempt": True
    }, headers=advisor_headers)
    cust_exempt_id = cust_exempt_resp.json()["customer_id"]

    vin2 = "1FA6P8CF" + str(uuid.uuid4().hex[:9]).upper()
    await client.post("/vehicles", json={
        "vin": vin2,
        "customer_id": cust_exempt_id,
        "make": "Ford",
        "model": "Transit",
        "year": 2021
    }, headers=advisor_headers)

    quote2_resp = await client.post("/quotes", json={
        "customer_id": cust_exempt_id,
        "vehicle_id": vin2,
        "total_amount": 1000.0,
        "valid_until": str(datetime.date.today() + datetime.timedelta(days=30))
    }, headers=advisor_headers)
    q2_id = quote2_resp.json()["quote_id"]
    await client.put(f"/quotes/{q2_id}", json={"status": "approved"}, headers=manager_headers)

    wo2_resp = await client.post("/work-orders", json={
        "quote_id": q2_id,
        "vehicle_id": vin2,
        "customer_id": cust_exempt_id,
        "authorized_amount": 1000.0,
        "status": "closed"
    }, headers=manager_headers)
    wo2_id = wo2_resp.json()["work_order_id"]

    inv2_resp = await client.post("/invoices", json={
        "work_order_id": wo2_id,
        "customer_id": cust_exempt_id,
        "amount_due": 1000.0
    }, headers=advisor_headers)
    assert inv2_resp.status_code == 201
    inv2_data = inv2_resp.json()
    assert float(inv2_data["tax_rate"]) == 0.00
    assert float(inv2_data["tax_amount"]) == 0.00
    assert float(inv2_data["total_balance"]) == 1000.00
