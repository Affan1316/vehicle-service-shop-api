import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.models import Customer, Vehicle, User
from app.schemas import (
    CustomerCreate, CustomerUpdate, CustomerResponse,
    VehicleCreate, VehicleUpdate, VehicleResponse, VehicleServiceHistory,
    TimelineEventResponse
)
from fastapi_pagination import LimitOffsetPage
from fastapi_pagination.ext.sqlalchemy import apaginate
from app.routers.auth_deps import RoleChecker, get_current_user
from app.routers.pagination_deps import PaginationParams

from app.services import CustomerService, SearchService, AuditService
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
async def create_customer(
    payload: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new customer profile.
    """
    try:
        cust = await CustomerService.create_customer(db, payload)
        await AuditService.log_create(
            db, "customer", str(cust.customer_id),
            current_user.user_id, current_user.username,
            {"name": cust.name, "email": cust.email, "phone": cust.phone}
        )
        return cust
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/customers/search",
    response_model=List[CustomerResponse],
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))],
)
@_with_required_roles("manager", "advisor", "technician")
async def search_customers(
    q: str = Query(..., min_length=1, description="Search by name, phone, email, or secondary phone"),
    db: AsyncSession = Depends(get_db)
):
    """
    Search customers by name, phone number, email address, or secondary phone.
    """
    return await SearchService.search_customers(db, q)

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
)
async def get_customer(
    customer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor", "technician", "customer"]))
):
    """
    Get details of a single customer by ID.
    """
    if current_user.role == "customer" and current_user.customer_id != customer_id:
        raise HTTPException(status_code=403, detail="Not authorized to view other customer profiles.")
    try:
        return await CustomerService.get_customer(db, customer_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/customers/{customer_id}/timeline",
    response_model=List[TimelineEventResponse],
)
async def get_customer_timeline(
    customer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor", "technician", "customer"]))
):
    """
    Get the history timeline for a customer.
    """
    if current_user.role == "customer" and current_user.customer_id != customer_id:
        raise HTTPException(status_code=403, detail="Not authorized to view other customer's timeline.")

    # First ensure customer exists
    try:
        await CustomerService.get_customer(db, customer_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    events = await CustomerService.get_timeline_events(db, customer_id)
    return events

@router.put(
    "/customers/{customer_id}",
    response_model=CustomerResponse,
    dependencies=[Depends(RoleChecker(["manager", "advisor"]))],
)
@_with_required_roles("manager", "advisor")
async def update_customer(
    customer_id: uuid.UUID,
    payload: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a customer's fields dynamically.
    """
    try:
        cust = await CustomerService.update_customer(db, customer_id, payload)
        await AuditService.log_update(
            db, "customer", str(customer_id),
            current_user.user_id, current_user.username,
            payload.model_dump(exclude_unset=True)
        )
        return cust
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete(
    "/customers/{customer_id}",
    dependencies=[Depends(RoleChecker(["manager"]))],
)
@_with_required_roles("manager")
async def delete_customer(
    customer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a customer profile.
    """
    try:
        await CustomerService.delete_customer(db, customer_id)
        await AuditService.log_delete(
            db, "customer", str(customer_id),
            current_user.user_id, current_user.username
        )
        return {"message": "Customer deleted successfully"}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- VEHICLE ENDPOINTS ---

@router.post(
    "/vehicles",
    response_model=VehicleResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_vehicle(
    payload: VehicleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor", "customer"]))
):
    """
    Register a new vehicle. Checks if the owner (customer) exists first.
    """
    if current_user.role == "customer":
        if current_user.customer_id != payload.customer_id:
            raise HTTPException(status_code=403, detail="Not authorized to register vehicles for other customers.")
    try:
        veh = await CustomerService.create_vehicle(db, payload)
        await AuditService.log_create(
            db, "vehicle", veh.vin,
            current_user.user_id, current_user.username,
            {"make": veh.make, "model": veh.model, "year": veh.year}
        )
        return veh
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
    "/vehicles/search",
    response_model=List[VehicleResponse],
    dependencies=[Depends(RoleChecker(["manager", "advisor", "technician"]))],
)
@_with_required_roles("manager", "advisor", "technician")
async def search_vehicles(
    q: str = Query(..., min_length=1, description="Search by VIN, license plate, or customer name"),
    db: AsyncSession = Depends(get_db)
):
    """
    Search vehicles by VIN, license plate, or customer name.
    """
    return await SearchService.search_vehicles(db, q)

@router.get(
    "/vehicles/{vin}",
    response_model=VehicleResponse,
)
async def get_vehicle(
    vin: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor", "technician", "customer"]))
):
    """
    Get vehicle details by VIN (Vehicle Identification Number).
    """
    try:
        vehicle = await CustomerService.get_vehicle(db, vin)
        if current_user.role == "customer" and vehicle.customer_id != current_user.customer_id:
            raise HTTPException(status_code=403, detail="Not authorized to view other customers' vehicles.")
        return vehicle
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/vehicles/{vin}/service-history",
    response_model=VehicleServiceHistory,
)
async def get_vehicle_service_history(
    vin: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(RoleChecker(["manager", "advisor", "technician", "customer"]))
):
    """
    Retrieve comprehensive service history, work orders, line items, and invoice payments for a vehicle.
    """
    if current_user.role == "customer":
        try:
            vehicle = await CustomerService.get_vehicle(db, vin)
            if vehicle.customer_id != current_user.customer_id:
                raise HTTPException(status_code=403, detail="Not authorized to view other customers' vehicle service history.")
        except NotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
    try:
        return await CustomerService.get_vehicle_service_history(db, vin)
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

