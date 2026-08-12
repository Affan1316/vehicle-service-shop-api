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
        veh = veh_res.scalar_one_or_none()
        if not veh:
            raise ValueError("Vehicle does not exist.")
        if veh.customer_id != payload.customer_id:
            raise ValueError("Vehicle does not belong to the specified customer.")

        appt = Appointment(
            customer_id=payload.customer_id,
            vehicle_id=payload.vehicle_id,
            requested_date=payload.requested_date,
            confirmed_date=payload.confirmed_date,
            status=payload.status,
            bay_id=payload.bay_id,
            preferred_time=payload.preferred_time
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
        if payload.preferred_time is not None:
            appt.preferred_time = payload.preferred_time
            
        if appt.status == 'confirmed' and appt.bay_id is not None:
            from app.models.models import Bay
            bay_res = await db.execute(select(Bay).where(Bay.bay_id == appt.bay_id))
            bay = bay_res.scalar_one_or_none()
            if not bay:
                raise ValueError("Bay does not exist.")
            if bay.status != 'available' and bay.status != 'confirmed':
                # Note: The event listener in models.py automatically sets bay.status to 'confirmed'
                # if it was available. We just need to prevent confirming into an occupied/held bay.
                # Actually, to be safe, if we are transitioning to confirmed, we must ensure it's available.
                if payload.status == 'confirmed':
                    if bay.status != 'available':
                        raise ValueError(f"Cannot confirm appointment: Bay is currently {bay.status}")

        await db.flush()
        return appt

    @staticmethod
    async def create_visit(db: AsyncSession, payload: VisitCreate) -> Visit:
        cust_res = await db.execute(select(Customer).where(Customer.customer_id == payload.customer_id))
        if not cust_res.scalar_one_or_none():
            raise ValueError("Customer does not exist.")
        
        veh_res = await db.execute(select(Vehicle).where(Vehicle.vin == payload.vehicle_id))
        veh = veh_res.scalar_one_or_none()
        if not veh:
            raise ValueError("Vehicle does not exist.")
        if veh.customer_id != payload.customer_id:
            raise ValueError("Vehicle does not belong to the specified customer.")

        walk_in = False
        if payload.appointment_id is None:
            import datetime
            today = datetime.datetime.now(datetime.timezone.utc).date()
            appt_res = await db.execute(select(Appointment).where(
                Appointment.vehicle_id == payload.vehicle_id,
                Appointment.requested_date == today,
                Appointment.status.in_(['requested', 'confirmed'])
            ))
            appts = appt_res.scalars().all()
            if len(appts) == 1:
                payload.appointment_id = appts[0].appointment_id
                appts[0].status = 'checked_in'
            else:
                walk_in = True
        else:
            appt_res = await db.execute(select(Appointment).where(Appointment.appointment_id == payload.appointment_id))
            appt = appt_res.scalar_one_or_none()
            if not appt:
                raise ValueError("Appointment does not exist.")
            appt.status = 'checked_in'
                
        # Check for existing active visit
        active_visit_res = await db.execute(
            select(Visit).where(
                (Visit.vehicle_id == payload.vehicle_id) & 
                (Visit.status != 'completed')
            )
        )
        if active_visit_res.scalar_one_or_none():
            raise ValueError("Vehicle is already checked in with an active visit.")

        visit = Visit(
            vehicle_id=payload.vehicle_id,
            customer_id=payload.customer_id,
            appointment_id=payload.appointment_id,
            checked_in_at=payload.checked_in_at,
            status=payload.status,
            walk_in=walk_in
        )
        db.add(visit)

        if payload.appointment_id:
            appt_res = await db.execute(select(Appointment).where(Appointment.appointment_id == payload.appointment_id))
            appt = appt_res.scalar_one_or_none()
            if appt and appt.status == 'confirmed':
                appt.status = 'checked_in'

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
            if payload.status != visit.status:
                valid_transitions = {
                    'checked_in': ['in_diagnosis', 'awaiting_quote', 'completed'],
                    'in_diagnosis': ['awaiting_quote', 'in_service', 'completed'],
                    'awaiting_quote': ['in_service', 'completed'],
                    'in_service': ['awaiting_pickup', 'completed'],
                    'awaiting_pickup': ['completed'],
                    'completed': []
                }
                allowed_next = valid_transitions.get(visit.status, [])
                if payload.status not in allowed_next:
                    raise ValueError(f"Invalid visit state transition from '{visit.status}' to '{payload.status}'.")

            if payload.status == 'in_service':
                from app.models.models import WorkOrder
                wo_res = await db.execute(select(WorkOrder.work_order_id).where(WorkOrder.visit_id == visit_id))
                if not wo_res.all():
                    raise ValueError("Cannot transition to in_service: No active work order exists for this visit.")
            elif payload.status == 'awaiting_pickup':
                from app.models.models import WorkOrder, ChangeOrder
                wo_res = await db.execute(select(WorkOrder.work_order_id).where(WorkOrder.visit_id == visit_id))
                wo_ids = [row[0] for row in wo_res.all()]
                if wo_ids:
                    co_res = await db.execute(select(ChangeOrder).where(ChangeOrder.work_order_id.in_(wo_ids), ChangeOrder.approval_status == 'issued'))
                    pending_cos = co_res.scalars().all()
                    if pending_cos:
                        raise ValueError(f"Cannot transition to awaiting_pickup: {len(pending_cos)} pending change order(s) must be resolved first.")
            visit.status = payload.status
        if payload.checked_out_at is not None:
            from app.models.models import WorkOrder, Invoice
            wo_res = await db.execute(select(WorkOrder.work_order_id).where(WorkOrder.visit_id == visit_id))
            wo_ids = [row[0] for row in wo_res.all()]
            
            if wo_ids:
                inv_res = await db.execute(select(Invoice).where(Invoice.work_order_id.in_(wo_ids)))
                invoices = inv_res.scalars().all()
                for inv in invoices:
                    if inv.status != 'paid':
                        raise ValueError(f"Cannot check out vehicle: Invoice {inv.invoice_id} is not fully paid.")
                        
            from app.models.models import Quote
            quote_res = await db.execute(select(Quote).where(Quote.visit_id == visit_id, Quote.status.in_(['draft', 'issued'])))
            quotes = quote_res.scalars().all()
            for q in quotes:
                q.status = 'expired'
                
            visit.checked_out_at = payload.checked_out_at

        await db.flush()
        return visit
