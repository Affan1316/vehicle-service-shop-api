import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.schemas import (
    CannedServiceCreate, CannedServiceUpdate, CannedServiceResponse, LineItemResponse
)
from app.routers.auth_deps import RoleChecker
from app.services import MenuService

router = APIRouter(tags=["Service Menu & Canned Services"])


@router.get(
    "/service-menu",
    response_model=List[CannedServiceResponse],
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician", "customer"]))]
)
async def list_service_menu(
    active_only: bool = Query(True, description="Filter to active services only"),
    db: AsyncSession = Depends(get_db)
):
    """
    List all canned service packages and menu items.
    """
    return await MenuService.list_canned_services(db, active_only=active_only)


@router.post(
    "/service-menu",
    response_model=CannedServiceResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker(["manager"]))]
)
async def create_canned_service(
    payload: CannedServiceCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new canned service template in the shop catalog. (Manager only)
    """
    try:
        return await MenuService.create_canned_service(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/service-menu/{service_id}",
    response_model=CannedServiceResponse,
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician", "customer"]))]
)
async def get_canned_service(
    service_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve details of a specific canned service by ID.
    """
    return await MenuService.get_canned_service(db, service_id)


@router.put(
    "/service-menu/{service_id}",
    response_model=CannedServiceResponse,
    dependencies=[Depends(RoleChecker(["manager"]))]
)
async def update_canned_service(
    service_id: uuid.UUID,
    payload: CannedServiceUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update an existing canned service template. (Manager only)
    """
    try:
        return await MenuService.update_canned_service(db, service_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/work-orders/{work_order_id}/apply-service/{service_id}",
    response_model=LineItemResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def apply_service_to_work_order(
    work_order_id: uuid.UUID,
    service_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Quickly add a pre-configured canned service as a LineItem on a WorkOrder.
    """
    try:
        return await MenuService.apply_to_work_order(db, work_order_id, service_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
