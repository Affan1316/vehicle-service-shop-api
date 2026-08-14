import uuid
import decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.models import Customer, Vehicle, Appointment, Visit, Quote, WorkOrder, Invoice, Payment
from app.schemas.schemas import CustomerCreate, CustomerUpdate, VehicleCreate, VehicleUpdate
from app.exceptions import NotFoundError


class CustomerService:
    @staticmethod
    async def create_customer(db: AsyncSession, payload: CustomerCreate) -> Customer:
        customer = Customer(
            name=payload.name,
            customer_type=payload.customer_type,
            billing_address=payload.billing_address,
            tax_exempt=payload.tax_exempt,
            phone=payload.phone,
            email=payload.email,
            secondary_phone=payload.secondary_phone,
            notes=payload.notes
        )
        db.add(customer)
        await db.flush()
        return customer

    @staticmethod
    async def get_customer(db: AsyncSession, customer_id: uuid.UUID) -> Customer:
        result = await db.execute(select(Customer).where(Customer.customer_id == customer_id))
        customer = result.scalar_one_or_none()
        if not customer:
            raise NotFoundError("Customer not found")
        return customer

    @staticmethod
    async def update_customer(db: AsyncSession, customer_id: uuid.UUID, payload: CustomerUpdate) -> Customer:
        customer = await CustomerService.get_customer(db, customer_id)

        if payload.name is not None:
            customer.name = payload.name
        if payload.customer_type is not None:
            customer.customer_type = payload.customer_type
        if payload.billing_address is not None:
            customer.billing_address = payload.billing_address
        if payload.tax_exempt is not None:
            customer.tax_exempt = payload.tax_exempt
        if payload.phone is not None:
            customer.phone = payload.phone
        if payload.email is not None:
            customer.email = payload.email
        if payload.secondary_phone is not None:
            customer.secondary_phone = payload.secondary_phone
        if payload.notes is not None:
            customer.notes = payload.notes

        await db.flush()
        return customer

    @staticmethod
    async def delete_customer(db: AsyncSession, customer_id: uuid.UUID) -> None:
        customer = await CustomerService.get_customer(db, customer_id)
        await db.delete(customer)

    @staticmethod
    async def create_vehicle(db: AsyncSession, payload: VehicleCreate) -> Vehicle:
        # Check owner existence
        cust_res = await db.execute(select(Customer).where(Customer.customer_id == payload.customer_id))
        if not cust_res.scalar_one_or_none():
            raise ValueError(f"Customer with ID {payload.customer_id} does not exist.")

        vehicle = Vehicle(
            vin=payload.vin,
            customer_id=payload.customer_id,
            make=payload.make,
            model=payload.model,
            year=payload.year,
            current_mileage=payload.current_mileage,
            license_plate=payload.license_plate
        )
        db.add(vehicle)
        await db.flush()
        return vehicle

    @staticmethod
    async def get_vehicle(db: AsyncSession, vin: str) -> Vehicle:
        result = await db.execute(select(Vehicle).where(Vehicle.vin == vin))
        vehicle = result.scalar_one_or_none()
        if not vehicle:
            raise NotFoundError("Vehicle not found")
        return vehicle

    @staticmethod
    async def update_vehicle(db: AsyncSession, vin: str, payload: VehicleUpdate) -> Vehicle:
        vehicle = await CustomerService.get_vehicle(db, vin)

        if payload.customer_id is not None:
            cust_res = await db.execute(select(Customer).where(Customer.customer_id == payload.customer_id))
            if not cust_res.scalar_one_or_none():
                raise ValueError("Target customer does not exist.")
            vehicle.customer_id = payload.customer_id
        if payload.make is not None:
            vehicle.make = payload.make
        if payload.model is not None:
            vehicle.model = payload.model
        if payload.year is not None:
            vehicle.year = payload.year
        if payload.current_mileage is not None:
            vehicle.current_mileage = payload.current_mileage
        if payload.license_plate is not None:
            vehicle.license_plate = payload.license_plate

        await db.flush()
        return vehicle

    @staticmethod
    async def delete_vehicle(db: AsyncSession, vin: str) -> None:
        vehicle = await CustomerService.get_vehicle(db, vin)
        await db.delete(vehicle)

    @staticmethod
    async def get_timeline_events(db: AsyncSession, customer_id: uuid.UUID) -> list[dict]:
        events = []

        # 1. Appointments
        res_appts = await db.execute(select(Appointment).where(Appointment.customer_id == customer_id))
        for appt in res_appts.scalars().all():
            events.append({
                "title": "Appointment booked",
                "date": appt.requested_date, # Date
                "description": f"Appointment booked for {appt.vehicle_id}.",
                "amount": None,
                "type": "appointment",
                "status": appt.status
            })

        # 2. Visits (Check-in)
        res_visits = await db.execute(select(Visit).where(Visit.customer_id == customer_id))
        for visit in res_visits.scalars().all():
            events.append({
                "title": "Vehicle checked in",
                "date": visit.checked_in_at,
                "description": f"Checked in vehicle {visit.vehicle_id}.",
                "amount": None,
                "type": "check_in",
                "status": visit.status
            })

        # 3. Quotes
        res_quotes = await db.execute(select(Quote).where(Quote.customer_id == customer_id))
        for quote in res_quotes.scalars().all():
            events.append({
                "title": f"Quote {quote.status}",
                "date": quote.drafted_at,
                "description": f"Quote for vehicle {quote.vehicle_id}.",
                "amount": f"${quote.total_amount:,.2f}",
                "type": "quote",
                "status": quote.status
            })

        # 4. Work Orders
        res_wos = await db.execute(select(WorkOrder).where(WorkOrder.customer_id == customer_id))
        for wo in res_wos.scalars().all():
            events.append({
                "title": f"Work order {wo.status}",
                "date": wo.created_at,
                "description": f"Work order for vehicle {wo.vehicle_id}.",
                "amount": f"${wo.authorized_amount:,.2f}",
                "type": "work_order",
                "status": wo.status
            })

        # 5. Invoices
        res_invs = await db.execute(select(Invoice).where(Invoice.customer_id == customer_id))
        for inv in res_invs.scalars().all():
            events.append({
                "title": f"Invoice {inv.status}",
                "date": inv.issued_at,
                "description": "Invoice issued.",
                "amount": f"${inv.amount_due:,.2f}",
                "type": "invoice",
                "status": inv.status
            })

        # 6. Payments
        # We need payments for this customer. Payments are linked to Invoice, so we join.
        res_pays = await db.execute(
            select(Payment, Invoice)
            .join(Invoice, Payment.invoice_id == Invoice.invoice_id)
            .where(Invoice.customer_id == customer_id)
        )
        for payment, _invoice in res_pays.all():
            events.append({
                "title": "Payment received",
                "date": payment.collected_at,
                "description": f"Payment via {payment.method}.",
                "amount": f"${payment.amount:,.2f}",
                "type": "payment",
                "status": "completed"
            })

        # Sort events by date descending
        # Convert date/datetime to timestamp for safe sorting
        import datetime
        def get_timestamp(d):
            if isinstance(d, datetime.datetime):
                return d.timestamp()
            elif isinstance(d, datetime.date):
                # convert date to datetime
                return datetime.datetime.combine(d, datetime.time.min).timestamp()
            return 0

        events.sort(key=lambda x: get_timestamp(x['date']), reverse=True)

        # Convert date to datetime for response model if it's a date object
        for event in events:
            if isinstance(event['date'], datetime.date) and not isinstance(event['date'], datetime.datetime):
                event['date'] = datetime.datetime.combine(event['date'], datetime.time.min, tzinfo=datetime.timezone.utc)

        return events

    @staticmethod
    async def get_vehicle_service_history(db: AsyncSession, vin: str):
        """
        Retrieves the complete historical service record of a vehicle by VIN.
        """
        from app.schemas.schemas import (
            VehicleServiceHistory, ServiceHistoryEntry, ServiceHistoryLineItem
        )
        from sqlalchemy.orm import selectinload

        veh_res = await db.execute(
            select(Vehicle)
            .options(selectinload(Vehicle.customer))
            .where(Vehicle.vin == vin)
        )
        vehicle = veh_res.scalar_one_or_none()
        if not vehicle:
            raise NotFoundError(f"Vehicle with VIN '{vin}' not found.")

        wo_stmt = (
            select(WorkOrder)
            .options(
                selectinload(WorkOrder.line_items),
                selectinload(WorkOrder.quote),
                selectinload(WorkOrder.invoice).selectinload(Invoice.payments)
            )
            .where(WorkOrder.vehicle_id == vin)
            .order_by(WorkOrder.created_at.desc())
        )
        wo_res = await db.execute(wo_stmt)
        work_orders = wo_res.scalars().all()

        history_entries = []
        total_spent = decimal.Decimal("0.00")

        for wo in work_orders:
            line_items = [
                ServiceHistoryLineItem(
                    description=li.description,
                    billing_mode=li.billing_mode,
                    price=li.price,
                    status=li.status
                )
                for li in wo.line_items
            ]

            inv_amount = wo.invoice.amount_due if wo.invoice else None
            inv_status = wo.invoice.status if wo.invoice else None
            total_paid = None
            if wo.invoice and wo.invoice.payments:
                total_paid = sum(
                    (p.amount - (p.refund_amount or decimal.Decimal("0.00")))
                    for p in wo.invoice.payments
                )
                total_spent += total_paid
            elif inv_amount and inv_status == 'paid':
                total_spent += inv_amount

            history_entries.append(
                ServiceHistoryEntry(
                    work_order_id=wo.work_order_id,
                    status=wo.status,
                    created_at=wo.created_at,
                    closed_at=wo.closed_at,
                    quote_total=wo.quote.total_amount if wo.quote else wo.authorized_amount,
                    line_items=line_items,
                    invoice_amount=inv_amount,
                    invoice_status=inv_status,
                    total_paid=total_paid
                )
            )

        return VehicleServiceHistory(
            vin=vehicle.vin,
            make=vehicle.make,
            model=vehicle.model,
            year=vehicle.year,
            customer_name=vehicle.customer.name if vehicle.customer else "Unknown",
            total_visits=len(history_entries),
            total_spent=total_spent,
            history=history_entries
        )

