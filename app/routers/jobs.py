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
    try:
        return await JobService.get_work_order(db, work_order_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.put(
    "/work-orders/{work_order_id}", 
    response_model=WorkOrderResponse, 
    dependencies=[Depends(RoleChecker(["manager", "advisor"]))]
)
async def update_work_order(work_order_id: uuid.UUID, payload: WorkOrderUpdate, db: AsyncSession = Depends(get_db)):
    """
    Update work order fields (status, scheduled bay, authorized amount, etc.)
    """
    try:
        return await JobService.update_work_order(db, work_order_id, payload)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
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
async def update_line_item(line_item_id: uuid.UUID, payload: LineItemUpdate, db: AsyncSession = Depends(get_db)):
    """
    Update line item fields (e.g. started_at time, completed_at time, hold reason).
    """
    try:
        return await JobService.update_line_item(db, line_item_id, payload)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

