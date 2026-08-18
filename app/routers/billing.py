import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response, BackgroundTasks, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.models import Customer, Quote, Invoice, Payment, User
from app.schemas import (
    QuoteCreate, QuoteUpdate, QuoteResponse,
    InvoiceCreate, InvoiceUpdate, InvoiceResponse, InvoiceDetailResponse,
    DepositCreate, DepositResponse,
    PaymentCreate, PaymentResponse, RefundRequest, PaymentRefundResponse,
    DisputeCreate, DisputeUpdate, DisputeResponse,
    WarrantyCreate, WarrantyResponse,
    WarrantyClaimCreate, WarrantyClaimUpdate, WarrantyClaimResponse,
    StripeCheckoutRequest, StripeCheckoutResponse, StripePaymentStatusResponse
)
from fastapi_pagination import LimitOffsetPage
from fastapi_pagination.ext.sqlalchemy import apaginate
from app.routers.auth_deps import RoleChecker
from app.routers.pagination_deps import PaginationParams

from app.services import BillingService, PDFService, EmailService, AuditService, StripeService
from app.exceptions import NotFoundError, ValidationError, PaymentGatewayError

router = APIRouter()

# --- QUOTE ENDPOINTS ---

@router.post("/quotes", response_model=QuoteResponse, status_code=status.HTTP_201_CREATED)
async def create_quote(
    payload: QuoteCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor"]))
):
    """
    Draft a new quote. Validates customer and vehicle existence.
    """
    try:
        quote = await BillingService.create_quote(db, payload)
        await AuditService.log_create(
            db, "quote", str(quote.quote_id),
            current_user.user_id, current_user.username,
            {"total_amount": str(quote.total_amount), "status": quote.status}
        )
        # Send quote ready email if customer has email
        cust_res = await db.execute(select(Customer).where(Customer.customer_id == payload.customer_id))
        cust = cust_res.scalar_one_or_none()
        if cust and cust.email:
            background_tasks.add_task(
                EmailService.send_quote_ready,
                cust.email,
                cust.name,
                quote.quote_id,
                float(quote.total_amount)
            )
        return quote
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/quotes", response_model=LimitOffsetPage[QuoteResponse])
async def list_quotes(
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor", "customer"]))
):
    """
    Retrieve all quotes with pagination.
    """
    query = select(Quote).options(selectinload(Quote.work_order))
    if current_user.role == "customer":
        if current_user.customer_id is None:
            raise HTTPException(status_code=400, detail="User is not linked to a customer profile.")
        query = query.where(Quote.customer_id == current_user.customer_id)
    return await apaginate(db, query, params)

@router.put("/quotes/{quote_id}", response_model=QuoteResponse)
async def update_quote(
    quote_id: uuid.UUID,
    payload: QuoteUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor", "customer"]))
):
    """
    Update details of an existing quote (status, amount, etc.).
    """
    if current_user.role == "customer":
        try:
            quote = await BillingService.get_quote(db, quote_id)
            if quote.customer_id != current_user.customer_id:
                raise HTTPException(status_code=403, detail="Not authorized to update this quote.")
            if payload.status not in ["approved", "declined"]:
                raise HTTPException(status_code=400, detail="Customers can only approve or decline quotes.")
            # Restrict fields customers can update
            payload = QuoteUpdate(
                status=payload.status,
                decline_reason=payload.decline_reason
            )
        except NotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))

    elif current_user.role == "advisor":
        if payload.status == "approved":
            raise HTTPException(status_code=403, detail="Advisors cannot approve quotes on behalf of customers. Manager override or customer approval is required.")
        if payload.total_amount is not None:
            raise HTTPException(status_code=403, detail="Advisors cannot manually override the quote total amount. Manager approval required.")

    try:
        quote = await BillingService.update_quote(db, quote_id, payload)
        await AuditService.log_update(
            db, "quote", str(quote_id),
            current_user.user_id, current_user.username,
            payload.model_dump(exclude_unset=True)
        )
        return quote
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/quotes/{quote_id}/pdf")
async def get_quote_pdf(
    quote_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor", "customer"]))
):
    """
    Download a formatted PDF estimate/quote document.
    """
    if current_user.role == "customer":
        try:
            quote = await BillingService.get_quote(db, quote_id)
            if quote.customer_id != current_user.customer_id:
                raise HTTPException(status_code=403, detail="Not authorized to view this quote.")
        except NotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
    try:
        pdf_bytes = await PDFService.generate_quote_pdf(db, quote_id)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename=quote_{str(quote_id)[:8]}.pdf"}
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- INVOICE ENDPOINTS ---

@router.post("/invoices", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    payload: InvoiceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor"]))
):
    """
    Generate a new bill/invoice for completed work orders.
    """
    try:
        return await BillingService.create_invoice(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/invoices", response_model=LimitOffsetPage[InvoiceResponse])
async def list_invoices(
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor", "customer"]))
):
    """
    Retrieve all invoices with pagination.
    """
    from sqlalchemy.orm import selectinload
    query = select(Invoice).options(selectinload(Invoice.payments))
    if current_user.role == "customer":
        if current_user.customer_id is None:
            raise HTTPException(status_code=400, detail="User is not linked to a customer profile.")
        query = query.where(Invoice.customer_id == current_user.customer_id)
    return await apaginate(db, query, params)

@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor", "customer"]))
):
    """
    Retrieve details of a single invoice by ID.
    """
    try:
        invoice = await BillingService.get_invoice(db, invoice_id)
        if current_user.role == "customer" and invoice.customer_id != current_user.customer_id:
            raise HTTPException(status_code=403, detail="Not authorized to view this invoice.")
        return invoice
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/invoices/{invoice_id}/details", response_model=InvoiceDetailResponse)
async def get_invoice_details(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor", "customer"]))
):
    """
    Retrieve itemized labor and part details for a single invoice.
    """
    try:
        details = await BillingService.get_invoice_details(db, invoice_id)
        if current_user.role == "customer" and details.customer_id != current_user.customer_id:
            raise HTTPException(status_code=403, detail="Not authorized to view this invoice's details.")
        return details
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.put("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(
    invoice_id: uuid.UUID,
    payload: InvoiceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor"]))
):
    """
    Modify an invoice status, adjust amount due, or apply credit.
    """
    if current_user.role == "advisor":
        if payload.amount_due is not None:
            raise HTTPException(status_code=403, detail="Advisors cannot manually override the total amount due. Manager approval required.")
        if payload.credit_amount is not None and payload.credit_amount > 50:
            raise HTTPException(status_code=403, detail="Advisors cannot apply credits greater than $50. Manager approval required.")

    try:
        return await BillingService.update_invoice(db, invoice_id, payload)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/invoices/{invoice_id}/pdf")
async def get_invoice_pdf(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor", "customer"]))
):
    """
    Download a formatted PDF invoice with tax, payment history, and balance details.
    """
    if current_user.role == "customer":
        try:
            invoice = await BillingService.get_invoice(db, invoice_id)
            if invoice.customer_id != current_user.customer_id:
                raise HTTPException(status_code=403, detail="Not authorized to view this invoice.")
        except NotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
    try:
        pdf_bytes = await PDFService.generate_invoice_pdf(db, invoice_id)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename=invoice_{str(invoice_id)[:8]}.pdf"}
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- DEPOSIT ENDPOINTS ---

@router.post("/deposits", response_model=DepositResponse, status_code=status.HTTP_201_CREATED)
async def create_deposit(
    payload: DepositCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor"]))
):
    """
    Record a pre-payment/deposit collected from a customer.
    """
    try:
        return await BillingService.create_deposit(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/deposits/{deposit_id}/refund", response_model=DepositResponse)
async def refund_deposit(
    deposit_id: uuid.UUID,
    payload: RefundRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager"]))
):
    """
    Manager endpoint: Issue a full or partial refund for a customer deposit.
    """
    try:
        return await BillingService.refund_deposit(db, deposit_id, payload.amount, payload.reason)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- PAYMENT ENDPOINTS ---

@router.post("/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    payload: PaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor", "customer"]))
):
    """
    Record a payment received for an invoice.
    """
    if current_user.role == "customer":
        try:
            invoice = await BillingService.get_invoice(db, payload.invoice_id)
            if invoice.customer_id != current_user.customer_id:
                raise HTTPException(status_code=403, detail="Not authorized to pay for this invoice.")
        except NotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
    try:
        return await BillingService.create_payment(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/payments/{payment_id}/refund", response_model=PaymentRefundResponse)
async def refund_payment(
    payment_id: uuid.UUID,
    payload: RefundRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager"]))
):
    """
    Manager endpoint: Issue a full or partial refund for an invoice payment.
    """
    try:
        return await BillingService.refund_payment(db, payment_id, payload.amount, payload.reason)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (ValueError, PaymentGatewayError) as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- STRIPE PAYMENT GATEWAY ENDPOINTS ---

@router.post("/invoices/{invoice_id}/pay", response_model=StripeCheckoutResponse)
async def create_stripe_checkout_session(
    invoice_id: uuid.UUID,
    payload: StripeCheckoutRequest = StripeCheckoutRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor", "customer"]))
):
    """
    Create a Stripe Checkout session to collect online payment for an invoice.
    Returns the session ID and hosted checkout URL.
    """
    if current_user.role == "customer":
        try:
            invoice = await BillingService.get_invoice(db, invoice_id)
            if invoice.customer_id != current_user.customer_id:
                raise HTTPException(status_code=403, detail="Not authorized to pay for this invoice.")
        except NotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))

    try:
        session_data = await StripeService.create_checkout_session(
            db=db,
            invoice_id=invoice_id,
            success_url=payload.success_url,
            cancel_url=payload.cancel_url
        )
        return session_data
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PaymentGatewayError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Payment gateway error: {str(e)}")


@router.post("/stripe/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature"),
    db: AsyncSession = Depends(get_db)
):
    """
    Stripe Webhook handler to receive asynchronous payment lifecycle events.
    Verifies cryptographic signature using STRIPE_WEBHOOK_SECRET.
    """
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header.")

    payload = await request.body()
    try:
        event = StripeService.process_webhook_event(payload, stripe_signature)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PaymentGatewayError as e:
        raise HTTPException(status_code=503, detail=str(e))

    event_type = event.get("type")
    data_object = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        await StripeService.handle_checkout_completed(db, data_object)

    return {"status": "success", "event_type": event_type}


@router.get("/payments/{payment_id}/stripe-status", response_model=StripePaymentStatusResponse)
async def get_stripe_payment_status(
    payment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor"]))
):
    """
    Manager & Advisor endpoint: Query live Stripe status for a payment.
    """
    res = await db.execute(select(Payment).where(Payment.payment_id == payment_id))
    payment = res.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail=f"Payment with ID {payment_id} not found.")

    if not payment.stripe_payment_intent_id:
        raise HTTPException(
            status_code=400,
            detail="This payment was not processed via Stripe or lacks a Stripe Payment Intent ID."
        )

    try:
        status_info = StripeService.get_payment_status(payment.stripe_payment_intent_id)
        return {
            "payment_id": payment.payment_id,
            "stripe_status": status_info["stripe_status"],
            "stripe_payment_intent_id": status_info["stripe_payment_intent_id"],
            "amount": status_info["amount"],
            "currency": status_info["currency"]
        }
    except PaymentGatewayError as e:
        raise HTTPException(status_code=503, detail=str(e))


# --- DISPUTE ENDPOINTS ---

@router.post(
    "/invoices/{invoice_id}/disputes",
    response_model=DisputeResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_dispute(
    invoice_id: uuid.UUID,
    payload: DisputeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor", "customer"]))
):
    """
    Open a dispute against an invoice.
    """
    if current_user.role == "customer":
        try:
            invoice = await BillingService.get_invoice(db, invoice_id)
            if invoice.customer_id != current_user.customer_id:
                raise HTTPException(status_code=403, detail="Not authorized to dispute this invoice.")
        except NotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
    try:
        return await BillingService.create_dispute(db, payload)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/invoices/{invoice_id}/disputes",
    response_model=List[DisputeResponse]
)
async def list_invoice_disputes(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor", "customer"]))
):
    """
    List disputes for a single invoice.
    """
    if current_user.role == "customer":
        try:
            invoice = await BillingService.get_invoice(db, invoice_id)
            if invoice.customer_id != current_user.customer_id:
                raise HTTPException(status_code=403, detail="Not authorized to view disputes for this invoice.")
        except NotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
    return await BillingService.get_invoice_disputes(db, invoice_id)

@router.put(
    "/disputes/{dispute_id}",
    response_model=DisputeResponse,
    dependencies=[Depends(RoleChecker(["manager"]))]
)
async def update_dispute(dispute_id: uuid.UUID, payload: DisputeUpdate, db: AsyncSession = Depends(get_db)):
    """
    Update/resolve a dispute.
    """
    try:
        return await BillingService.update_dispute(db, dispute_id, payload)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- WARRANTY ENDPOINTS ---

@router.post(
    "/work-orders/{work_order_id}/warranties",
    response_model=WarrantyResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker(["manager", "advisor"]))]
)
async def create_warranty(work_order_id: uuid.UUID, payload: WarrantyCreate, db: AsyncSession = Depends(get_db)):
    """
    Issue a new warranty.
    """
    try:
        return await BillingService.create_warranty(db, payload)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/warranties/{warranty_id}",
    response_model=WarrantyResponse,
    dependencies=[Depends(RoleChecker(["manager", "advisor", "customer"]))]
)
async def get_warranty(warranty_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """
    Get a warranty by ID.
    """
    try:
        return await BillingService.get_warranty(db, warranty_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post(
    "/warranties/{warranty_id}/claims",
    response_model=WarrantyClaimResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker(["manager", "advisor"]))]
)
async def create_warranty_claim(warranty_id: uuid.UUID, payload: WarrantyClaimCreate, db: AsyncSession = Depends(get_db)):
    """
    File a warranty claim.
    """
    try:
        return await BillingService.create_warranty_claim(db, payload)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/warranties/{warranty_id}/claims",
    response_model=List[WarrantyClaimResponse],
    dependencies=[Depends(RoleChecker(["manager", "advisor", "customer"]))]
)
async def list_warranty_claims(warranty_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """
    List claims filed against a warranty.
    """
    return await BillingService.get_warranty_claims(db, warranty_id)

@router.put(
    "/claims/{claim_id}",
    response_model=WarrantyClaimResponse,
    dependencies=[Depends(RoleChecker(["manager"]))]
)
async def update_warranty_claim(claim_id: uuid.UUID, payload: WarrantyClaimUpdate, db: AsyncSession = Depends(get_db)):
    """
    Approve, deny, or resolve a claim.
    """
    try:
        return await BillingService.update_warranty_claim(db, claim_id, payload)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- SAFEPAY WEBHOOK ---
@router.post("/webhooks/safepay")
async def safepay_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Handle Safepay webhooks for payment updates.
    """
    from app.services.safepay_service import SafepayService
    payload = await request.body()
    sig_header = request.headers.get("x-sfpy-signature", "")

    is_valid = SafepayService.verify_webhook(payload, sig_header)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    import json
    try:
        data = json.loads(payload)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    if data.get('event') == 'payment.success' or data.get('type') == 'payment_intent.succeeded':
        tracker = data.get('tracker')
        invoice_id = data.get('metadata', {}).get('order_id') or data.get('order_id')
        if invoice_id:
            try:
                invoice = await BillingService.get_invoice(db, uuid.UUID(invoice_id))
                from app.models.models import Payment
                res = await db.execute(select(Payment).where(Payment.stripe_charge_id == tracker))
                if res.scalar_one_or_none():
                    return {"status": "success"}

                amount = decimal.Decimal(str(data.get('amount', 0)))
                payment = Payment(
                    invoice_id=invoice.invoice_id,
                    amount=amount,
                    method="safepay",
                    collected_at=datetime.datetime.now(datetime.timezone.utc),
                    stripe_charge_id=tracker
                )
                db.add(payment)
                invoice.status = 'paid'
                await db.flush()
            except Exception as e:
                pass
                
    return {"status": "success"}


