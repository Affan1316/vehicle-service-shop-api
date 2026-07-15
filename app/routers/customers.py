import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.models import Customer, Vehicle, User
from app.schemas import (
    CustomerCreate, CustomerUpdate, CustomerResponse,
    VehicleCreate, VehicleUpdate, VehicleResponse
)
from fastapi_pagination import LimitOffsetPage
from fastapi_pagination.ext.sqlalchemy import apaginate
from app.routers.auth_deps import RoleChecker
from app.routers.pagination_deps import PaginationParams

from app.services import CustomerService
from app.exceptions import NotFoundError

router = APIRouter()


def _with_required_roles(*roles: str):
    def decorator(operation):
        operation.__dict__["x-required-roles"] = list(roles)
        return operation
    return decorator


# --- CUSTOMER ENDPOINTS ---

@router.post(
    "/customers", 
    response_model=CustomerResponse, 
    status_code=status.HTTP_201_CREATED, 
    dependencies=[Depends(RoleChecker(["manager", "advisor"]))],
)
@_with_required_roles("manager", "advisor")
async def create_customer(payload: CustomerCreate, db: AsyncSession = Depends(get_db)):
    """
    Create a new customer profile.
    """
    try:
        return await CustomerService.create_customer(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/customers", 
    response_model=LimitOffsetPage[CustomerResponse], 
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))],
)
@_with_required_roles("manager", "advisor", "technician")
async def list_customers(params: PaginationParams = Depends(), db: AsyncSession = Depends(get_db)):
    """
    Retrieve a paginated list of all customers.
    """
    return await apaginate(db, select(Customer), params)

@router.get(
    "/customers/{customer_id}", 
    response_model=CustomerResponse, 
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))],
)
@_with_required_roles("manager", "advisor", "technician")
async def get_customer(customer_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """
    Get details of a single customer by ID.
    """
    try:
        return await CustomerService.get_customer(db, customer_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.put(
    "/customers/{customer_id}", 
    response_model=CustomerResponse, 
    dependencies=[Depends(RoleChecker(["manager", "advisor"]))],
)
@_with_required_roles("manager", "advisor")
async def update_customer(customer_id: uuid.UUID, payload: CustomerUpdate, db: AsyncSession = Depends(get_db)):
    """
    Update a customer's fields dynamically.
    """
    try:
        return await CustomerService.update_customer(db, customer_id, payload)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete(
    "/customers/{customer_id}", 
    dependencies=[Depends(RoleChecker(["manager"]))],
)
@_with_required_roles("manager")
async def delete_customer(customer_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """
    Delete a customer profile.
    """
    try:
        await CustomerService.delete_customer(db, customer_id)
        return {"message": "Customer deleted successfully"}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


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
    try:
        return await CustomerService.create_vehicle(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/vehicles", 
    response_model=LimitOffsetPage[VehicleResponse]
)
async def list_vehicles(
    params: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor", "technician", "customer"]))
):
    """
    Retrieve all registered vehicles with pagination.
    """
    query = select(Vehicle)
    if current_user.role == "customer":
        if current_user.customer_id is None:
            raise HTTPException(status_code=400, detail="User is not linked to a customer profile.")
        query = query.where(Vehicle.customer_id == current_user.customer_id)
    return await apaginate(db, query, params)

@router.get(
    "/vehicles/{vin}", 
    response_model=VehicleResponse, 
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))]
)
async def get_vehicle(vin: str, db: AsyncSession = Depends(get_db)):
    """
    Get vehicle details by VIN (Vehicle Identification Number).
    """
    try:
        return await CustomerService.get_vehicle(db, vin)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.put(
    "/vehicles/{vin}", 
    response_model=VehicleResponse, 
    dependencies=[Depends(RoleChecker(["manager", "advisor"]))]
)
async def update_vehicle(vin: str, payload: VehicleUpdate, db: AsyncSession = Depends(get_db)):
    """
    Update vehicle information (e.g. mileage updates).
    """
    try:
        return await CustomerService.update_vehicle(db, vin, payload)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
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
    try:
        await CustomerService.delete_vehicle(db, vin)
        return {"message": "Vehicle deleted successfully"}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

