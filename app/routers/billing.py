import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.models import Customer, Vehicle, Quote, WorkOrder, Invoice, Deposit, Payment, User, Dispute, Warranty, WarrantyClaim
from app.schemas import (
    QuoteCreate, QuoteUpdate, QuoteResponse,
    InvoiceCreate, InvoiceUpdate, InvoiceResponse, InvoiceDetailResponse,
    DepositCreate, DepositUpdate, DepositResponse,
    PaymentCreate, PaymentResponse,
    DisputeCreate, DisputeUpdate, DisputeResponse,
    WarrantyCreate, WarrantyUpdate, WarrantyResponse,
    WarrantyClaimCreate, WarrantyClaimUpdate, WarrantyClaimResponse
)
from fastapi_pagination import LimitOffsetPage
from fastapi_pagination.ext.sqlalchemy import apaginate
from app.routers.auth_deps import RoleChecker
from app.routers.pagination_deps import PaginationParams

from app.services import BillingService
from app.exceptions import NotFoundError

router = APIRouter()

# --- QUOTE ENDPOINTS ---

@router.post("/quotes", response_model=QuoteResponse, status_code=status.HTTP_201_CREATED)
async def create_quote(
    payload: QuoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor"]))
):
    """
    Draft a new quote. Validates customer and vehicle existence.
    """
    try:
        return await BillingService.create_quote(db, payload)
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
        return await BillingService.update_quote(db, quote_id, payload)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
    query = select(Invoice)
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

