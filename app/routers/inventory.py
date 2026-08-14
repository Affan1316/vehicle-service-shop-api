import uuid
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.models import Part, Vendor, PurchaseOrder, PartInstance
from app.schemas.schemas import (
    PartCreate, PartUpdate, PartResponse,
    VendorCreate, VendorResponse,
    PurchaseOrderCreate, PurchaseOrderResponse,
    PartInstanceUpdate, PartInstanceResponse
)
from fastapi_pagination import LimitOffsetPage
from fastapi_pagination.ext.sqlalchemy import apaginate
from app.routers.auth_deps import RoleChecker
from app.routers.pagination_deps import PaginationParams
from app.services import InventoryService, SearchService

router = APIRouter()

# --- PART CATALOG ENDPOINTS ---

@router.post(
    "/parts",
    response_model=PartResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker(["manager", "advisor"]))]
)
async def create_part(payload: PartCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await InventoryService.create_part(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/parts/search",
    response_model=List[PartResponse],
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def search_parts(
    q: str = Query(..., min_length=1, description="Search by name, part number, or category"),
    db: AsyncSession = Depends(get_db)
):
    """
    Search parts catalog by name, part number, or category.
    """
    return await SearchService.search_parts(db, q)

@router.get(
    "/parts",
    response_model=LimitOffsetPage[PartResponse],
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def list_parts(params: PaginationParams = Depends(), db: AsyncSession = Depends(get_db)):
    return await apaginate(db, select(Part), params)

@router.get(
    "/parts/{part_id}",
    response_model=PartResponse,
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def get_part(part_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    try:
        return await InventoryService.get_part(db, part_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.put(
    "/parts/{part_id}",
    response_model=PartResponse,
    dependencies=[Depends(RoleChecker(["manager", "advisor"]))]
)
async def update_part(part_id: uuid.UUID, payload: PartUpdate, db: AsyncSession = Depends(get_db)):
    try:
        return await InventoryService.update_part(db, part_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- VENDOR ENDPOINTS ---

@router.post(
    "/vendors",
    response_model=VendorResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker(["manager"]))]
)
async def create_vendor(payload: VendorCreate, db: AsyncSession = Depends(get_db)):
    try:
        return await InventoryService.create_vendor(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/vendors",
    response_model=LimitOffsetPage[VendorResponse],
    dependencies=[Depends(RoleChecker(["manager", "advisor"]))]
)
async def list_vendors(params: PaginationParams = Depends(), db: AsyncSession = Depends(get_db)):
    return await apaginate(db, select(Vendor), params)

# --- PURCHASE ORDER ENDPOINTS ---

class POCreateWithItems(PurchaseOrderCreate):
    items: List[Dict[str, Any]]  # List of dicts representing parts and ordered qty

@router.post(
    "/purchase-orders",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker(["manager"]))]
)
async def create_purchase_order(payload: POCreateWithItems, db: AsyncSession = Depends(get_db)):
    try:
        # Separate line item details from the PO creation payload
        items = payload.items
        return await InventoryService.create_purchase_order(db, payload, items)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/purchase-orders",
    response_model=LimitOffsetPage[PurchaseOrderResponse],
    dependencies=[Depends(RoleChecker(["manager", "advisor"]))]
)
async def list_purchase_orders(params: PaginationParams = Depends(), db: AsyncSession = Depends(get_db)):
    return await apaginate(db, select(PurchaseOrder), params)

# --- PART INSTANCE ENDPOINTS ---

@router.get(
    "/part-instances",
    response_model=LimitOffsetPage[PartInstanceResponse],
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def list_part_instances(params: PaginationParams = Depends(), db: AsyncSession = Depends(get_db)):
    return await apaginate(db, select(PartInstance), params)

@router.put(
    "/part-instances/{instance_id}",
    response_model=PartInstanceResponse,
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def update_part_instance(
    instance_id: uuid.UUID,
    payload: PartInstanceUpdate,
    db: AsyncSession = Depends(get_db)
):
    try:
        return await InventoryService.update_part_instance(db, instance_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
