import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.models import Customer, Vehicle, Quote, WorkOrder, Invoice, Deposit, Payment
from app.schemas import (
    QuoteCreate, QuoteUpdate, QuoteResponse,
    InvoiceCreate, InvoiceUpdate, InvoiceResponse,
    DepositCreate, DepositUpdate, DepositResponse,
    PaymentCreate, PaymentResponse
)
from fastapi_pagination import LimitOffsetPage
from fastapi_pagination.ext.sqlalchemy import apaginate
from app.routers.auth_deps import RoleChecker
from app.routers.pagination_deps import PaginationParams

# Enforces that all endpoints in this file require manager or advisor roles by default
router = APIRouter(dependencies=[Depends(RoleChecker(["manager", "advisor"]))])

# --- QUOTE ENDPOINTS ---

@router.post("/quotes", response_model=QuoteResponse, status_code=status.HTTP_201_CREATED)
async def create_quote(payload: QuoteCreate, db: AsyncSession = Depends(get_db)):
    """
    Draft a new quote. Validates customer and vehicle existence.
    """
    # Validate Customer exists
    cust_res = await db.execute(select(Customer).where(Customer.customer_id == payload.customer_id))
    if not cust_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Customer does not exist.")
    
    # Validate Vehicle exists
    veh_res = await db.execute(select(Vehicle).where(Vehicle.vin == payload.vehicle_id))
    if not veh_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Vehicle does not exist.")

    try:
        q = Quote(
            customer_id=payload.customer_id,
            vehicle_id=payload.vehicle_id,
            visit_id=payload.visit_id,
            status=payload.status,
            total_amount=payload.total_amount,
            drafted_at=payload.drafted_at,
            valid_until=payload.valid_until,
            issued_at=payload.issued_at,
            decline_reason=payload.decline_reason
        )
        db.add(q)
        await db.flush()
        return q
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/quotes", response_model=LimitOffsetPage[QuoteResponse])
async def list_quotes(params: PaginationParams = Depends(), db: AsyncSession = Depends(get_db)):
    """
    Retrieve all quotes with pagination.
    """
    return await apaginate(db, select(Quote), params)

@router.put("/quotes/{quote_id}", response_model=QuoteResponse)
async def update_quote(quote_id: uuid.UUID, payload: QuoteUpdate, db: AsyncSession = Depends(get_db)):
    """
    Update details of an existing quote (status, amount, etc.).
    """
    result = await db.execute(select(Quote).where(Quote.quote_id == quote_id))
    q = result.scalar_one_or_none()
    if not q:
        raise HTTPException(status_code=404, detail="Quote not found")
    
    try:
        if payload.status is not None:
            q.status = payload.status
        if payload.total_amount is not None:
            q.total_amount = payload.total_amount
        if payload.valid_until is not None:
            q.valid_until = payload.valid_until
        if payload.issued_at is not None:
            q.issued_at = payload.issued_at
        if payload.decline_reason is not None:
            q.decline_reason = payload.decline_reason
            
        await db.flush()
        return q
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- INVOICE ENDPOINTS ---

@router.post("/invoices", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(payload: InvoiceCreate, db: AsyncSession = Depends(get_db)):
    """
    Generate a new bill/invoice for completed work orders.
    """
    # Validate Customer exists
    cust_res = await db.execute(select(Customer).where(Customer.customer_id == payload.customer_id))
    if not cust_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Customer does not exist.")
    
    # Validate WorkOrder exists
    wo_res = await db.execute(select(WorkOrder).where(WorkOrder.work_order_id == payload.work_order_id))
    if not wo_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="WorkOrder does not exist.")

    try:
        invoice = Invoice(
            work_order_id=payload.work_order_id,
            customer_id=payload.customer_id,
            status=payload.status,
            amount_due=payload.amount_due,
            issued_at=payload.issued_at
        )
        db.add(invoice)
        await db.flush()
        return invoice
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/invoices", response_model=LimitOffsetPage[InvoiceResponse])
async def list_invoices(params: PaginationParams = Depends(), db: AsyncSession = Depends(get_db)):
    """
    Retrieve all invoices with pagination.
    """
    return await apaginate(db, select(Invoice), params)

@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(invoice_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """
    Retrieve details of a single invoice by ID.
    """
    result = await db.execute(select(Invoice).where(Invoice.invoice_id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice

@router.put("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(invoice_id: uuid.UUID, payload: InvoiceUpdate, db: AsyncSession = Depends(get_db)):
    """
    Modify an invoice status, adjust amount due, or apply credit.
    """
    result = await db.execute(select(Invoice).where(Invoice.invoice_id == invoice_id))
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    try:
        if payload.status is not None:
            invoice.status = payload.status
        if payload.amount_due is not None:
            invoice.amount_due = payload.amount_due
        if payload.warranty_id is not None:
            invoice.warranty_id = payload.warranty_id
        if payload.credit_amount is not None:
            invoice.credit_amount = payload.credit_amount
        if payload.credit_reason is not None:
            invoice.credit_reason = payload.credit_reason
            
        await db.flush()
        return invoice
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- DEPOSIT ENDPOINTS ---

@router.post("/deposits", response_model=DepositResponse, status_code=status.HTTP_201_CREATED)
async def create_deposit(payload: DepositCreate, db: AsyncSession = Depends(get_db)):
    """
    Record a pre-payment/deposit collected from a customer.
    """
    # Validate Customer exists
    cust_res = await db.execute(select(Customer).where(Customer.customer_id == payload.customer_id))
    if not cust_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Customer does not exist.")
    
    # Validate Quote exists
    q_res = await db.execute(select(Quote).where(Quote.quote_id == payload.quote_id))
    if not q_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Quote does not exist.")

    # Validate WorkOrder if provided
    wo_obj = None
    if payload.work_order_id is not None:
        wo_res = await db.execute(select(WorkOrder).where(WorkOrder.work_order_id == payload.work_order_id))
        wo_obj = wo_res.scalar_one_or_none()
        if not wo_obj:
            raise HTTPException(status_code=400, detail="WorkOrder does not exist.")

    try:
        deposit = Deposit(
            quote_id=payload.quote_id,
            customer_id=payload.customer_id,
            amount=payload.amount,
            status=payload.status,
            collected_at=payload.collected_at
        )
        if wo_obj:
            # Setting the relationship in memory so that the event listener triggers
            deposit.work_order = wo_obj
        
        db.add(deposit)
        await db.flush()
        return deposit
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- PAYMENT ENDPOINTS ---

@router.post("/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(payload: PaymentCreate, db: AsyncSession = Depends(get_db)):
    """
    Record a payment received for an invoice.
    """
    # Validate Invoice exists
    inv_res = await db.execute(select(Invoice).where(Invoice.invoice_id == payload.invoice_id))
    if not inv_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Invoice does not exist.")

    try:
        payment = Payment(
            invoice_id=payload.invoice_id,
            amount=payload.amount,
            method=payload.method,
            collected_at=payload.collected_at,
            payer_id=payload.payer_id
        )
        db.add(payment)
        await db.flush()
        return payment
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
