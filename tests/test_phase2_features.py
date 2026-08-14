import pytest
import httpx
import uuid
import datetime


def generate_vin() -> str:
    return "1FA6P8CF" + str(uuid.uuid4().hex[:9]).upper()


@pytest.mark.asyncio
async def test_daily_revenue_report(
    client: httpx.AsyncClient,
    manager_headers: dict,
    advisor_headers: dict
):
    # 1. Non-manager access is blocked (RBAC)
    adv_resp = await client.get("/reports/daily-revenue", headers=advisor_headers)
    assert adv_resp.status_code == 403

    # 2. Create customer, vehicle, quote, work order, invoice
    cust_resp = await client.post("/customers", json={
        "name": "Revenue Report Customer",
        "customer_type": "individual",
        "tax_exempt": True
    }, headers=advisor_headers)
    cust_id = cust_resp.json()["customer_id"]

    vin = generate_vin()
    await client.post("/vehicles", json={
        "vin": vin,
        "customer_id": cust_id,
        "make": "Ford",
        "model": "F-150",
        "year": 2022
    }, headers=advisor_headers)

    quote_resp = await client.post("/quotes", json={
        "customer_id": cust_id,
        "vehicle_id": vin,
        "total_amount": 300.0,
        "valid_until": str(datetime.date.today() + datetime.timedelta(days=30))
    }, headers=advisor_headers)
    quote_id = quote_resp.json()["quote_id"]
    await client.put(f"/quotes/{quote_id}", json={"status": "approved"}, headers=manager_headers)

    wo_resp = await client.post("/work-orders", json={
        "quote_id": quote_id,
        "vehicle_id": vin,
        "customer_id": cust_id,
        "authorized_amount": 300.0,
        "status": "closed"
    }, headers=manager_headers)
    wo_id = wo_resp.json()["work_order_id"]

    inv_resp = await client.post("/invoices", json={
        "work_order_id": wo_id,
        "customer_id": cust_id,
        "amount_due": 300.0
    }, headers=advisor_headers)
    inv_id = inv_resp.json()["invoice_id"]

    # 3. Collect two payments on today's date
    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    await client.post("/payments", json={
        "invoice_id": inv_id,
        "amount": 200.0,
        "method": "credit_card",
        "collected_at": now_str
    }, headers=advisor_headers)

    await client.post("/payments", json={
        "invoice_id": inv_id,
        "amount": 100.0,
        "method": "cash",
        "collected_at": now_str
    }, headers=advisor_headers)

    # 4. Fetch daily revenue report
    today_str = datetime.date.today().isoformat()
    rep_resp = await client.get(f"/reports/daily-revenue?date={today_str}", headers=manager_headers)
    assert rep_resp.status_code == 200
    rep_data = rep_resp.json()
    assert float(rep_data["total_revenue"]) >= 300.0
    assert rep_data["invoice_count"] >= 1
    methods = [b["method"] for b in rep_data["breakdown_by_method"]]
    assert "credit_card" in methods
    assert "cash" in methods


@pytest.mark.asyncio
async def test_outstanding_ar_report(
    client: httpx.AsyncClient,
    manager_headers: dict,
    advisor_headers: dict
):
    # 1. Create an unpaid invoice
    cust_resp = await client.post("/customers", json={
        "name": "AR Aging Customer",
        "customer_type": "individual",
        "tax_exempt": True
    }, headers=advisor_headers)
    cust_id = cust_resp.json()["customer_id"]

    vin = generate_vin()
    await client.post("/vehicles", json={
        "vin": vin,
        "customer_id": cust_id,
        "make": "Toyota",
        "model": "Camry",
        "year": 2021
    }, headers=advisor_headers)

    quote_resp = await client.post("/quotes", json={
        "customer_id": cust_id,
        "vehicle_id": vin,
        "total_amount": 750.0,
        "valid_until": str(datetime.date.today() + datetime.timedelta(days=30))
    }, headers=advisor_headers)
    quote_id = quote_resp.json()["quote_id"]
    await client.put(f"/quotes/{quote_id}", json={"status": "approved"}, headers=manager_headers)

    wo_resp = await client.post("/work-orders", json={
        "quote_id": quote_id,
        "vehicle_id": vin,
        "customer_id": cust_id,
        "authorized_amount": 750.0,
        "status": "closed"
    }, headers=manager_headers)
    wo_id = wo_resp.json()["work_order_id"]

    inv_resp = await client.post("/invoices", json={
        "work_order_id": wo_id,
        "customer_id": cust_id,
        "amount_due": 750.0
    }, headers=advisor_headers)
    inv_id = inv_resp.json()["invoice_id"]

    # 2. Fetch Outstanding AR report
    ar_resp = await client.get("/reports/outstanding-ar", headers=manager_headers)
    assert ar_resp.status_code == 200
    ar_data = ar_resp.json()
    assert float(ar_data["total_outstanding"]) >= 750.0
    assert ar_data["invoice_count"] >= 1
    item_ids = [item["invoice_id"] for item in ar_data["items"]]
    assert inv_id in item_ids


@pytest.mark.asyncio
async def test_tech_productivity_report(
    client: httpx.AsyncClient,
    manager_headers: dict,
    advisor_headers: dict
):
    # 1. Create technician with active certification
    tech_resp = await client.post("/technicians", json={
        "name": "Productivity Test Tech",
        "hourly_rate": 45.0
    }, headers=manager_headers)
    tech_id = tech_resp.json()["tech_id"]

    cert_resp = await client.post(f"/technicians/{tech_id}/certifications", json={
        "tech_id": tech_id,
        "cert_type": "ASE Master Certified",
        "expiry_date": str(datetime.date.today() + datetime.timedelta(days=365))
    }, headers=manager_headers)
    assert cert_resp.status_code == 201

    # 2. Create customer, vehicle, quote, work order, line item
    cust_resp = await client.post("/customers", json={
        "name": "Tech Productivity Customer",
        "customer_type": "individual",
        "tax_exempt": True
    }, headers=advisor_headers)
    cust_id = cust_resp.json()["customer_id"]

    vin = generate_vin()
    await client.post("/vehicles", json={
        "vin": vin,
        "customer_id": cust_id,
        "make": "BMW",
        "model": "330i",
        "year": 2020
    }, headers=advisor_headers)

    quote_resp = await client.post("/quotes", json={
        "customer_id": cust_id,
        "vehicle_id": vin,
        "total_amount": 400.0,
        "valid_until": str(datetime.date.today() + datetime.timedelta(days=30))
    }, headers=advisor_headers)
    quote_id = quote_resp.json()["quote_id"]
    await client.put(f"/quotes/{quote_id}", json={"status": "approved"}, headers=manager_headers)

    wo_resp = await client.post("/work-orders", json={
        "quote_id": quote_id,
        "vehicle_id": vin,
        "customer_id": cust_id,
        "authorized_amount": 400.0,
        "status": "active"
    }, headers=manager_headers)
    wo_id = wo_resp.json()["work_order_id"]

    li_resp = await client.post(f"/work-orders/{wo_id}/line-items", json={
        "work_order_id": wo_id,
        "description": "Brake Rotor Replacement",
        "billing_mode": "hourly",
        "price": 200.0,
        "status": "in_progress"
    }, headers=advisor_headers)
    li_id = li_resp.json()["line_item_id"]

    # 3. Log 3.5 hours of labor
    today_str = datetime.date.today().isoformat()
    labor_resp = await client.post(f"/work-orders/{wo_id}/labor-entries", json={
        "tech_id": tech_id,
        "line_item_id": li_id,
        "hours": 3.5,
        "work_date": today_str
    }, headers=manager_headers)
    assert labor_resp.status_code == 201

    # 4. Fetch productivity report
    rep_resp = await client.get(
        f"/reports/tech-productivity?start_date={today_str}&end_date={today_str}",
        headers=manager_headers
    )
    assert rep_resp.status_code == 200
    rep_data = rep_resp.json()
    tech_entries = [t for t in rep_data["technicians"] if t["tech_id"] == tech_id]
    assert len(tech_entries) == 1
    assert float(tech_entries[0]["total_hours"]) == 3.5
    assert float(tech_entries[0]["total_labor_value"]) == 3.5 * 45.0  # 157.50


@pytest.mark.asyncio
async def test_quote_and_invoice_pdf_generation(
    client: httpx.AsyncClient,
    manager_headers: dict,
    advisor_headers: dict
):
    cust_resp = await client.post("/customers", json={
        "name": "PDF Generation Customer",
        "customer_type": "individual",
        "phone": "555-999-8888",
        "email": "pdf.test@example.com",
        "billing_address": "789 Pine Ave",
        "tax_exempt": False
    }, headers=advisor_headers)
    cust_id = cust_resp.json()["customer_id"]

    vin = generate_vin()
    await client.post("/vehicles", json={
        "vin": vin,
        "customer_id": cust_id,
        "make": "Audi",
        "model": "Q5",
        "year": 2023,
        "license_plate": "PDF-TEST"
    }, headers=advisor_headers)

    quote_resp = await client.post("/quotes", json={
        "customer_id": cust_id,
        "vehicle_id": vin,
        "total_amount": 600.0,
        "valid_until": str(datetime.date.today() + datetime.timedelta(days=30))
    }, headers=advisor_headers)
    quote_id = quote_resp.json()["quote_id"]
    await client.put(f"/quotes/{quote_id}", json={"status": "approved"}, headers=manager_headers)

    wo_resp = await client.post("/work-orders", json={
        "quote_id": quote_id,
        "vehicle_id": vin,
        "customer_id": cust_id,
        "authorized_amount": 600.0,
        "status": "closed"
    }, headers=manager_headers)
    wo_id = wo_resp.json()["work_order_id"]

    inv_resp = await client.post("/invoices", json={
        "work_order_id": wo_id,
        "customer_id": cust_id,
        "amount_due": 600.0
    }, headers=advisor_headers)
    inv_id = inv_resp.json()["invoice_id"]

    # 1. Test Quote PDF
    q_pdf_resp = await client.get(f"/quotes/{quote_id}/pdf", headers=advisor_headers)
    assert q_pdf_resp.status_code == 200
    assert q_pdf_resp.headers["content-type"] == "application/pdf"
    assert len(q_pdf_resp.content) > 500
    assert q_pdf_resp.content[:4] == b"%PDF"

    # 2. Test Invoice PDF
    inv_pdf_resp = await client.get(f"/invoices/{inv_id}/pdf", headers=advisor_headers)
    assert inv_pdf_resp.status_code == 200
    assert inv_pdf_resp.headers["content-type"] == "application/pdf"
    assert len(inv_pdf_resp.content) > 500
    assert inv_pdf_resp.content[:4] == b"%PDF"


@pytest.mark.asyncio
async def test_deposit_and_payment_refunds(
    client: httpx.AsyncClient,
    manager_headers: dict,
    advisor_headers: dict
):
    cust_resp = await client.post("/customers", json={
        "name": "Refund Test Customer",
        "customer_type": "individual",
        "tax_exempt": True
    }, headers=advisor_headers)
    cust_id = cust_resp.json()["customer_id"]

    vin = generate_vin()
    await client.post("/vehicles", json={
        "vin": vin,
        "customer_id": cust_id,
        "make": "Subaru",
        "model": "Outback",
        "year": 2020
    }, headers=advisor_headers)

    quote_resp = await client.post("/quotes", json={
        "customer_id": cust_id,
        "vehicle_id": vin,
        "total_amount": 500.0,
        "valid_until": str(datetime.date.today() + datetime.timedelta(days=30))
    }, headers=advisor_headers)
    quote_id = quote_resp.json()["quote_id"]

    # 1. Deposit Refund
    dep_resp = await client.post("/deposits", json={
        "quote_id": quote_id,
        "customer_id": cust_id,
        "amount": 200.0
    }, headers=advisor_headers)
    dep_id = dep_resp.json()["deposit_id"]

    dep_ref_resp = await client.post(f"/deposits/{dep_id}/refund", json={
        "amount": 200.0,
        "reason": "Customer cancelled scheduled service"
    }, headers=manager_headers)
    assert dep_ref_resp.status_code == 200
    assert dep_ref_resp.json()["status"] == "refunded"
    assert float(dep_ref_resp.json()["refund_amount"]) == 200.0

    # Duplicate refund attempt should fail
    dup_ref = await client.post(f"/deposits/{dep_id}/refund", json={
        "amount": 200.0,
        "reason": "Repeat refund attempt"
    }, headers=manager_headers)
    assert dup_ref.status_code == 400

    # 2. Payment Refund & Invoice Status Revert
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
    inv_id = inv_resp.json()["invoice_id"]

    pay_resp = await client.post("/payments", json={
        "invoice_id": inv_id,
        "amount": 500.0,
        "method": "credit_card",
        "collected_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }, headers=advisor_headers)
    pay_id = pay_resp.json()["payment_id"]

    # Invoice is paid
    inv_check = await client.get(f"/invoices/{inv_id}", headers=advisor_headers)
    assert inv_check.json()["status"] == "paid"

    # Issue partial refund of $100
    pay_ref_resp = await client.post(f"/payments/{pay_id}/refund", json={
        "amount": 100.0,
        "reason": "Disputed diagnostic fee credit"
    }, headers=manager_headers)
    assert pay_ref_resp.status_code == 200
    assert float(pay_ref_resp.json()["refund_amount"]) == 100.0

    # Invoice should have reverted back to 'issued' since balance is now > 0
    inv_after = await client.get(f"/invoices/{inv_id}", headers=advisor_headers)
    assert inv_after.json()["status"] == "issued"


@pytest.mark.asyncio
async def test_vehicle_service_history_endpoint(
    client: httpx.AsyncClient,
    manager_headers: dict,
    advisor_headers: dict
):
    cust_resp = await client.post("/customers", json={
        "name": "Service History Fleet",
        "customer_type": "fleet",
        "tax_exempt": True
    }, headers=advisor_headers)
    cust_id = cust_resp.json()["customer_id"]

    vin = generate_vin()
    await client.post("/vehicles", json={
        "vin": vin,
        "customer_id": cust_id,
        "make": "Mercedes-Benz",
        "model": "Sprinter",
        "year": 2022,
        "license_plate": "FLT-001"
    }, headers=advisor_headers)

    # First Visit / Work Order
    q1 = await client.post("/quotes", json={
        "customer_id": cust_id,
        "vehicle_id": vin,
        "total_amount": 250.0,
        "valid_until": str(datetime.date.today() + datetime.timedelta(days=30))
    }, headers=advisor_headers)
    q1_id = q1.json()["quote_id"]
    await client.put(f"/quotes/{q1_id}", json={"status": "approved"}, headers=manager_headers)

    wo1 = await client.post("/work-orders", json={
        "quote_id": q1_id,
        "vehicle_id": vin,
        "customer_id": cust_id,
        "authorized_amount": 250.0,
        "status": "closed"
    }, headers=manager_headers)
    wo1_id = wo1.json()["work_order_id"]

    await client.post(f"/work-orders/{wo1_id}/line-items", json={
        "work_order_id": wo1_id,
        "description": "Oil & Filter Service",
        "billing_mode": "flat_rate",
        "price": 250.0,
        "status": "completed"
    }, headers=advisor_headers)

    # Second Visit / Work Order
    q2 = await client.post("/quotes", json={
        "customer_id": cust_id,
        "vehicle_id": vin,
        "total_amount": 400.0,
        "valid_until": str(datetime.date.today() + datetime.timedelta(days=30))
    }, headers=advisor_headers)
    q2_id = q2.json()["quote_id"]
    await client.put(f"/quotes/{q2_id}", json={"status": "approved"}, headers=manager_headers)

    wo2 = await client.post("/work-orders", json={
        "quote_id": q2_id,
        "vehicle_id": vin,
        "customer_id": cust_id,
        "authorized_amount": 400.0,
        "status": "active"
    }, headers=manager_headers)
    wo2_id = wo2.json()["work_order_id"]

    await client.post(f"/work-orders/{wo2_id}/line-items", json={
        "work_order_id": wo2_id,
        "description": "Front Brake Pads",
        "billing_mode": "flat_rate",
        "price": 400.0,
        "status": "in_progress"
    }, headers=advisor_headers)

    # Fetch vehicle service history
    hist_resp = await client.get(f"/vehicles/{vin}/service-history", headers=advisor_headers)
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()
    assert hist_data["vin"] == vin
    assert hist_data["make"] == "Mercedes-Benz"
    assert hist_data["total_visits"] == 2
    assert len(hist_data["history"]) == 2
    descriptions = [li["description"] for entry in hist_data["history"] for li in entry["line_items"]]
    assert "Oil & Filter Service" in descriptions
    assert "Front Brake Pads" in descriptions


@pytest.mark.asyncio
async def test_canned_service_catalog_and_apply(
    client: httpx.AsyncClient,
    manager_headers: dict,
    advisor_headers: dict
):
    # 1. Create canned service template (Manager only)
    create_resp = await client.post("/service-menu", json={
        "name": "Full Synthetic Oil Change Package",
        "description": "Up to 5 quarts full synthetic oil, premium filter, multi-point check",
        "category": "Maintenance",
        "billing_mode": "flat_rate",
        "default_price": 89.99,
        "estimated_hours": 0.75,
        "is_active": True
    }, headers=manager_headers)
    assert create_resp.status_code == 201
    svc_data = create_resp.json()
    svc_id = svc_data["service_id"]
    assert svc_data["name"] == "Full Synthetic Oil Change Package"
    assert float(svc_data["default_price"]) == 89.99

    # 2. List service menu
    menu_resp = await client.get("/service-menu", headers=advisor_headers)
    assert menu_resp.status_code == 200
    menu_items = menu_resp.json()
    assert any(item["service_id"] == svc_id for item in menu_items)

    # 3. Update canned service
    upd_resp = await client.put(f"/service-menu/{svc_id}", json={
        "default_price": 94.99
    }, headers=manager_headers)
    assert upd_resp.status_code == 200
    assert float(upd_resp.json()["default_price"]) == 94.99

    # 4. Apply canned service to a work order
    cust_resp = await client.post("/customers", json={
        "name": "Canned Service Customer",
        "customer_type": "individual",
        "tax_exempt": True
    }, headers=advisor_headers)
    cust_id = cust_resp.json()["customer_id"]

    vin = generate_vin()
    await client.post("/vehicles", json={
        "vin": vin,
        "customer_id": cust_id,
        "make": "Honda",
        "model": "Accord",
        "year": 2019
    }, headers=advisor_headers)

    quote_resp = await client.post("/quotes", json={
        "customer_id": cust_id,
        "vehicle_id": vin,
        "total_amount": 100.0,
        "valid_until": str(datetime.date.today() + datetime.timedelta(days=30))
    }, headers=advisor_headers)
    quote_id = quote_resp.json()["quote_id"]
    await client.put(f"/quotes/{quote_id}", json={"status": "approved"}, headers=manager_headers)

    wo_resp = await client.post("/work-orders", json={
        "quote_id": quote_id,
        "vehicle_id": vin,
        "customer_id": cust_id,
        "authorized_amount": 100.0,
        "status": "active"
    }, headers=manager_headers)
    wo_id = wo_resp.json()["work_order_id"]

    apply_resp = await client.post(
        f"/work-orders/{wo_id}/apply-service/{svc_id}",
        headers=advisor_headers
    )
    assert apply_resp.status_code == 201
    li_data = apply_resp.json()
    assert "Full Synthetic Oil Change Package" in li_data["description"]
    assert li_data["billing_mode"] == "flat_rate"
    assert float(li_data["price"]) == 94.99
    assert li_data["status"] == "not_started"
