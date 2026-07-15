import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.models import Customer, Vehicle, Appointment, Visit, User
from app.schemas import (
    AppointmentCreate, AppointmentUpdate, AppointmentResponse,
    VisitCreate, VisitUpdate, VisitResponse
)
from fastapi_pagination import LimitOffsetPage
from fastapi_pagination.ext.sqlalchemy import apaginate
from app.routers.auth_deps import RoleChecker
from app.routers.pagination_deps import PaginationParams

from app.services import VisitService
from app.exceptions import NotFoundError

router = APIRouter()

# --- APPOINTMENT ENDPOINTS ---

@router.post(
    "/appointments", 
    response_model=AppointmentResponse, 
    status_code=status.HTTP_201_CREATED, 
    dependencies=[Depends(RoleChecker(["manager", "advisor"]))]
)
async def create_appointment(payload: AppointmentCreate, db: AsyncSession = Depends(get_db)):
    """
    Book a new customer appointment. Checks if customer and vehicle exist first.
    """
    try:
        return await VisitService.create_appointment(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/appointments", 
    response_model=LimitOffsetPage[AppointmentResponse], 
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def list_appointments(params: PaginationParams = Depends(), db: AsyncSession = Depends(get_db)):
    """
    List appointments with pagination.
    """
    return await apaginate(db, select(Appointment), params)

@router.put(
    "/appointments/{appointment_id}", 
    response_model=AppointmentResponse, 
    dependencies=[Depends(RoleChecker(["manager", "advisor"]))]
)
async def update_appointment(appointment_id: uuid.UUID, payload: AppointmentUpdate, db: AsyncSession = Depends(get_db)):
    """
    Update appointment details.
    """
    try:
        return await VisitService.update_appointment(db, appointment_id, payload)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# --- VISIT ENDPOINTS ---

@router.post(
    "/visits", 
    response_model=VisitResponse, 
    status_code=status.HTTP_201_CREATED, 
    dependencies=[Depends(RoleChecker(["manager", "advisor"]))]
)
async def create_visit(payload: VisitCreate, db: AsyncSession = Depends(get_db)):
    """
    Record a new vehicle check-in visit.
    """
    try:
        return await VisitService.create_visit(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/visits", 
    response_model=LimitOffsetPage[VisitResponse]
)
async def list_visits(
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor", "technician", "customer"]))
):
    """
    List vehicle service visits with pagination.
    """
    query = select(Visit)
    if current_user.role == "customer":
        if current_user.customer_id is None:
            raise HTTPException(status_code=400, detail="User is not linked to a customer profile.")
        query = query.where(Visit.customer_id == current_user.customer_id)
    return await apaginate(db, query, params)

@router.put(
    "/visits/{visit_id}", 
    response_model=VisitResponse, 
    dependencies=[Depends(RoleChecker(["manager", "advisor"]))]
)
async def update_visit(visit_id: uuid.UUID, payload: VisitUpdate, db: AsyncSession = Depends(get_db)):
    """
    Update visit details (e.g. check-out times).
    """
    try:
        return await VisitService.update_visit(db, visit_id, payload)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

