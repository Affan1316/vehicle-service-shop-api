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

from app.services import BillingService
from app.exceptions import NotFoundError

# Enforces that all endpoints in this file require manager or advisor roles by default
router = APIRouter(dependencies=[Depends(RoleChecker(["manager", "advisor"]))])

# --- QUOTE ENDPOINTS ---

@router.post("/quotes", response_model=QuoteResponse, status_code=status.HTTP_201_CREATED)
async def create_quote(payload: QuoteCreate, db: AsyncSession = Depends(get_db)):
    """
    Draft a new quote. Validates customer and vehicle existence.
    """
    try:
        return await BillingService.create_quote(db, payload)
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
    try:
        return await BillingService.update_quote(db, quote_id, payload)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- INVOICE ENDPOINTS ---

@router.post("/invoices", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(payload: InvoiceCreate, db: AsyncSession = Depends(get_db)):
    """
    Generate a new bill/invoice for completed work orders.
    """
    try:
        return await BillingService.create_invoice(db, payload)
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
    try:
        return await BillingService.get_invoice(db, invoice_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.put("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(invoice_id: uuid.UUID, payload: InvoiceUpdate, db: AsyncSession = Depends(get_db)):
    """
    Modify an invoice status, adjust amount due, or apply credit.
    """
    try:
        return await BillingService.update_invoice(db, invoice_id, payload)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- DEPOSIT ENDPOINTS ---

@router.post("/deposits", response_model=DepositResponse, status_code=status.HTTP_201_CREATED)
async def create_deposit(payload: DepositCreate, db: AsyncSession = Depends(get_db)):
    """
    Record a pre-payment/deposit collected from a customer.
    """
    try:
        return await BillingService.create_deposit(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- PAYMENT ENDPOINTS ---

@router.post("/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(payload: PaymentCreate, db: AsyncSession = Depends(get_db)):
    """
    Record a payment received for an invoice.
    """
    try:
        return await BillingService.create_payment(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

