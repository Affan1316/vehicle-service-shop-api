import uuid
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.models import Customer, Appointment, Visit, User
from app.schemas import (
    AppointmentCreate, AppointmentUpdate, AppointmentResponse,
    VisitCreate, VisitUpdate, VisitResponse
)
from fastapi_pagination import LimitOffsetPage
from fastapi_pagination.ext.sqlalchemy import apaginate
from app.routers.auth_deps import RoleChecker
from app.routers.pagination_deps import PaginationParams

from app.services import VisitService, EmailService, AuditService
from app.exceptions import NotFoundError

router = APIRouter()

# --- APPOINTMENT ENDPOINTS ---

@router.post(
    "/appointments",
    response_model=AppointmentResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_appointment(
    payload: AppointmentCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor", "customer"]))
):
    """
    Book a new customer appointment. Checks if customer and vehicle exist first.
    """
    if current_user.role == "customer":
        if current_user.customer_id != payload.customer_id:
            raise HTTPException(status_code=403, detail="Not authorized to book appointments for other customers.")
    try:
        appt = await VisitService.create_appointment(db, payload)
        await AuditService.log_create(
            db, "appointment", str(appt.appointment_id),
            current_user.user_id, current_user.username,
            {"vehicle_id": appt.vehicle_id, "requested_date": str(appt.requested_date)}
        )
        # Send confirmation email if customer has email configured
        cust_res = await db.execute(select(Customer).where(Customer.customer_id == payload.customer_id))
        cust = cust_res.scalar_one_or_none()
        if cust and cust.email:
            background_tasks.add_task(
                EmailService.send_appointment_reminder,
                cust.email,
                cust.name,
                str(appt.requested_date),
                appt.vehicle_id
            )
        return appt
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/appointments",
    response_model=LimitOffsetPage[AppointmentResponse]
)
async def list_appointments(
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor", "technician", "customer"]))
):
    """
    List appointments with pagination.
    """
    query = select(Appointment)
    if current_user.role == "customer":
        if current_user.customer_id is None:
            raise HTTPException(status_code=400, detail="User is not linked to a customer profile.")
        query = query.where(Appointment.customer_id == current_user.customer_id)
    return await apaginate(db, query, params)

@router.put(
    "/appointments/{appointment_id}",
    response_model=AppointmentResponse,
)
async def update_appointment(
    appointment_id: uuid.UUID,
    payload: AppointmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor", "customer"]))
):
    """
    Update appointment details.
    Customers may only cancel their own appointments.
    """
    if current_user.role == "customer":
        # Customers can only cancel, not confirm or change other fields
        if payload.status != "cancelled":
            raise HTTPException(status_code=403, detail="Customers may only cancel appointments.")
        # Verify ownership
        result = await db.execute(select(Appointment).where(Appointment.appointment_id == appointment_id))
        appointment = result.scalar_one_or_none()
        if appointment is None:
            raise HTTPException(status_code=404, detail="Appointment not found.")
        if appointment.customer_id != current_user.customer_id:
            raise HTTPException(status_code=403, detail="Not authorized to modify this appointment.")
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

