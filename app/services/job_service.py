import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.models import Customer, Vehicle, Quote, WorkOrder, LineItem, LaborEntry, Technician
from app.schemas.schemas import WorkOrderCreate, WorkOrderUpdate, LineItemCreate, LineItemUpdate, LaborEntryCreate
from app.exceptions import NotFoundError


class JobService:
    @staticmethod
    async def create_work_order(db: AsyncSession, payload: WorkOrderCreate) -> WorkOrder:
        cust_res = await db.execute(select(Customer).where(Customer.customer_id == payload.customer_id))
        if not cust_res.scalar_one_or_none():
            raise ValueError("Customer does not exist.")
        
        veh_res = await db.execute(select(Vehicle).where(Vehicle.vin == payload.vehicle_id))
        if not veh_res.scalar_one_or_none():
            raise ValueError("Vehicle does not exist.")

        q_res = await db.execute(select(Quote).where(Quote.quote_id == payload.quote_id))
        if not q_res.scalar_one_or_none():
            raise ValueError("Quote does not exist.")

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
            .options(selectinload(WorkOrder.line_items))
            .where(WorkOrder.work_order_id == wo.work_order_id)
        )
        return result.scalar_one()

    @staticmethod
    async def get_work_order(db: AsyncSession, work_order_id: uuid.UUID) -> WorkOrder:
        result = await db.execute(
            select(WorkOrder)
            .options(selectinload(WorkOrder.line_items))
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
        wo_res = await db.execute(select(WorkOrder).where(WorkOrder.work_order_id == work_order_id))
        if not wo_res.scalar_one_or_none():
            raise NotFoundError("WorkOrder not found")

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
            li.price = payload.price
        if payload.status is not None:
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
        if not wo_res.scalar_one_or_none():
            raise NotFoundError("WorkOrder not found")

        # Verify line item belongs to work order
        li_res = await db.execute(
            select(LineItem)
            .where(LineItem.line_item_id == payload.line_item_id)
            .where(LineItem.work_order_id == work_order_id)
        )
        if not li_res.scalar_one_or_none():
            raise ValueError("LineItem not found or does not belong to this work order.")

        # Verify technician exists
        tech_res = await db.execute(select(Technician).where(Technician.tech_id == payload.tech_id))
        if not tech_res.scalar_one_or_none():
            raise ValueError("Technician not found.")

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

