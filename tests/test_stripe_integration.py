import pytest
import httpx
import uuid
import datetime
from unittest.mock import patch, MagicMock
from app.config import settings


def generate_vin() -> str:
    return "1FA6P8CF" + str(uuid.uuid4().hex[:9]).upper()


async def create_test_invoice(
    client: httpx.AsyncClient,
    advisor_headers: dict,
    manager_headers: dict,
    amount: float = 250.0,
    customer_email: str = "customer@example.com"
) -> tuple[str, str, str]:
    """Helper to create Customer, Vehicle, Quote, WorkOrder, and Invoice."""
    cust_resp = await client.post("/customers", json={
        "name": "Stripe Test Customer",
        "customer_type": "individual",
        "email": customer_email,
        "tax_exempt": True
    }, headers=advisor_headers)
    cust_id = cust_resp.json()["customer_id"]

    vin = generate_vin()
    await client.post("/vehicles", json={
        "vin": vin,
        "customer_id": cust_id,
        "make": "Toyota",
        "model": "RAV4",
        "year": 2023
    }, headers=advisor_headers)

    quote_resp = await client.post("/quotes", json={
        "customer_id": cust_id,
        "vehicle_id": vin,
        "total_amount": amount,
        "valid_until": str(datetime.date.today() + datetime.timedelta(days=30))
    }, headers=advisor_headers)
    quote_id = quote_resp.json()["quote_id"]
    await client.put(f"/quotes/{quote_id}", json={"status": "approved"}, headers=manager_headers)

    wo_resp = await client.post("/work-orders", json={
        "quote_id": quote_id,
        "vehicle_id": vin,
        "customer_id": cust_id,
        "authorized_amount": amount,
        "status": "closed"
    }, headers=manager_headers)
    wo_id = wo_resp.json()["work_order_id"]

    inv_resp = await client.post("/invoices", json={
        "work_order_id": wo_id,
        "customer_id": cust_id,
        "amount_due": amount
    }, headers=advisor_headers)
    inv_id = inv_resp.json()["invoice_id"]

    return cust_id, vin, inv_id


@pytest.mark.asyncio
async def test_stripe_checkout_disabled_by_default(
    client: httpx.AsyncClient,
    advisor_headers: dict,
    manager_headers: dict
):
    """When STRIPE_ENABLED is False, /invoices/{id}/pay returns 503."""
    _, _, inv_id = await create_test_invoice(client, advisor_headers, manager_headers, amount=200.0)

    # Ensure Stripe is disabled
    with patch.object(settings, "STRIPE_ENABLED", False):
        resp = await client.post(f"/invoices/{inv_id}/pay", json={}, headers=advisor_headers)
        assert resp.status_code == 503
        assert "not enabled" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_stripe_checkout_session_creation(
    client: httpx.AsyncClient,
    advisor_headers: dict,
    manager_headers: dict
):
    """When STRIPE_ENABLED is True, checkout session is created and returns URL."""
    _, _, inv_id = await create_test_invoice(client, advisor_headers, manager_headers, amount=175.50)

    mock_session = MagicMock()
    mock_session.id = "cs_test_mock_123456"
    mock_session.url = "https://checkout.stripe.com/pay/cs_test_mock_123456"

    mock_customer = MagicMock()
    mock_customer.id = "cus_test_mock_98765"

    with patch.object(settings, "STRIPE_ENABLED", True), \
         patch.object(settings, "STRIPE_SECRET_KEY", "sk_test_mock"), \
         patch("stripe.Customer.create", return_value=mock_customer), \
         patch("stripe.checkout.Session.create", return_value=mock_session) as mock_create:

        resp = await client.post(
            f"/invoices/{inv_id}/pay",
            json={
                "success_url": "http://localhost:3000/success",
                "cancel_url": "http://localhost:3000/cancel"
            },
            headers=advisor_headers
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "cs_test_mock_123456"
        assert data["checkout_url"] == "https://checkout.stripe.com/pay/cs_test_mock_123456"
        assert data["invoice_id"] == inv_id
        assert float(data["amount"]) == 175.50

        # Verify stripe.checkout.Session.create was called with expected amount in cents
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["line_items"][0]["price_data"]["unit_amount"] == 17550
        assert call_kwargs["mode"] == "payment"
        assert call_kwargs["client_reference_id"] == inv_id


@pytest.mark.asyncio
async def test_stripe_checkout_paid_invoice_fails(
    client: httpx.AsyncClient,
    advisor_headers: dict,
    manager_headers: dict
):
    """Attempting to create a checkout session for an already-paid invoice returns 400."""
    _, _, inv_id = await create_test_invoice(client, advisor_headers, manager_headers, amount=100.0)

    # Pay the invoice via manual payment
    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    await client.post("/payments", json={
        "invoice_id": inv_id,
        "amount": 100.0,
        "method": "cash",
        "collected_at": now_str
    }, headers=advisor_headers)

    with patch.object(settings, "STRIPE_ENABLED", True), \
         patch.object(settings, "STRIPE_SECRET_KEY", "sk_test_mock"):

        resp = await client.post(f"/invoices/{inv_id}/pay", json={}, headers=advisor_headers)
        assert resp.status_code == 400
        assert "paid" in resp.json()["detail"].lower() or "no remaining balance" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_stripe_customer_rbac_isolation(
    client: httpx.AsyncClient,
    advisor_headers: dict,
    manager_headers: dict
):
    """Customer user cannot create a checkout session for another customer's invoice."""
    # 1. Create Invoice for Customer A
    cust_a_id, _, inv_a_id = await create_test_invoice(client, advisor_headers, manager_headers, amount=150.0)

    # 2. Register & login Customer B
    cust_b_user = "cust_user_b_" + uuid.uuid4().hex[:6]
    cust_b_email = f"{cust_b_user}@test.com"
    await client.post("/auth/register", json={
        "username": cust_b_user,
        "email": cust_b_email,
        "password": "Password123!",
        "role": "customer"
    })
    token_resp = await client.post("/auth/token", data={
        "username": cust_b_user,
        "password": "Password123!"
    })
    cust_b_token = token_resp.json()["access_token"]
    cust_b_headers = {"Authorization": f"Bearer {cust_b_token}"}

    # 3. Create distinct customer profile for Customer B and link
    cust_b_resp = await client.post("/customers", json={
        "name": "Customer B",
        "customer_type": "individual",
        "tax_exempt": True
    }, headers=advisor_headers)
    cust_b_id = cust_b_resp.json()["customer_id"]

    # Link user to customer B
    user_me = await client.get("/auth/me", headers=cust_b_headers)
    user_id = user_me.json()["user_id"]
    await client.put(f"/users/{user_id}", json={"customer_id": cust_b_id}, headers=manager_headers)

    # Refresh customer B token to pick up customer_id
    token_resp2 = await client.post("/auth/token", data={
        "username": cust_b_user,
        "password": "Password123!"
    })
    cust_b_headers = {"Authorization": f"Bearer {token_resp2.json()['access_token']}"}

    # 4. Customer B tries to pay for Customer A's invoice -> 403 Forbidden
    with patch.object(settings, "STRIPE_ENABLED", True), \
         patch.object(settings, "STRIPE_SECRET_KEY", "sk_test_mock"):

        resp = await client.post(f"/invoices/{inv_a_id}/pay", json={}, headers=cust_b_headers)
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_stripe_webhook_signature_verification(
    client: httpx.AsyncClient
):
    """Webhook rejects missing or invalid signatures."""
    # Missing header -> 400
    resp1 = await client.post("/stripe/webhook", content=b"{}")
    assert resp1.status_code == 400
    assert "missing stripe-signature" in resp1.json()["detail"].lower()

    # Invalid signature -> 400
    with patch.object(settings, "STRIPE_ENABLED", True), \
         patch.object(settings, "STRIPE_SECRET_KEY", "sk_test_mock"), \
         patch.object(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test_mock"), \
         patch("stripe.Webhook.construct_event", side_effect=Exception("Invalid signature")):

        resp2 = await client.post(
            "/stripe/webhook",
            content=b'{"id": "evt_test"}',
            headers={"Stripe-Signature": "t=123,v1=bad_signature"}
        )
        assert resp2.status_code == 400
        assert "invalid" in resp2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_stripe_webhook_checkout_completed_and_idempotency(
    client: httpx.AsyncClient,
    advisor_headers: dict,
    manager_headers: dict
):
    """Valid checkout.session.completed webhook records payment and updates invoice status."""
    _, _, inv_id = await create_test_invoice(client, advisor_headers, manager_headers, amount=220.0)

    session_id = f"cs_test_{uuid.uuid4().hex[:12]}"
    payment_intent_id = f"pi_test_{uuid.uuid4().hex[:12]}"

    mock_event = {
        "id": "evt_test_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "payment_intent": payment_intent_id,
                "amount_total": 22000,  # $220.00 in cents
                "client_reference_id": inv_id,
                "metadata": {
                    "invoice_id": inv_id
                }
            }
        }
    }

    with patch.object(settings, "STRIPE_ENABLED", True), \
         patch.object(settings, "STRIPE_SECRET_KEY", "sk_test_mock"), \
         patch.object(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test_mock"), \
         patch("stripe.Webhook.construct_event", return_value=mock_event):

        # 1. Send webhook event
        resp = await client.post(
            "/stripe/webhook",
            content=b'{"mock": "payload"}',
            headers={"Stripe-Signature": "t=123,v1=valid"}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

        # 2. Verify invoice is now paid
        inv_check = await client.get(f"/invoices/{inv_id}", headers=advisor_headers)
        assert inv_check.status_code == 200
        assert inv_check.json()["status"] == "paid"

        # 3. Test Idempotency: Send the exact same webhook again
        resp_dup = await client.post(
            "/stripe/webhook",
            content=b'{"mock": "payload"}',
            headers={"Stripe-Signature": "t=123,v1=valid"}
        )
        assert resp_dup.status_code == 200

        # Invoice details should only contain 1 payment
        details = await client.get(f"/invoices/{inv_id}/details", headers=advisor_headers)
        assert details.status_code == 200
        # total balance must remain 0
        assert float(details.json()["total_balance"]) == 0.0


@pytest.mark.asyncio
async def test_stripe_payment_status_endpoint(
    client: httpx.AsyncClient,
    advisor_headers: dict,
    manager_headers: dict
):
    """Manager/advisor can query live status for a Stripe-processed payment."""
    _, _, inv_id = await create_test_invoice(client, advisor_headers, manager_headers, amount=85.0)

    # 1. Simulate a Stripe payment recorded in the database
    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    pi_id = f"pi_test_{uuid.uuid4().hex[:12]}"
    pmt_resp = await client.post("/payments", json={
        "invoice_id": inv_id,
        "amount": 85.0,
        "method": "stripe",
        "collected_at": now_str,
        "stripe_payment_intent_id": pi_id
    }, headers=advisor_headers)
    payment_id = pmt_resp.json()["payment_id"]

    # 2. Mock Stripe PaymentIntent.retrieve
    mock_pi = MagicMock()
    mock_pi.id = pi_id
    mock_pi.status = "succeeded"
    mock_pi.amount = 8500
    mock_pi.currency = "usd"

    with patch.object(settings, "STRIPE_ENABLED", True), \
         patch.object(settings, "STRIPE_SECRET_KEY", "sk_test_mock"), \
         patch("stripe.PaymentIntent.retrieve", return_value=mock_pi):

        status_resp = await client.get(
            f"/payments/{payment_id}/stripe-status",
            headers=manager_headers
        )
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["payment_id"] == payment_id
        assert data["stripe_status"] == "succeeded"
        assert data["stripe_payment_intent_id"] == pi_id
        assert float(data["amount"]) == 85.0
        assert data["currency"] == "usd"


@pytest.mark.asyncio
async def test_stripe_online_refund(
    client: httpx.AsyncClient,
    advisor_headers: dict,
    manager_headers: dict
):
    """Refunding a Stripe payment invokes stripe.Refund.create and persists stripe_refund_id."""
    _, _, inv_id = await create_test_invoice(client, advisor_headers, manager_headers, amount=120.0)

    # Record Stripe payment
    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    pi_id = f"pi_test_{uuid.uuid4().hex[:12]}"
    pmt_resp = await client.post("/payments", json={
        "invoice_id": inv_id,
        "amount": 120.0,
        "method": "stripe",
        "collected_at": now_str,
        "stripe_payment_intent_id": pi_id
    }, headers=advisor_headers)
    payment_id = pmt_resp.json()["payment_id"]

    # Mock stripe.Refund.create
    mock_refund = MagicMock()
    mock_refund.id = f"re_test_{uuid.uuid4().hex[:12]}"

    with patch.object(settings, "STRIPE_ENABLED", True), \
         patch.object(settings, "STRIPE_SECRET_KEY", "sk_test_mock"), \
         patch("stripe.Refund.create", return_value=mock_refund) as mock_refund_create:

        refund_resp = await client.post(
            f"/payments/{payment_id}/refund",
            json={
                "amount": 120.0,
                "reason": "Customer cancellation after diagnostic"
            },
            headers=manager_headers
        )

        assert refund_resp.status_code == 200
        refund_data = refund_resp.json()
        assert float(refund_data["refund_amount"]) == 120.0
        assert refund_data["stripe_refund_id"] == mock_refund.id
        mock_refund_create.assert_called_once()
