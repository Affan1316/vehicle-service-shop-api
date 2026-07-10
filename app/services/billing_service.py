import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.models import Customer, Vehicle, Quote, WorkOrder, Invoice, Deposit, Payment
from app.schemas.schemas import (
    QuoteCreate, QuoteUpdate,
    InvoiceCreate, InvoiceUpdate,
    DepositCreate,
    PaymentCreate
)
from app.exceptions import NotFoundError


class BillingService:
    @staticmethod
    async def create_quote(db: AsyncSession, payload: QuoteCreate) -> Quote:
        cust_res = await db.execute(select(Customer).where(Customer.customer_id == payload.customer_id))
        if not cust_res.scalar_one_or_none():
            raise ValueError("Customer does not exist.")
        
        veh_res = await db.execute(select(Vehicle).where(Vehicle.vin == payload.vehicle_id))
        if not veh_res.scalar_one_or_none():
            raise ValueError("Vehicle does not exist.")

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

    @staticmethod
    async def get_quote(db: AsyncSession, quote_id: uuid.UUID) -> Quote:
        result = await db.execute(select(Quote).where(Quote.quote_id == quote_id))
        q = result.scalar_one_or_none()
        if not q:
            raise NotFoundError("Quote not found")
        return q

    @staticmethod
    async def update_quote(db: AsyncSession, quote_id: uuid.UUID, payload: QuoteUpdate) -> Quote:
        q = await BillingService.get_quote(db, quote_id)
        
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

    @staticmethod
    async def create_invoice(db: AsyncSession, payload: InvoiceCreate) -> Invoice:
        cust_res = await db.execute(select(Customer).where(Customer.customer_id == payload.customer_id))
        if not cust_res.scalar_one_or_none():
            raise ValueError("Customer does not exist.")
        
        wo_res = await db.execute(select(WorkOrder).where(WorkOrder.work_order_id == payload.work_order_id))
        if not wo_res.scalar_one_or_none():
            raise ValueError("WorkOrder does not exist.")

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

    @staticmethod
    async def get_invoice(db: AsyncSession, invoice_id: uuid.UUID) -> Invoice:
        result = await db.execute(select(Invoice).where(Invoice.invoice_id == invoice_id))
        invoice = result.scalar_one_or_none()
        if not invoice:
            raise NotFoundError("Invoice not found")
        return invoice

    @staticmethod
    async def update_invoice(db: AsyncSession, invoice_id: uuid.UUID, payload: InvoiceUpdate) -> Invoice:
        invoice = await BillingService.get_invoice(db, invoice_id)

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

    @staticmethod
    async def create_deposit(db: AsyncSession, payload: DepositCreate) -> Deposit:
        cust_res = await db.execute(select(Customer).where(Customer.customer_id == payload.customer_id))
        if not cust_res.scalar_one_or_none():
            raise ValueError("Customer does not exist.")
        
        q_res = await db.execute(select(Quote).where(Quote.quote_id == payload.quote_id))
        if not q_res.scalar_one_or_none():
            raise ValueError("Quote does not exist.")

        wo_obj = None
        if payload.work_order_id is not None:
            wo_res = await db.execute(select(WorkOrder).where(WorkOrder.work_order_id == payload.work_order_id))
            wo_obj = wo_res.scalar_one_or_none()
            if not wo_obj:
                raise ValueError("WorkOrder does not exist.")

        deposit = Deposit(
            quote_id=payload.quote_id,
            customer_id=payload.customer_id,
            amount=payload.amount,
            status=payload.status,
            collected_at=payload.collected_at
        )
        if wo_obj:
            deposit.work_order = wo_obj
        
        db.add(deposit)
        await db.flush()
        return deposit

    @staticmethod
    async def create_payment(db: AsyncSession, payload: PaymentCreate) -> Payment:
        inv_res = await db.execute(select(Invoice).where(Invoice.invoice_id == payload.invoice_id))
        if not inv_res.scalar_one_or_none():
            raise ValueError("Invoice does not exist.")

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
