import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import datetime
from app.models.models import Customer, Vehicle, Quote, WorkOrder, Invoice, Deposit, Payment, Dispute, Warranty, WarrantyClaim
from app.schemas.schemas import (
    QuoteCreate, QuoteUpdate,
    InvoiceCreate, InvoiceUpdate,
    DepositCreate,
    PaymentCreate,
    DisputeCreate, DisputeUpdate,
    WarrantyCreate, WarrantyUpdate,
    WarrantyClaimCreate, WarrantyClaimUpdate
)
from app.exceptions import NotFoundError
from app.services.safepay_service import SafepayService


class BillingService:
    @staticmethod
    async def create_quote(db: AsyncSession, payload: QuoteCreate) -> Quote:
        cust_res = await db.execute(select(Customer).where(Customer.customer_id == payload.customer_id))
        if not cust_res.scalar_one_or_none():
            raise ValueError("Customer does not exist.")
        
        veh_res = await db.execute(select(Vehicle).where(Vehicle.vin == payload.vehicle_id))
        veh = veh_res.scalar_one_or_none()
        if not veh:
            raise ValueError("Vehicle does not exist.")
        if veh.customer_id != payload.customer_id:
            raise ValueError("Vehicle does not belong to the specified customer.")
            
        if payload.visit_id is not None:
            from app.models.models import Diagnostic
            diag_res = await db.execute(select(Diagnostic).where(Diagnostic.visit_id == payload.visit_id))
            diagnostics = diag_res.scalars().all()
            if diagnostics:
                incomplete = [d for d in diagnostics if d.status != 'completed']
                if incomplete:
                    raise ValueError("Cannot create a quote: Technician visual inspection is pending or in progress.")

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
            if payload.status == 'issued':
                from app.models.models import WorkOrder
                from sqlalchemy.orm import selectinload
                wo_res = await db.execute(select(WorkOrder).options(selectinload(WorkOrder.line_items)).where(WorkOrder.quote_id == quote_id))
                wo = wo_res.scalar_one_or_none()
                if wo:
                    for li in wo.line_items:
                        if li.price == 0 and not getattr(li, 'is_complimentary', False):
                            raise ValueError(f"Cannot issue quote: line item '{li.description}' has a $0.00 price and is not marked complimentary.")
            elif payload.status == 'approved':
                from app.models.models import WorkOrder, Visit
                wo_res = await db.execute(select(WorkOrder).where(WorkOrder.quote_id == quote_id))
                wo = wo_res.scalar_one_or_none()
                if wo and wo.status == 'created':
                    wo.status = 'in_progress'
                    wo.authorized_amount = q.total_amount
                
                if q.visit_id:
                    visit_res = await db.execute(select(Visit).where(Visit.visit_id == q.visit_id))
                    visit = visit_res.scalar_one_or_none()
                    if visit and visit.status == 'awaiting_quote':
                        visit.status = 'in_service'

            q.status = payload.status
        
        if payload.total_amount is not None:
            if q.status in ['issued', 'approved'] and payload.total_amount != q.total_amount:
                raise ValueError(f"Cannot modify total amount of a quote that is '{q.status}'.")
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
        customer = cust_res.scalar_one_or_none()
        if not customer:
            raise ValueError("Customer does not exist.")
        
        wo_res = await db.execute(select(WorkOrder).where(WorkOrder.work_order_id == payload.work_order_id))
        wo = wo_res.scalar_one_or_none()
        if not wo:
            raise ValueError("WorkOrder does not exist.")
            
        if wo.status != 'closed':
            raise ValueError("Cannot create an invoice for a work order that is not closed.")

        existing_inv = await db.execute(select(Invoice).where(Invoice.work_order_id == payload.work_order_id))
        if existing_inv.scalar_one_or_none():
            raise ValueError("An invoice already exists for this work order.")

        invoice = Invoice(
            work_order_id=payload.work_order_id,
            customer_id=payload.customer_id,
            status=payload.status,
            amount_due=payload.amount_due,
            issued_at=payload.issued_at
        )
        db.add(invoice)
        await db.flush()
        
        # Generate Safepay Tracker
        try:
            tracker = await SafepayService.create_checkout_tracker(
                amount=float(payload.amount_due),
                order_id=str(invoice.invoice_id)
            )
            invoice.safepay_tracker_id = tracker.get("tracker_id")
            invoice.safepay_checkout_url = tracker.get("checkout_url")
            await db.flush()
        except Exception as e:
            pass # allow invoice creation even if Safepay fails initially


        # Apply collected deposits from the work order or its quote
        dep_res = await db.execute(
            select(Deposit)
            .where(
                (Deposit.status == 'collected') & 
                ((Deposit.work_order_id == wo.work_order_id) | (Deposit.quote_id == wo.quote_id))
            )
        )
        deposits = dep_res.scalars().all()
        
        for deposit in deposits:
            payment = Payment(
                invoice_id=invoice.invoice_id,
                amount=deposit.amount,
                method='deposit_transfer',
                collected_at=datetime.datetime.now(datetime.timezone.utc),
            )
            db.add(payment)
            deposit.status = 'applied'
            deposit.invoice_id = invoice.invoice_id
            
        await db.flush()
        
        # Check if invoice is fully paid by deposits
        paid_amount = sum(d.amount for d in deposits)
        credit = invoice.credit_amount or 0
        if invoice.amount_due - credit - paid_amount <= 0:
            invoice.status = 'paid'
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
    async def get_invoice_details(db: AsyncSession, invoice_id: uuid.UUID):
        invoice = await BillingService.get_invoice(db, invoice_id)
        
        from app.models.models import LineItem, LaborEntry, PartInstance
        
        li_res = await db.execute(select(LineItem.line_item_id).where(LineItem.work_order_id == invoice.work_order_id))
        li_ids = [row[0] for row in li_res.all()]
        
        if not li_ids:
            labor_entries = []
            part_instances = []
        else:
            labor_res = await db.execute(select(LaborEntry).where(LaborEntry.line_item_id.in_(li_ids)))
            labor_entries = labor_res.scalars().all()
            
            part_res = await db.execute(select(PartInstance).where(PartInstance.line_item_id.in_(li_ids)))
            part_instances = part_res.scalars().all()
            
        class InvoiceDetail:
            def __init__(self, inv, labors, parts):
                for k in inv.__mapper__.columns.keys():
                    setattr(self, k, getattr(inv, k))
                self.total_balance = inv.total_balance
                self.labor_entries = labors
                self.part_instances = parts
                
        return InvoiceDetail(invoice, labor_entries, part_instances)

    @staticmethod
    async def update_invoice(db: AsyncSession, invoice_id: uuid.UUID, payload: InvoiceUpdate) -> Invoice:
        from sqlalchemy.orm import selectinload
        inv_res = await db.execute(select(Invoice).options(selectinload(Invoice.payments)).where(Invoice.invoice_id == invoice_id))
        invoice = inv_res.scalar_one_or_none()
        if not invoice:
            raise NotFoundError("Invoice not found")

        if invoice.status == 'paid':
            if (payload.amount_due is not None and payload.amount_due != invoice.amount_due) or \
               (payload.status is not None and payload.status != 'paid'):
                raise ValueError("Cannot modify amount due or status of an invoice that is already paid.")

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
            
        if invoice.status != 'paid':
            paid_amount = sum(p.amount for p in invoice.payments)
            credit = invoice.credit_amount or 0
            if invoice.amount_due - credit < paid_amount:
                raise ValueError("New amount due (minus credits) cannot be less than the already paid amount.")
            if invoice.amount_due - credit == paid_amount:
                invoice.status = 'paid'
                
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
        from sqlalchemy.orm import selectinload
        inv_res = await db.execute(select(Invoice).options(selectinload(Invoice.payments)).where(Invoice.invoice_id == payload.invoice_id))
        invoice = inv_res.scalar_one_or_none()
        if not invoice:
            raise ValueError("Invoice does not exist.")
            
        current_paid_amount = sum(p.amount for p in invoice.payments)
        credit = invoice.credit_amount or 0
        balance_due = invoice.amount_due - credit - current_paid_amount
        
        if payload.amount > balance_due:
            raise ValueError(f"Payment amount ({payload.amount}) exceeds the remaining balance due ({balance_due}).")

        payment = Payment(
            invoice_id=payload.invoice_id,
            amount=payload.amount,
            method=payload.method,
            collected_at=payload.collected_at,
            payer_id=payload.payer_id
        )
        db.add(payment)
        await db.flush()
        
        # Check if the invoice is now paid
        paid_amount = sum(p.amount for p in invoice.payments) + payment.amount
        credit = invoice.credit_amount or 0
        if invoice.amount_due - credit - paid_amount <= 0:
            invoice.status = 'paid'
            await db.flush()
            
        return payment

    # --- DISPUTE SERVICE METHODS ---

    @staticmethod
    async def create_dispute(db: AsyncSession, payload: DisputeCreate) -> Dispute:
        # Check if invoice exists
        inv_res = await db.execute(select(Invoice).where(Invoice.invoice_id == payload.invoice_id))
        invoice = inv_res.scalar_one_or_none()
        if not invoice:
            raise NotFoundError("Invoice not found")

        dispute = Dispute(
            invoice_id=payload.invoice_id,
            opened_by=payload.opened_by,
            reason=payload.reason,
            status="open",
            opened_at=payload.opened_at or datetime.datetime.now(datetime.timezone.utc)
        )
        db.add(dispute)

        # Set parent invoice status to 'disputed'
        invoice.status = 'disputed'

        await db.flush()
        return dispute

    @staticmethod
    async def get_invoice_disputes(db: AsyncSession, invoice_id: uuid.UUID) -> list[Dispute]:
        res = await db.execute(select(Dispute).where(Dispute.invoice_id == invoice_id))
        return list(res.scalars().all())

    @staticmethod
    async def update_dispute(db: AsyncSession, dispute_id: uuid.UUID, payload: DisputeUpdate) -> Dispute:
        res = await db.execute(select(Dispute).where(Dispute.dispute_id == dispute_id))
        dispute = res.scalar_one_or_none()
        if not dispute:
            raise NotFoundError("Dispute not found")

        if payload.status is not None:
            old_status = dispute.status
            new_status = payload.status
            dispute.status = new_status

            # If resolved, set resolved_at and transition the parent invoice back to its proper state
            if new_status == 'resolved' and old_status != 'resolved':
                dispute.resolved_at = payload.resolved_at or datetime.datetime.now(datetime.timezone.utc)
                dispute.resolution = payload.resolution

                from sqlalchemy.orm import selectinload
                inv_res = await db.execute(select(Invoice).options(selectinload(Invoice.payments)).where(Invoice.invoice_id == dispute.invoice_id))
                invoice = inv_res.scalar_one()
                
                if payload.credit_amount is not None:
                    invoice.credit_amount = (invoice.credit_amount or 0) + payload.credit_amount
                if payload.credit_reason is not None:
                    invoice.credit_reason = payload.credit_reason
                
                paid_amount = sum(p.amount for p in invoice.payments) if invoice.payments else 0
                credit = invoice.credit_amount or 0
                if invoice.amount_due - credit - paid_amount <= 0:
                    invoice.status = 'paid'
                else:
                    invoice.status = 'issued'

        await db.flush()
        return dispute

    # --- WARRANTY SERVICE METHODS ---

    @staticmethod
    async def create_warranty(db: AsyncSession, payload: WarrantyCreate) -> Warranty:
        wo_res = await db.execute(select(WorkOrder).where(WorkOrder.work_order_id == payload.work_order_id))
        if not wo_res.scalar_one_or_none():
            raise NotFoundError("WorkOrder not found")

        warranty = Warranty(
            work_order_id=payload.work_order_id,
            covers_labor=payload.covers_labor,
            covers_parts=payload.covers_parts,
            coverage_type=payload.coverage_type,
            term=payload.term,
            start_date=payload.start_date or datetime.date.today()
        )
        db.add(warranty)
        await db.flush()

        # Update the associated Invoice with the new warranty_id
        inv_res = await db.execute(select(Invoice).where(Invoice.work_order_id == payload.work_order_id))
        invoice = inv_res.scalar_one_or_none()
        if invoice:
            invoice.warranty_id = warranty.warranty_id

        return warranty

    @staticmethod
    async def get_warranty(db: AsyncSession, warranty_id: uuid.UUID) -> Warranty:
        res = await db.execute(select(Warranty).where(Warranty.warranty_id == warranty_id))
        w = res.scalar_one_or_none()
        if not w:
            raise NotFoundError("Warranty not found")
        return w

    @staticmethod
    async def create_warranty_claim(db: AsyncSession, payload: WarrantyClaimCreate) -> WarrantyClaim:
        w_res = await db.execute(select(Warranty).where(Warranty.warranty_id == payload.warranty_id))
        if not w_res.scalar_one_or_none():
            raise NotFoundError("Warranty not found")

        claim = WarrantyClaim(
            warranty_id=payload.warranty_id,
            claim_date=payload.claim_date or datetime.date.today(),
            status="filed",
            resolution=payload.resolution
        )
        db.add(claim)
        await db.flush()
        return claim

    @staticmethod
    async def get_warranty_claims(db: AsyncSession, warranty_id: uuid.UUID) -> list[WarrantyClaim]:
        res = await db.execute(select(WarrantyClaim).where(WarrantyClaim.warranty_id == warranty_id))
        return list(res.scalars().all())

    @staticmethod
    async def update_warranty_claim(db: AsyncSession, claim_id: uuid.UUID, payload: WarrantyClaimUpdate) -> WarrantyClaim:
        res = await db.execute(select(WarrantyClaim).where(WarrantyClaim.claim_id == claim_id))
        claim = res.scalar_one_or_none()
        if not claim:
            raise NotFoundError("WarrantyClaim not found")

        if payload.status is not None:
            claim.status = payload.status
        if payload.resolution is not None:
            claim.resolution = payload.resolution

        await db.flush()
        return claim

