import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.models import Customer, Vehicle, Quote, WorkOrder, LineItem, ChangeOrder, QualityCheck, User
from app.schemas import (
    WorkOrderCreate, WorkOrderUpdate, WorkOrderResponse,
    LineItemCreate, LineItemUpdate, LineItemResponse,
    LaborEntryCreate, LaborEntryResponse,
    ChangeOrderCreate, ChangeOrderUpdate, ChangeOrderResponse,
    QualityCheckCreate, QualityCheckResponse
)
from fastapi_pagination import LimitOffsetPage
from fastapi_pagination.ext.sqlalchemy import apaginate
from app.routers.auth_deps import RoleChecker, get_current_user
from app.routers.pagination_deps import PaginationParams

from app.services import JobService
from app.exceptions import NotFoundError

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
    try:
        return await JobService.create_work_order(db, payload)
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
    query = select(WorkOrder).options(
        selectinload(WorkOrder.line_items),
        selectinload(WorkOrder.invoice)
    )
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
    try:
        return await JobService.get_work_order(db, work_order_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.put(
    "/work-orders/{work_order_id}", 
    response_model=WorkOrderResponse, 
    dependencies=[Depends(RoleChecker(["manager", "advisor"]))]
)
async def update_work_order(
    work_order_id: uuid.UUID, 
    payload: WorkOrderUpdate, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor"]))
):
    """
    Update work order fields (status, scheduled bay, authorized amount, etc.)
    """
    if current_user.role == "advisor" and payload.authorized_amount is not None:
        raise HTTPException(status_code=403, detail="Advisors cannot manually override the authorized amount. Manager approval required.")
        
    try:
        return await JobService.update_work_order(db, work_order_id, payload)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- LABOR ENTRY ENDPOINTS ---

@router.post(
    "/work-orders/{work_order_id}/labor-entries",
    response_model=LaborEntryResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def create_labor_entry(work_order_id: uuid.UUID, payload: LaborEntryCreate, db: AsyncSession = Depends(get_db)):
    """
    Log a labor time entry against a line item within a work order.
    """
    try:
        return await JobService.create_labor_entry(db, work_order_id, payload)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/work-orders/{work_order_id}/labor-entries",
    response_model=List[LaborEntryResponse],
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def list_labor_entries(work_order_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """
    List all labor entries for a given work order.
    """
    try:
        return await JobService.get_labor_entries(db, work_order_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
# --- LINE ITEM ENDPOINTS ---

@router.post(
    "/work-orders/{work_order_id}/line-items", 
    response_model=LineItemResponse, 
    status_code=status.HTTP_201_CREATED, 
    dependencies=[Depends(RoleChecker(["manager", "advisor"]))]
)
async def create_line_item(
    work_order_id: uuid.UUID, 
    payload: LineItemCreate, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor"]))
):
    """
    Add a task/job line item (e.g. oil change labor, part costs) to a work order.
    """
    if current_user.role == "advisor" and payload.price == 0 and not payload.is_complimentary:
        raise HTTPException(status_code=403, detail="Advisors cannot add a line item with $0 price unless marked as complimentary.")
        
    try:
        return await JobService.create_line_item(db, work_order_id, payload)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put(
    "/line-items/{line_item_id}", 
    response_model=LineItemResponse, 
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def update_line_item(line_item_id: uuid.UUID, payload: LineItemUpdate, current_user = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Update line item fields (e.g. started_at time, completed_at time, hold reason).
    """
    try:
        if current_user.role in ['advisor', 'technician'] and payload.price == 0:
            if payload.is_complimentary is not True:
                from sqlalchemy import select
                from app.models.models import LineItem
                li_res = await db.execute(select(LineItem).where(LineItem.line_item_id == line_item_id))
                li = li_res.scalar_one_or_none()
                if not li or not li.is_complimentary:
                    raise HTTPException(status_code=403, detail="Cannot set a line item price to $0 unless marked as complimentary.")

        if payload.status == 'completed' and current_user.role != 'manager':
            from sqlalchemy import select
            from app.models.models import LineItem, LaborEntry
            li_res = await db.execute(select(LineItem).where(LineItem.line_item_id == line_item_id))
            li = li_res.scalar_one_or_none()
            if li and li.billing_mode == 'hourly':
                le_res = await db.execute(select(LaborEntry).where(LaborEntry.line_item_id == line_item_id))
                if not le_res.scalars().first():
                    raise ValueError("Cannot complete an hourly line item without labor entries unless manager overrides.")

        return await JobService.update_line_item(db, line_item_id, payload)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- CHANGE ORDER ENDPOINTS ---

@router.post(
    "/work-orders/{work_order_id}/change-orders",
    response_model=ChangeOrderResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def create_change_order(work_order_id: uuid.UUID, payload: ChangeOrderCreate, db: AsyncSession = Depends(get_db)):
    """
    Submit a change order for work authorization.
    """
    try:
        return await JobService.create_change_order(db, work_order_id, payload)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/work-orders/{work_order_id}/change-orders",
    response_model=List[ChangeOrderResponse]
)
async def list_change_orders(
    work_order_id: uuid.UUID, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor", "technician", "customer"]))
):
    """
    Get all change orders associated with a work order.
    """
    if current_user.role == "customer":
        try:
            wo = await JobService.get_work_order(db, work_order_id)
            if wo.customer_id != current_user.customer_id:
                raise HTTPException(status_code=403, detail="Not authorized to view change orders for this work order.")
        except NotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
    return await JobService.get_change_orders(db, work_order_id)

@router.put(
    "/change-orders/{change_order_id}",
    response_model=ChangeOrderResponse
)
async def update_change_order(
    change_order_id: uuid.UUID, 
    payload: ChangeOrderUpdate, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor", "customer"]))
):
    """
    Approve or decline a change order.
    """
    if current_user.role == "customer":
        res = await db.execute(select(ChangeOrder).where(ChangeOrder.change_order_id == change_order_id))
        co = res.scalar_one_or_none()
        if not co:
            raise HTTPException(status_code=404, detail="Change order not found.")
        wo_res = await db.execute(select(WorkOrder).where(WorkOrder.work_order_id == co.work_order_id))
        wo = wo_res.scalar_one()
        if wo.customer_id != current_user.customer_id:
            raise HTTPException(status_code=403, detail="Not authorized to update this change order.")
            
    elif current_user.role == "advisor":
        if payload.approval_status == "approved":
            raise HTTPException(status_code=403, detail="Advisors are not authorized to approve change orders. Manager approval is required.")
            
    try:
        return await JobService.update_change_order(db, change_order_id, payload)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- QUALITY CONTROL (QC) ENDPOINTS ---

@router.post(
    "/line-items/{line_item_id}/quality-checks",
    response_model=QualityCheckResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker(["manager", "advisor"]))]
)
async def create_quality_check(line_item_id: uuid.UUID, payload: QualityCheckCreate, db: AsyncSession = Depends(get_db)):
    """
    Log a quality check result against a task.
    """
    try:
        return await JobService.create_quality_check(db, line_item_id, payload)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/line-items/{line_item_id}/quality-checks",
    response_model=List[QualityCheckResponse],
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def list_quality_checks(line_item_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """
    Get quality check logs for a line item.
    """
    return await JobService.get_quality_checks(db, line_item_id)


