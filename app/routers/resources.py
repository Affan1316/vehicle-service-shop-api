from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.models import Technician, Bay
from app.schemas import (
    TechnicianCreate, TechnicianResponse,
    BayCreate, BayUpdate, BayResponse
)
from fastapi_pagination import LimitOffsetPage
from fastapi_pagination.ext.sqlalchemy import apaginate
from app.routers.auth_deps import RoleChecker
from app.routers.pagination_deps import PaginationParams

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
    if payload.tech_id is not None:
        # Pre-verify if a technician with this custom UUID already exists to fail gracefully with 400
        ex_res = await db.execute(select(Technician).where(Technician.tech_id == payload.tech_id))
        if ex_res.scalar_one_or_none():
            raise HTTPException(status_code=400, detail=f"Technician with ID {payload.tech_id} already exists.")

    try:
        # Extract payload data and instantiate a SQLAlchemy model record
        kwargs = {
            "name": payload.name,
            "hourly_rate": payload.hourly_rate
        }
        if payload.tech_id is not None:
            kwargs["tech_id"] = payload.tech_id
            
        tech = Technician(**kwargs)
        
        # db.add schedules the object for insertion. 
        # db.flush pushes it to the database so it generates its ID, but doesn't finalize (commit) the transaction yet.
        db.add(tech)
        await db.flush()
        return tech
    except ValueError as e:
        # Catch validation errors raised inside models
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
    # apaginate runs count and select queries automatically and formats the result to match the pagination schema
    return await apaginate(db, select(Technician), params)


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
        # Convert the incoming Pydantic payload data directly to a SQLAlchemy model instance
        bay = Bay(
            bay_type=payload.bay_type,
            status=payload.status,
            current_work_order_id=payload.current_work_order_id,
            held_until=payload.held_until
        )
        db.add(bay)
        await db.flush()
        return bay
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/bays", 
    response_model=LimitOffsetPage[BayResponse], 
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def list_bays(params: PaginationParams = Depends(), db: AsyncSession = Depends(get_db)):
    """
    List service bays using pagination.
    """
    return await apaginate(db, select(Bay), params)
