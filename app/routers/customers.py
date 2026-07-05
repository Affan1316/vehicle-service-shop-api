import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.models import Customer, Vehicle
from app.schemas import (
    CustomerCreate, CustomerUpdate, CustomerResponse,
    VehicleCreate, VehicleUpdate, VehicleResponse
)
from fastapi_pagination import LimitOffsetPage
from fastapi_pagination.ext.sqlalchemy import apaginate
from app.routers.auth_deps import RoleChecker
from app.routers.pagination_deps import PaginationParams

router = APIRouter()

# --- CUSTOMER ENDPOINTS ---

@router.post(
    "/customers", 
    response_model=CustomerResponse, 
    status_code=status.HTTP_201_CREATED, 
    dependencies=[Depends(RoleChecker(["manager", "advisor"]))]
)
async def create_customer(payload: CustomerCreate, db: AsyncSession = Depends(get_db)):
    """
    Create a new customer profile.
    """
    try:
        customer = Customer(
            name=payload.name,
            customer_type=payload.customer_type,
            billing_address=payload.billing_address,
            tax_exempt=payload.tax_exempt
        )
        db.add(customer)
        # Flush executes the SQL INSERT statement to verify constraints and fetch the generated UUID (customer_id)
        await db.flush()
        return customer
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/customers", 
    response_model=LimitOffsetPage[CustomerResponse], 
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def list_customers(params: PaginationParams = Depends(), db: AsyncSession = Depends(get_db)):
    """
    Retrieve a paginated list of all customers.
    """
    return await apaginate(db, select(Customer), params)

@router.get(
    "/customers/{customer_id}", 
    response_model=CustomerResponse, 
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def get_customer(customer_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """
    Get details of a single customer by ID.
    """
    result = await db.execute(select(Customer).where(Customer.customer_id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer

@router.put(
    "/customers/{customer_id}", 
    response_model=CustomerResponse, 
    dependencies=[Depends(RoleChecker(["manager", "advisor"]))]
)
async def update_customer(customer_id: uuid.UUID, payload: CustomerUpdate, db: AsyncSession = Depends(get_db)):
    """
    Update a customer's fields dynamically.
    """
    result = await db.execute(select(Customer).where(Customer.customer_id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    try:
        # Update field values only if they are provided in the request payload
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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete(
    "/customers/{customer_id}", 
    dependencies=[Depends(RoleChecker(["manager"]))]
)
async def delete_customer(customer_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """
    Delete a customer profile.
    """
    result = await db.execute(select(Customer).where(Customer.customer_id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    await db.delete(customer)
    return {"message": "Customer deleted successfully"}


# --- VEHICLE ENDPOINTS ---

@router.post(
    "/vehicles", 
    response_model=VehicleResponse, 
    status_code=status.HTTP_201_CREATED, 
    dependencies=[Depends(RoleChecker(["manager", "advisor"]))]
)
async def create_vehicle(payload: VehicleCreate, db: AsyncSession = Depends(get_db)):
    """
    Register a new vehicle. Checks if the owner (customer) exists first.
    """
    # Verify owner customer exists in database
    cust_res = await db.execute(select(Customer).where(Customer.customer_id == payload.customer_id))
    if not cust_res.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Customer with ID {payload.customer_id} does not exist.")
    
    try:
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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/vehicles", 
    response_model=LimitOffsetPage[VehicleResponse], 
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def list_vehicles(params: PaginationParams = Depends(), db: AsyncSession = Depends(get_db)):
    """
    Retrieve all registered vehicles with pagination.
    """
    return await apaginate(db, select(Vehicle), params)

@router.get(
    "/vehicles/{vin}", 
    response_model=VehicleResponse, 
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def get_vehicle(vin: str, db: AsyncSession = Depends(get_db)):
    """
    Get vehicle details by VIN (Vehicle Identification Number).
    """
    result = await db.execute(select(Vehicle).where(Vehicle.vin == vin))
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return vehicle

@router.put(
    "/vehicles/{vin}", 
    response_model=VehicleResponse, 
    dependencies=[Depends(RoleChecker(["manager", "advisor"]))]
)
async def update_vehicle(vin: str, payload: VehicleUpdate, db: AsyncSession = Depends(get_db)):
    """
    Update vehicle information (e.g. mileage updates).
    """
    result = await db.execute(select(Vehicle).where(Vehicle.vin == vin))
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    try:
        if payload.customer_id is not None:
            # Verify new target owner exists in database before moving ownership
            cust_res = await db.execute(select(Customer).where(Customer.customer_id == payload.customer_id))
            if not cust_res.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Target customer does not exist.")
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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete(
    "/vehicles/{vin}", 
    dependencies=[Depends(RoleChecker(["manager"]))]
)
async def delete_vehicle(vin: str, db: AsyncSession = Depends(get_db)):
    """
    Delete a vehicle record.
    """
    result = await db.execute(select(Vehicle).where(Vehicle.vin == vin))
    vehicle = result.scalar_one_or_none()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    await db.delete(vehicle)
    return {"message": "Vehicle deleted successfully"}
