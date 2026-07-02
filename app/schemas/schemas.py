import datetime
import decimal
import uuid
from typing import Optional, List, Generic, TypeVar
from pydantic import BaseModel, ConfigDict, Field

# ================================================================
# SECTION 1: Independent Core Entities
# ================================================================

# CUSTOMER
class CustomerBase(BaseModel):
    name: str = Field(..., max_length=255)
    customer_type: str = Field(..., description="Must be 'individual' or 'fleet'")
    billing_address: Optional[str] = Field(None, max_length=500)
    tax_exempt: bool = Field(default=False)

class CustomerCreate(CustomerBase):
    pass

class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    customer_type: Optional[str] = Field(None, description="Must be 'individual' or 'fleet'")
    billing_address: Optional[str] = Field(None, max_length=500)
    tax_exempt: Optional[bool] = None

class CustomerResponse(CustomerBase):
    customer_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# VENDOR
class VendorBase(BaseModel):
    name: str = Field(..., max_length=255)
    vendor_type: str = Field(..., max_length=100)

class VendorCreate(VendorBase):
    pass

class VendorUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    vendor_type: Optional[str] = Field(None, max_length=100)

class VendorResponse(VendorBase):
    vendor_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# TECHNICIAN
class TechnicianBase(BaseModel):
    name: str = Field(..., max_length=255)
    hourly_rate: decimal.Decimal = Field(..., ge=0)

class TechnicianCreate(TechnicianBase):
    tech_id: Optional[uuid.UUID] = None

class TechnicianUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    hourly_rate: Optional[decimal.Decimal] = Field(None, ge=0)

class TechnicianResponse(TechnicianBase):
    tech_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# PART (Catalog Part)
class PartBase(BaseModel):
    part_number: str = Field(..., max_length=100)
    category: str = Field(..., max_length=100)
    quantity_on_hand: int = Field(..., ge=0)
    is_returnable: bool = Field(default=True)

class PartCreate(PartBase):
    pass

class PartUpdate(BaseModel):
    part_number: Optional[str] = Field(None, max_length=100)
    category: Optional[str] = Field(None, max_length=100)
    quantity_on_hand: Optional[int] = Field(None, ge=0)
    is_returnable: Optional[bool] = None

class PartResponse(PartBase):
    part_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# PAYER
class PayerBase(BaseModel):
    name: str = Field(..., max_length=255)
    payer_type: str = Field(..., description="Must be 'insurer', 'warranty_company', or 'fleet_account'")
    contact_info: Optional[str] = Field(None, max_length=500)
    billing_terms: Optional[str] = Field(None, max_length=255)
    account_number: Optional[str] = Field(None, max_length=100)

class PayerCreate(PayerBase):
    pass

class PayerUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    payer_type: Optional[str] = Field(None, description="Must be 'insurer', 'warranty_company', or 'fleet_account'")
    contact_info: Optional[str] = Field(None, max_length=500)
    billing_terms: Optional[str] = Field(None, max_length=255)
    account_number: Optional[str] = Field(None, max_length=100)

class PayerResponse(PayerBase):
    payer_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# ================================================================
# SECTION 2: Dependent Entities & Work Flow
# ================================================================

# VEHICLE
class VehicleBase(BaseModel):
    vin: str = Field(..., min_length=17, max_length=17)
    customer_id: uuid.UUID
    make: str = Field(..., max_length=100)
    model: str = Field(..., max_length=100)
    year: int = Field(..., ge=1900, le=2100)
    current_mileage: Optional[int] = Field(None, ge=0)

class VehicleCreate(VehicleBase):
    pass

class VehicleUpdate(BaseModel):
    customer_id: Optional[uuid.UUID] = None
    make: Optional[str] = Field(None, max_length=100)
    model: Optional[str] = Field(None, max_length=100)
    year: Optional[int] = Field(None, ge=1900, le=2100)
    current_mileage: Optional[int] = Field(None, ge=0)

class VehicleResponse(VehicleBase):
    model_config = ConfigDict(from_attributes=True)


# APPOINTMENT
class AppointmentBase(BaseModel):
    customer_id: uuid.UUID
    vehicle_id: str = Field(..., min_length=17, max_length=17)
    requested_date: datetime.date
    confirmed_date: Optional[datetime.date] = None
    status: str = Field(..., description="Must be 'requested', 'confirmed', or 'cancelled'")
    bay_id: Optional[uuid.UUID] = None

class AppointmentCreate(AppointmentBase):
    pass

class AppointmentUpdate(BaseModel):
    customer_id: Optional[uuid.UUID] = None
    vehicle_id: Optional[str] = Field(None, min_length=17, max_length=17)
    requested_date: Optional[datetime.date] = None
    confirmed_date: Optional[datetime.date] = None
    status: Optional[str] = Field(None, description="Must be 'requested', 'confirmed', or 'cancelled'")
    bay_id: Optional[uuid.UUID] = None

class AppointmentResponse(AppointmentBase):
    appointment_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# VISIT
class VisitBase(BaseModel):
    vehicle_id: str = Field(..., min_length=17, max_length=17)
    customer_id: uuid.UUID
    appointment_id: Optional[uuid.UUID] = None
    checked_in_at: datetime.datetime
    checked_out_at: Optional[datetime.datetime] = None
    status: str = Field(..., description="checked_in, in_diagnosis, awaiting_quote, in_service, awaiting_pickup, completed")

class VisitCreate(BaseModel):
    vehicle_id: str = Field(..., min_length=17, max_length=17)
    customer_id: uuid.UUID
    appointment_id: Optional[uuid.UUID] = None
    checked_in_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    status: str = "checked_in"

class VisitUpdate(BaseModel):
    checked_out_at: Optional[datetime.datetime] = None
    status: Optional[str] = None

class VisitResponse(VisitBase):
    visit_id: uuid.UUID
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


# ================================================================
# SECTION 3: Sales
# ================================================================

# QUOTE
class QuoteBase(BaseModel):
    customer_id: uuid.UUID
    vehicle_id: str = Field(..., min_length=17, max_length=17)
    visit_id: Optional[uuid.UUID] = None
    status: str = Field(..., description="draft, issued, approved, declined, expired")
    total_amount: decimal.Decimal = Field(..., ge=0)
    drafted_at: datetime.datetime
    valid_until: datetime.date
    issued_at: Optional[datetime.datetime] = None
    decline_reason: Optional[str] = Field(None, max_length=500)

class QuoteCreate(BaseModel):
    customer_id: uuid.UUID
    vehicle_id: str = Field(..., min_length=17, max_length=17)
    visit_id: Optional[uuid.UUID] = None
    status: str = "draft"
    total_amount: decimal.Decimal = Field(..., ge=0)
    drafted_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    valid_until: datetime.date
    issued_at: Optional[datetime.datetime] = None
    decline_reason: Optional[str] = Field(None, max_length=500)

class QuoteUpdate(BaseModel):
    status: Optional[str] = None
    total_amount: Optional[decimal.Decimal] = Field(None, ge=0)
    valid_until: Optional[datetime.date] = None
    issued_at: Optional[datetime.datetime] = None
    decline_reason: Optional[str] = Field(None, max_length=500)

class QuoteResponse(QuoteBase):
    quote_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)
