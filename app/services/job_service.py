import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import datetime
from app.models.models import Customer, Vehicle, Quote, WorkOrder, LineItem, LaborEntry, Technician, ChangeOrder, QualityCheck
from app.schemas.schemas import WorkOrderCreate, WorkOrderUpdate, LineItemCreate, LineItemUpdate, LaborEntryCreate, ChangeOrderCreate, ChangeOrderUpdate, QualityCheckCreate
from app.exceptions import NotFoundError


class JobService:
    @staticmethod
    async def create_work_order(db: AsyncSession, payload: WorkOrderCreate) -> WorkOrder:
        cust_res = await db.execute(select(Customer).where(Customer.customer_id == payload.customer_id))
        if not cust_res.scalar_one_or_none():
            raise ValueError("Customer does not exist.")
        
        veh_res = await db.execute(select(Vehicle).where(Vehicle.vin == payload.vehicle_id))
        veh = veh_res.scalar_one_or_none()
        if not veh:
            raise ValueError("Vehicle does not exist.")
        if veh.customer_id != payload.customer_id:
            raise ValueError("Vehicle does not belong to the specified customer.")

        q_res = await db.execute(select(Quote).where(Quote.quote_id == payload.quote_id))
        quote = q_res.scalar_one_or_none()
        if not quote:
            raise ValueError("Quote does not exist.")
        if quote.status != "approved":
            if not (quote.status == "draft" and payload.status == "created"):
                raise ValueError("Quote must be approved before creating an active work order.")

        existing_wo = await db.execute(select(WorkOrder).where(WorkOrder.quote_id == payload.quote_id))
        if existing_wo.scalar_one_or_none():
            raise ValueError("A work order already exists for this quote.")

        wo = WorkOrder(
            quote_id=payload.quote_id,
            visit_id=payload.visit_id,
            vehicle_id=payload.vehicle_id,
            customer_id=payload.customer_id,
            status=payload.status,
            authorized_amount=payload.authorized_amount,
            promised_date=payload.promised_date,
            created_at=payload.created_at
        )
        db.add(wo)
        await db.flush()

        # Reload with line items to satisfy total_cost computed property
        result = await db.execute(
            select(WorkOrder)
            .options(
                selectinload(WorkOrder.line_items),
                selectinload(WorkOrder.invoice)
            )
            .where(WorkOrder.work_order_id == wo.work_order_id)
        )
        return result.scalar_one()

    @staticmethod
    async def get_work_order(db: AsyncSession, work_order_id: uuid.UUID) -> WorkOrder:
        result = await db.execute(
            select(WorkOrder)
            .options(
                selectinload(WorkOrder.line_items),
                selectinload(WorkOrder.invoice)
            )
            .where(WorkOrder.work_order_id == work_order_id)
        )
        wo = result.scalar_one_or_none()
        if not wo:
            raise NotFoundError("WorkOrder not found")
        return wo

    @staticmethod
    async def update_work_order(db: AsyncSession, work_order_id: uuid.UUID, payload: WorkOrderUpdate) -> WorkOrder:
        wo = await JobService.get_work_order(db, work_order_id)

        if payload.bay_id is not None:
            wo.bay_id = payload.bay_id
        if payload.status is not None:
            if payload.status == 'closed':
                if any(li.status != 'completed' for li in wo.line_items):
                    raise ValueError("Cannot close work order: all tasks must be completed.")
                
                REQUIRE_QC_BEFORE_CLOSURE = True
                if REQUIRE_QC_BEFORE_CLOSURE:
                    from app.models.models import QualityCheck
                    for li in wo.line_items:
                        qc_res = await db.execute(select(QualityCheck).where(QualityCheck.line_item_id == li.line_item_id, QualityCheck.status == 'passed'))
                        if not qc_res.scalars().first():
                            raise ValueError(f"Cannot close work order: line item {li.line_item_id} lacks a passed quality check.")

                # Auto-generate warranty if required
                from app.models.models import Warranty, PartInstance, Part
                warranty_needed = any(getattr(li, 'warranty_required', False) for li in wo.line_items)
                
                if not warranty_needed:
                    li_ids = [li.line_item_id for li in wo.line_items]
                    if li_ids:
                        pi_res = await db.execute(
                            select(PartInstance).join(Part).where(PartInstance.line_item_id.in_(li_ids))
                        )
                        for pi in pi_res.scalars().all():
                            if getattr(pi.part, 'warranty_required', False):
                                warranty_needed = True
                                break
                                
                if warranty_needed:
                    existing_w_res = await db.execute(select(Warranty).where(Warranty.work_order_id == work_order_id))
                    if not existing_w_res.scalar_one_or_none():
                        import datetime
                        new_w = Warranty(
                            work_order_id=work_order_id,
                            covers_labor=True,
                            covers_parts=True,
                            coverage_type="Standard Auto-Generated",
                            term="12 months / 12,000 miles",
                            start_date=datetime.date.today()
                        )
                        db.add(new_w)
                        
            wo.status = payload.status
        if payload.authorized_amount is not None:
            wo.authorized_amount = payload.authorized_amount
        if payload.promised_date is not None:
            wo.promised_date = payload.promised_date
        if payload.scheduled_at is not None:
            wo.scheduled_at = payload.scheduled_at
        if payload.paused_at is not None:
            wo.paused_at = payload.paused_at
        if payload.pause_reason is not None:
            wo.pause_reason = payload.pause_reason
        if payload.closed_at is not None:
            wo.closed_at = payload.closed_at
        if payload.archived_at is not None:
            wo.archived_at = payload.archived_at

        await db.flush()
        return wo

    @staticmethod
    async def create_line_item(db: AsyncSession, work_order_id: uuid.UUID, payload: LineItemCreate) -> LineItem:
        wo_res = await db.execute(select(WorkOrder).options(selectinload(WorkOrder.line_items)).where(WorkOrder.work_order_id == work_order_id))
        wo = wo_res.scalar_one_or_none()
        if not wo:
            raise NotFoundError("WorkOrder not found")

        current_total = sum(item.price for item in wo.line_items)
        if current_total + payload.price > wo.authorized_amount:
            raise ValueError(f"Adding this line item ({payload.price}) exceeds the authorized amount ({wo.authorized_amount}).")

        li = LineItem(
            work_order_id=work_order_id,
            description=payload.description,
            billing_mode=payload.billing_mode,
            price=payload.price,
            status=payload.status,
            hold_reason=payload.hold_reason,
            started_at=payload.started_at,
            completed_at=payload.completed_at
        )
        db.add(li)
        await db.flush()
        return li

    @staticmethod
    async def get_line_item(db: AsyncSession, line_item_id: uuid.UUID) -> LineItem:
        result = await db.execute(select(LineItem).where(LineItem.line_item_id == line_item_id))
        li = result.scalar_one_or_none()
        if not li:
            raise NotFoundError("LineItem not found")
        return li

    @staticmethod
    async def update_line_item(db: AsyncSession, line_item_id: uuid.UUID, payload: LineItemUpdate) -> LineItem:
        li = await JobService.get_line_item(db, line_item_id)

        if payload.description is not None:
            li.description = payload.description
        if payload.billing_mode is not None:
            li.billing_mode = payload.billing_mode
        if payload.price is not None:
            if li.status == 'completed' and payload.price != li.price:
                raise ValueError("Cannot modify the price of a completed line item.")
            
            wo_res = await db.execute(select(WorkOrder).options(selectinload(WorkOrder.line_items)).where(WorkOrder.work_order_id == li.work_order_id))
            wo = wo_res.scalar_one()
            other_total = sum(item.price for item in wo.line_items if item.line_item_id != li.line_item_id)
            if other_total + payload.price > wo.authorized_amount:
                raise ValueError(f"Updating this line item price ({payload.price}) exceeds the authorized amount ({wo.authorized_amount}).")
            li.price = payload.price
            
            if payload.status in ['in_progress', 'completed']:
                wo_res = await db.execute(select(WorkOrder).where(WorkOrder.work_order_id == li.work_order_id))
                wo = wo_res.scalar_one()
                if wo.status not in ['in_progress', 'active']:
                    raise ValueError(f"Cannot change line item status to {payload.status} unless the work order is active or in_progress.")

                    
            if payload.status == 'in_progress':
                from app.models.models import ChangeOrder
                co_res = await db.execute(select(ChangeOrder).where(ChangeOrder.line_item_id == line_item_id, ChangeOrder.approval_status == 'issued'))
                if co_res.scalars().first():
                    raise ValueError("Cannot start work on this line item: it has a pending change order awaiting approval.")
            li.status = payload.status
        if payload.hold_reason is not None:
            li.hold_reason = payload.hold_reason
        if payload.started_at is not None:
            li.started_at = payload.started_at
        if payload.completed_at is not None:
            li.completed_at = payload.completed_at

        await db.flush()
        return li

    @staticmethod
    async def create_labor_entry(db: AsyncSession, work_order_id: uuid.UUID, payload: LaborEntryCreate) -> LaborEntry:
        # Verify work order exists
        wo_res = await db.execute(select(WorkOrder).where(WorkOrder.work_order_id == work_order_id))
        wo = wo_res.scalar_one_or_none()
        if not wo:
            raise NotFoundError("WorkOrder not found")
        if wo.status != 'in_progress':
            raise ValueError(f"Cannot log labor: WorkOrder is '{wo.status}', not 'in_progress'.")

        # Verify line item belongs to work order
        li_res = await db.execute(
            select(LineItem)
            .where(LineItem.line_item_id == payload.line_item_id)
            .where(LineItem.work_order_id == work_order_id)
        )
        li = li_res.scalar_one_or_none()
        if not li:
            raise ValueError("LineItem not found or does not belong to this work order.")
        if li.status != 'in_progress':
            raise ValueError(f"Cannot log labor: LineItem is '{li.status}', not 'in_progress'.")

        # Verify technician exists and has active certification
        from app.models.models import Technician, Certification
        tech_res = await db.execute(
            select(Technician)
            .options(selectinload(Technician.certifications))
            .where(Technician.tech_id == payload.tech_id)
        )
        tech = tech_res.scalar_one_or_none()
        if not tech:
            raise ValueError("Technician not found.")
            
        import datetime
        has_active_cert = any(c.expiry_date >= datetime.date.today() for c in tech.certifications)
        if not has_active_cert:
            raise ValueError("Technician does not have any active certifications.")

        entry = LaborEntry(
            tech_id=payload.tech_id,
            line_item_id=payload.line_item_id,
            work_date=payload.work_date,
            hours=payload.hours,
        )
        db.add(entry)
        await db.flush()
        return entry

    @staticmethod
    async def get_labor_entries(db: AsyncSession, work_order_id: uuid.UUID) -> list[LaborEntry]:
        # Verify work order exists
        wo_res = await db.execute(select(WorkOrder).where(WorkOrder.work_order_id == work_order_id))
        if not wo_res.scalar_one_or_none():
            raise NotFoundError("WorkOrder not found")

        # Get all line item IDs for this work order
        li_res = await db.execute(
            select(LineItem.line_item_id).where(LineItem.work_order_id == work_order_id)
        )
        li_ids = [row[0] for row in li_res.all()]

        if not li_ids:
            return []

        result = await db.execute(
            select(LaborEntry).where(LaborEntry.line_item_id.in_(li_ids))
        )
        return list(result.scalars().all())

    @staticmethod
    async def create_change_order(db: AsyncSession, work_order_id: uuid.UUID, payload: ChangeOrderCreate) -> ChangeOrder:
        # Verify work order exists
        wo_res = await db.execute(select(WorkOrder).where(WorkOrder.work_order_id == work_order_id))
        if not wo_res.scalar_one_or_none():
            raise NotFoundError("WorkOrder not found")

        from app.models.models import Invoice
        inv_res = await db.execute(select(Invoice).where(Invoice.work_order_id == work_order_id))
        inv = inv_res.scalar_one_or_none()
        if inv and inv.status in ('issued', 'paid'):
            raise ValueError("Cannot submit a change order: the invoice for this work order has already been issued or paid.")

        co = ChangeOrder(
            work_order_id=work_order_id,
            line_item_id=payload.line_item_id,
            finding_id=payload.finding_id,
            reason=payload.reason,
            delta_amount=payload.delta_amount,
            approval_status=payload.approval_status
        )
        db.add(co)
        await db.flush()
        return co

    @staticmethod
    async def get_change_orders(db: AsyncSession, work_order_id: uuid.UUID) -> list[ChangeOrder]:
        res = await db.execute(select(ChangeOrder).where(ChangeOrder.work_order_id == work_order_id))
        return list(res.scalars().all())

    @staticmethod
    async def update_change_order(db: AsyncSession, change_order_id: uuid.UUID, payload: ChangeOrderUpdate) -> ChangeOrder:
        res = await db.execute(select(ChangeOrder).where(ChangeOrder.change_order_id == change_order_id))
        co = res.scalar_one_or_none()
        if not co:
            raise NotFoundError("ChangeOrder not found")

        if payload.approval_status is not None:
            old_status = co.approval_status
            new_status = payload.approval_status
            co.approval_status = new_status

            if new_status == 'approved' and old_status != 'approved':
                # Update parent work order authorized_amount
                wo_res = await db.execute(select(WorkOrder).where(WorkOrder.work_order_id == co.work_order_id))
                wo = wo_res.scalar_one()
                wo.authorized_amount += co.delta_amount

            co.approved_by = payload.approved_by
            co.approved_at = payload.approved_at or datetime.datetime.now(datetime.timezone.utc)

        if payload.decline_reason is not None:
            co.decline_reason = payload.decline_reason

        await db.flush()
        return co

    @staticmethod
    async def create_quality_check(db: AsyncSession, line_item_id: uuid.UUID, payload: QualityCheckCreate) -> QualityCheck:
        # Verify line item exists
        li = await JobService.get_line_item(db, line_item_id)
        if li.status != 'completed':
            raise ValueError(f"Cannot perform quality check: LineItem is '{li.status}', not 'completed'.")
        
        # Verify technician exists and has active certification
        from app.models.models import Technician, Certification
        tech_res = await db.execute(
            select(Technician)
            .options(selectinload(Technician.certifications))
            .where(Technician.tech_id == payload.tech_id)
        )
        tech = tech_res.scalar_one_or_none()
        if not tech:
            raise ValueError("Technician not found.")
            
        import datetime
        has_active_cert = any(c.expiry_date >= datetime.date.today() for c in tech.certifications)
        if not has_active_cert:
            raise ValueError("Technician does not have any active certifications.")

        qc = QualityCheck(
            line_item_id=line_item_id,
            tech_id=payload.tech_id,
            performed_at=payload.performed_at or datetime.datetime.now(datetime.timezone.utc),
            status=payload.status
        )
        db.add(qc)

        # If failed, move the line item back to in_progress or similar status
        if payload.status == 'failed':
            li.status = 'in_progress'
            li.hold_reason = "Quality Control Check Failed"

        await db.flush()
        return qc

    @staticmethod
    async def get_quality_checks(db: AsyncSession, line_item_id: uuid.UUID) -> list[QualityCheck]:
        res = await db.execute(select(QualityCheck).where(QualityCheck.line_item_id == line_item_id))
        return list(res.scalars().all())

