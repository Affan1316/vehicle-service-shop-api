import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.models import Technician, Bay
from app.schemas import (
    TechnicianCreate, TechnicianResponse,
    BayCreate, BayUpdate, BayResponse,
    CertificationCreate, CertificationResponse
)
from fastapi_pagination import LimitOffsetPage
from fastapi_pagination.ext.sqlalchemy import apaginate
from app.routers.auth_deps import RoleChecker
from app.routers.pagination_deps import PaginationParams

from app.services import ResourceService

router = APIRouter()

# --- TECHNICIAN ENDPOINTS ---

@router.post(
    "/technicians", 
    response_model=TechnicianResponse, 
    status_code=status.HTTP_201_CREATED, 
    dependencies=[Depends(RoleChecker(["manager"]))]  # Enforces that only managers can call this route
)
async def create_technician(payload: TechnicianCreate, db: AsyncSession = Depends(get_db)):
    """
    Create a new technician record in the database.
    """
    try:
        return await ResourceService.create_technician(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/technicians/{tech_id}/certifications", 
    response_model=CertificationResponse, 
    status_code=status.HTTP_201_CREATED, 
    dependencies=[Depends(RoleChecker(["manager"]))]
)
async def add_technician_certification(tech_id: uuid.UUID, payload: CertificationCreate, db: AsyncSession = Depends(get_db)):
    """
    Add a certification to an existing technician.
    """
    try:
        return await ResourceService.add_technician_certification(db, tech_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/technicians", 
    response_model=LimitOffsetPage[TechnicianResponse], 
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def list_technicians(params: PaginationParams = Depends(), db: AsyncSession = Depends(get_db)):
    """
    List all technicians using offset-limit pagination.
    """
    from sqlalchemy.orm import selectinload
    return await apaginate(db, select(Technician).options(selectinload(Technician.certifications)), params)


# --- BAY ENDPOINTS ---

@router.post(
    "/bays", 
    response_model=BayResponse, 
    status_code=status.HTTP_201_CREATED, 
    dependencies=[Depends(RoleChecker(["manager"]))]
)
async def create_bay(payload: BayCreate, db: AsyncSession = Depends(get_db)):
    """
    Create a new service bay.
    """
    try:
        return await ResourceService.create_bay(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/bays", 
    response_model=LimitOffsetPage[BayResponse], 
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def list_bays(params: PaginationParams = Depends(), db: AsyncSession = Depends(get_db)):
    """
    List service bays using pagination. Auto-releases expired holds.
    """
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    
    # Auto-release expired bay holds
    expired_bays_res = await db.execute(
        select(Bay).where(
            (Bay.status == 'held') & 
            (Bay.held_until < now)
        )
    )
    for bay in expired_bays_res.scalars().all():
        bay.status = 'available'
        bay.held_until = None
        
    await db.flush()
    
    return await apaginate(db, select(Bay), params)

@router.put(
    "/bays/{bay_id}", 
    response_model=BayResponse, 
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def update_bay(
    bay_id: uuid.UUID, 
    payload: BayUpdate, 
    db: AsyncSession = Depends(get_db)
):
    """
    Update a service bay status or work order allocation.
    """
    try:
        return await ResourceService.update_bay(db, bay_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

