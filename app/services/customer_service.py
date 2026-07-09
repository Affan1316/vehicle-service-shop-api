import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.models import Customer, Vehicle
from app.schemas.schemas import CustomerCreate, CustomerUpdate, VehicleCreate, VehicleUpdate
from app.exceptions import NotFoundError


class CustomerService:
    @staticmethod
    async def create_customer(db: AsyncSession, payload: CustomerCreate) -> Customer:
        customer = Customer(
            name=payload.name,
            customer_type=payload.customer_type,
            billing_address=payload.billing_address,
            tax_exempt=payload.tax_exempt
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
            current_mileage=payload.current_mileage
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

        await db.flush()
        return vehicle

    @staticmethod
    async def delete_vehicle(db: AsyncSession, vin: str) -> None:
        vehicle = await CustomerService.get_vehicle(db, vin)
        await db.delete(vehicle)
