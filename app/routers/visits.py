import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.models import Customer, Vehicle, Appointment, Visit
from app.schemas import (
    AppointmentCreate, AppointmentUpdate, AppointmentResponse,
    VisitCreate, VisitUpdate, VisitResponse
)
from fastapi_pagination import LimitOffsetPage
from fastapi_pagination.ext.sqlalchemy import apaginate
from app.routers.auth_deps import RoleChecker
from app.routers.pagination_deps import PaginationParams

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
    # 1. VALIDATION
    # Make sure the customer ID exists in our customer database
    cust_res = await db.execute(select(Customer).where(Customer.customer_id == payload.customer_id))
    if not cust_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Customer does not exist.")
    
    # Make sure the vehicle vin exists in our vehicle database
    veh_res = await db.execute(select(Vehicle).where(Vehicle.vin == payload.vehicle_id))
    if not veh_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Vehicle does not exist.")

    # 2. SAVE APPOINTMENT
    try:
        appt = Appointment(
            customer_id=payload.customer_id,
            vehicle_id=payload.vehicle_id,
            requested_date=payload.requested_date,
            confirmed_date=payload.confirmed_date,
            status=payload.status,
            bay_id=payload.bay_id
        )
        db.add(appt)
        await db.flush()
        return appt
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
    # 1. FIND THE APPOINTMENT
    result = await db.execute(select(Appointment).where(Appointment.appointment_id == appointment_id))
    appt = result.scalar_one_or_none()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    # 2. APPLY CHANGES DYNAMICALLY
    try:
        if payload.customer_id is not None:
            # Check customer exists
            cust_res = await db.execute(select(Customer).where(Customer.customer_id == payload.customer_id))
            if not cust_res.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Target customer does not exist.")
            appt.customer_id = payload.customer_id
        if payload.vehicle_id is not None:
            # Check vehicle exists
            veh_res = await db.execute(select(Vehicle).where(Vehicle.vin == payload.vehicle_id))
            if not veh_res.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Target vehicle does not exist.")
            appt.vehicle_id = payload.vehicle_id
        if payload.requested_date is not None:
            appt.requested_date = payload.requested_date
        if payload.confirmed_date is not None:
            appt.confirmed_date = payload.confirmed_date
        if payload.status is not None:
            appt.status = payload.status
        if payload.bay_id is not None:
            appt.bay_id = payload.bay_id
            
        await db.flush()
        return appt
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
    # Validate Customer exists
    cust_res = await db.execute(select(Customer).where(Customer.customer_id == payload.customer_id))
    if not cust_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Customer does not exist.")
    
    # Validate Vehicle exists
    veh_res = await db.execute(select(Vehicle).where(Vehicle.vin == payload.vehicle_id))
    if not veh_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Vehicle does not exist.")

    # Validate Appointment if provided
    if payload.appointment_id is not None:
        appt_res = await db.execute(select(Appointment).where(Appointment.appointment_id == payload.appointment_id))
        if not appt_res.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Appointment does not exist.")

    try:
        visit = Visit(
            vehicle_id=payload.vehicle_id,
            customer_id=payload.customer_id,
            appointment_id=payload.appointment_id,
            checked_in_at=payload.checked_in_at,
            status=payload.status
        )
        db.add(visit)
        await db.flush()
        return visit
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/visits", 
    response_model=LimitOffsetPage[VisitResponse], 
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def list_visits(params: PaginationParams = Depends(), db: AsyncSession = Depends(get_db)):
    """
    List vehicle service visits with pagination.
    """
    return await apaginate(db, select(Visit), params)

@router.put(
    "/visits/{visit_id}", 
    response_model=VisitResponse, 
    dependencies=[Depends(RoleChecker(["manager", "advisor"]))]
)
async def update_visit(visit_id: uuid.UUID, payload: VisitUpdate, db: AsyncSession = Depends(get_db)):
    """
    Update visit details (e.g. check-out times).
    """
    result = await db.execute(select(Visit).where(Visit.visit_id == visit_id))
    visit = result.scalar_one_or_none()
    if not visit:
        raise HTTPException(status_code=404, detail="Visit not found")
    
    try:
        if payload.status is not None:
            visit.status = payload.status
        if payload.checked_out_at is not None:
            # Setting checked_out_at automatically sets status to 'completed' via models events
            visit.checked_out_at = payload.checked_out_at
            
        await db.flush()
        return visit
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
