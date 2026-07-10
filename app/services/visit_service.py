import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.models import Customer, Vehicle, Appointment, Visit
from app.schemas.schemas import AppointmentCreate, AppointmentUpdate, VisitCreate, VisitUpdate
from app.exceptions import NotFoundError


class VisitService:
    @staticmethod
    async def create_appointment(db: AsyncSession, payload: AppointmentCreate) -> Appointment:
        cust_res = await db.execute(select(Customer).where(Customer.customer_id == payload.customer_id))
        if not cust_res.scalar_one_or_none():
            raise ValueError("Customer does not exist.")
        
        veh_res = await db.execute(select(Vehicle).where(Vehicle.vin == payload.vehicle_id))
        if not veh_res.scalar_one_or_none():
            raise ValueError("Vehicle does not exist.")

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

    @staticmethod
    async def get_appointment(db: AsyncSession, appointment_id: uuid.UUID) -> Appointment:
        result = await db.execute(select(Appointment).where(Appointment.appointment_id == appointment_id))
        appt = result.scalar_one_or_none()
        if not appt:
            raise NotFoundError("Appointment not found")
        return appt

    @staticmethod
    async def update_appointment(db: AsyncSession, appointment_id: uuid.UUID, payload: AppointmentUpdate) -> Appointment:
        appt = await VisitService.get_appointment(db, appointment_id)

        if payload.customer_id is not None:
            cust_res = await db.execute(select(Customer).where(Customer.customer_id == payload.customer_id))
            if not cust_res.scalar_one_or_none():
                raise ValueError("Target customer does not exist.")
            appt.customer_id = payload.customer_id
        if payload.vehicle_id is not None:
            veh_res = await db.execute(select(Vehicle).where(Vehicle.vin == payload.vehicle_id))
            if not veh_res.scalar_one_or_none():
                raise ValueError("Target vehicle does not exist.")
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

    @staticmethod
    async def create_visit(db: AsyncSession, payload: VisitCreate) -> Visit:
        cust_res = await db.execute(select(Customer).where(Customer.customer_id == payload.customer_id))
        if not cust_res.scalar_one_or_none():
            raise ValueError("Customer does not exist.")
        
        veh_res = await db.execute(select(Vehicle).where(Vehicle.vin == payload.vehicle_id))
        if not veh_res.scalar_one_or_none():
            raise ValueError("Vehicle does not exist.")

        if payload.appointment_id is not None:
            appt_res = await db.execute(select(Appointment).where(Appointment.appointment_id == payload.appointment_id))
            if not appt_res.scalar_one_or_none():
                raise ValueError("Appointment does not exist.")

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

    @staticmethod
    async def get_visit(db: AsyncSession, visit_id: uuid.UUID) -> Visit:
        result = await db.execute(select(Visit).where(Visit.visit_id == visit_id))
        visit = result.scalar_one_or_none()
        if not visit:
            raise NotFoundError("Visit not found")
        return visit

    @staticmethod
    async def update_visit(db: AsyncSession, visit_id: uuid.UUID, payload: VisitUpdate) -> Visit:
        visit = await VisitService.get_visit(db, visit_id)

        if payload.status is not None:
            visit.status = payload.status
        if payload.checked_out_at is not None:
            visit.checked_out_at = payload.checked_out_at

        await db.flush()
        return visit
