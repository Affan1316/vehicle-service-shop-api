import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.models import Customer, Vehicle, Quote, WorkOrder, LineItem
from app.schemas import (
    WorkOrderCreate, WorkOrderUpdate, WorkOrderResponse,
    LineItemCreate, LineItemUpdate, LineItemResponse
)
from fastapi_pagination import LimitOffsetPage
from fastapi_pagination.ext.sqlalchemy import apaginate
from app.routers.auth_deps import RoleChecker
from app.routers.pagination_deps import PaginationParams

router = APIRouter()

# --- WORK ORDER ENDPOINTS ---

@router.post(
    "/work-orders", 
    response_model=WorkOrderResponse, 
    status_code=status.HTTP_201_CREATED, 
    dependencies=[Depends(RoleChecker(["manager", "advisor"]))]
)
async def create_work_order(payload: WorkOrderCreate, db: AsyncSession = Depends(get_db)):
    """
    Generate a new work order from an approved quote.
    """
    # 1. VALIDATIONS
    # Verify owner customer exists
    cust_res = await db.execute(select(Customer).where(Customer.customer_id == payload.customer_id))
    if not cust_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Customer does not exist.")
    
    # Verify target vehicle exists
    veh_res = await db.execute(select(Vehicle).where(Vehicle.vin == payload.vehicle_id))
    if not veh_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Vehicle does not exist.")

    # Verify origin quote exists
    q_res = await db.execute(select(Quote).where(Quote.quote_id == payload.quote_id))
    if not q_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Quote does not exist.")

    # 2. SAVE WORK ORDER
    try:
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
        
        # 3. RELOAD RELATIONSHIPS
        # We must load associated line_items explicitly because the 'total_cost' property 
        # on WorkOrder references 'self.line_items' which would throw a LazyLoading error otherwise.
        q = await db.execute(
            select(WorkOrder)
            .options(selectinload(WorkOrder.line_items))
            .where(WorkOrder.work_order_id == wo.work_order_id)
        )
        return q.scalar_one()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/work-orders", 
    response_model=LimitOffsetPage[WorkOrderResponse], 
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def list_work_orders(params: PaginationParams = Depends(), db: AsyncSession = Depends(get_db)):
    """
    List all work orders with pagination. Eager loads associated line items.
    """
    query = select(WorkOrder).options(selectinload(WorkOrder.line_items))
    return await apaginate(db, query, params)

@router.get(
    "/work-orders/{work_order_id}", 
    response_model=WorkOrderResponse, 
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def get_work_order(work_order_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """
    Retrieve details of a single work order by ID.
    """
    result = await db.execute(
        select(WorkOrder)
        .options(selectinload(WorkOrder.line_items))
        .where(WorkOrder.work_order_id == work_order_id)
    )
    wo = result.scalar_one_or_none()
    if not wo:
        raise HTTPException(status_code=404, detail="WorkOrder not found")
    return wo

@router.put(
    "/work-orders/{work_order_id}", 
    response_model=WorkOrderResponse, 
    dependencies=[Depends(RoleChecker(["manager", "advisor"]))]
)
async def update_work_order(work_order_id: uuid.UUID, payload: WorkOrderUpdate, db: AsyncSession = Depends(get_db)):
    """
    Update work order fields (status, scheduled bay, authorized amount, etc.)
    """
    result = await db.execute(
        select(WorkOrder)
        .options(selectinload(WorkOrder.line_items))
        .where(WorkOrder.work_order_id == work_order_id)
    )
    wo = result.scalar_one_or_none()
    if not wo:
        raise HTTPException(status_code=404, detail="WorkOrder not found")
    
    try:
        # Dynamically apply changes only if fields are sent in the payload
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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- LINE ITEM ENDPOINTS ---

@router.post(
    "/work-orders/{work_order_id}/line-items", 
    response_model=LineItemResponse, 
    status_code=status.HTTP_201_CREATED, 
    dependencies=[Depends(RoleChecker(["manager", "advisor"]))]
)
async def create_line_item(work_order_id: uuid.UUID, payload: LineItemCreate, db: AsyncSession = Depends(get_db)):
    """
    Add a task/job line item (e.g. oil change labor, part costs) to a work order.
    """
    # Verify target parent work order exists in database first
    wo_res = await db.execute(select(WorkOrder).where(WorkOrder.work_order_id == work_order_id))
    if not wo_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="WorkOrder not found")
    
    try:
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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put(
    "/line-items/{line_item_id}", 
    response_model=LineItemResponse, 
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def update_line_item(line_item_id: uuid.UUID, payload: LineItemUpdate, db: AsyncSession = Depends(get_db)):
    """
    Update line item fields (e.g. started_at time, completed_at time, hold reason).
    """
    result = await db.execute(select(LineItem).where(LineItem.line_item_id == line_item_id))
    li = result.scalar_one_or_none()
    if not li:
        raise HTTPException(status_code=404, detail="LineItem not found")
    
    try:
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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
