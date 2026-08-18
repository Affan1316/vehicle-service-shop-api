import datetime
import decimal
import re
import uuid
from typing import Optional, List, Generic, TypeVar, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


# Helper validation functions
def _validate_email_str(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    cleaned = v.strip().lower()
    if not cleaned:
        return None
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", cleaned):
        raise ValueError(f"Invalid email address format: '{v}'")
    return cleaned


def _validate_phone_str(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    cleaned = v.strip()
    if not cleaned:
        return None
    # Strip common formatting characters for length check
    digits_only = re.sub(r"[^\d+]", "", cleaned)
    if len(digits_only) < 7 or len(digits_only) > 15:
        raise ValueError(f"Invalid phone number length: '{v}'. Must contain between 7 and 15 digits.")
    return cleaned


def _validate_license_plate_str(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    cleaned = v.strip().upper()
    return cleaned if cleaned else None


# ================================================================
# SECTION 1: Independent Core Entities
# ================================================================

# CUSTOMER
class CustomerBase(BaseModel):
    name: str = Field(..., max_length=255)
    customer_type: Literal["individual", "fleet"] = Field(..., description="Must be 'individual' or 'fleet'")
    billing_address: Optional[str] = Field(None, max_length=500)
    tax_exempt: bool = Field(default=False)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=255)
    secondary_phone: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("email", mode="before")
    @classmethod
    def check_email(cls, v):
        return _validate_email_str(v)

    @field_validator("phone", "secondary_phone", mode="before")
    @classmethod
    def check_phone(cls, v):
        return _validate_phone_str(v)


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    customer_type: Optional[Literal["individual", "fleet"]] = Field(None, description="Must be 'individual' or 'fleet'")
    billing_address: Optional[str] = Field(None, max_length=500)
    tax_exempt: Optional[bool] = None
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=255)
    secondary_phone: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("email", mode="before")
    @classmethod
    def check_email(cls, v):
        return _validate_email_str(v)

    @field_validator("phone", "secondary_phone", mode="before")
    @classmethod
    def check_phone(cls, v):
        return _validate_phone_str(v)


class CustomerResponse(CustomerBase):
    customer_id: uuid.UUID
    stripe_customer_id: Optional[str] = None
    safepay_customer_id: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)



class TimelineEventResponse(BaseModel):
    title: str
    date: datetime.datetime
    description: str
    amount: Optional[str] = None
    type: str
    status: str


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


class CertificationCreate(BaseModel):
    cert_type: str = Field(..., max_length=100)
    expiry_date: datetime.date


class CertificationResponse(BaseModel):
    cert_id: uuid.UUID
    tech_id: uuid.UUID
    cert_type: str
    expiry_date: datetime.date
    model_config = ConfigDict(from_attributes=True)


class TechnicianResponse(TechnicianBase):
    tech_id: uuid.UUID
    certifications: List[CertificationResponse] = Field(default_factory=list)
    has_expiring_cert: bool = False
    model_config = ConfigDict(from_attributes=True)


# PART (Catalog Part)
class PartBase(BaseModel):
    name: str = Field(default="", max_length=255)
    part_number: str = Field(..., max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    category: str = Field(..., max_length=100)
    cost_price: decimal.Decimal = Field(default=decimal.Decimal("0.00"), ge=0)
    retail_price: decimal.Decimal = Field(default=decimal.Decimal("0.00"), ge=0)
    quantity_on_hand: int = Field(..., ge=0)
    is_returnable: bool = Field(default=True)
    warranty_required: bool = False


class PartCreate(PartBase):
    pass


class PartUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    part_number: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    category: Optional[str] = Field(None, max_length=100)
    cost_price: Optional[decimal.Decimal] = Field(None, ge=0)
    retail_price: Optional[decimal.Decimal] = Field(None, ge=0)
    quantity_on_hand: Optional[int] = Field(None, ge=0)
    is_returnable: Optional[bool] = None
    warranty_required: Optional[bool] = None


class PartResponse(PartBase):
    part_id: uuid.UUID
    markup_percent: decimal.Decimal = decimal.Decimal("0.00")
    model_config = ConfigDict(from_attributes=True)


# PAYER
class PayerBase(BaseModel):
    name: str = Field(..., max_length=255)
    payer_type: Literal["insurer", "warranty_company", "fleet_account"] = Field(
        ..., description="Must be 'insurer', 'warranty_company', or 'fleet_account'"
    )
    contact_info: Optional[str] = Field(None, max_length=500)
    billing_terms: Optional[str] = Field(None, max_length=255)
    account_number: Optional[str] = Field(None, max_length=100)


class PayerCreate(PayerBase):
    pass


class PayerUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    payer_type: Optional[Literal["insurer", "warranty_company", "fleet_account"]] = Field(
        None, description="Must be 'insurer', 'warranty_company', or 'fleet_account'"
    )
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
    license_plate: Optional[str] = Field(None, max_length=15)

    @field_validator("vin", mode="before")
    @classmethod
    def upper_vin(cls, v: str) -> str:
        return v.strip().upper() if isinstance(v, str) else v

    @field_validator("license_plate", mode="before")
    @classmethod
    def check_plate(cls, v):
        return _validate_license_plate_str(v)


class VehicleCreate(VehicleBase):
    pass


class VehicleUpdate(BaseModel):
    customer_id: Optional[uuid.UUID] = None
    make: Optional[str] = Field(None, max_length=100)
    model: Optional[str] = Field(None, max_length=100)
    year: Optional[int] = Field(None, ge=1900, le=2100)
    current_mileage: Optional[int] = Field(None, ge=0)
    license_plate: Optional[str] = Field(None, max_length=15)

    @field_validator("license_plate", mode="before")
    @classmethod
    def check_plate(cls, v):
        return _validate_license_plate_str(v)


class VehicleResponse(VehicleBase):
    model_config = ConfigDict(from_attributes=True)


# APPOINTMENT
class AppointmentBase(BaseModel):
    customer_id: uuid.UUID
    vehicle_id: str = Field(..., min_length=17, max_length=17)
    requested_date: datetime.date
    confirmed_date: Optional[datetime.date] = None
    status: Literal["requested", "confirmed", "cancelled", "checked_in"] = Field(
        ..., description="Must be 'requested', 'confirmed', 'cancelled', or 'checked_in'"
    )
    bay_id: Optional[uuid.UUID] = None
    preferred_time: Optional[str] = None


class AppointmentCreate(BaseModel):
    customer_id: uuid.UUID
    vehicle_id: str = Field(..., min_length=17, max_length=17)
    requested_date: datetime.date
    confirmed_date: Optional[datetime.date] = None
    status: Literal["requested", "confirmed", "cancelled", "checked_in"] = "requested"
    bay_id: Optional[uuid.UUID] = None
    preferred_time: Optional[str] = None


class AppointmentUpdate(BaseModel):
    customer_id: Optional[uuid.UUID] = None
    vehicle_id: Optional[str] = Field(None, min_length=17, max_length=17)
    requested_date: Optional[datetime.date] = None
    confirmed_date: Optional[datetime.date] = None
    status: Optional[Literal["requested", "confirmed", "cancelled", "checked_in"]] = None
    bay_id: Optional[uuid.UUID] = None
    preferred_time: Optional[str] = None


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
    status: Literal[
        "checked_in", "in_diagnosis", "awaiting_quote", "in_service", "awaiting_pickup", "completed"
    ] = Field(..., description="checked_in, in_diagnosis, awaiting_quote, in_service, awaiting_pickup, completed")
    walk_in: bool = False


class VisitCreate(BaseModel):
    vehicle_id: str = Field(..., min_length=17, max_length=17)
    customer_id: uuid.UUID
    appointment_id: Optional[uuid.UUID] = None
    checked_in_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    status: Literal[
        "checked_in", "in_diagnosis", "awaiting_quote", "in_service", "awaiting_pickup", "completed"
    ] = "checked_in"


class VisitUpdate(BaseModel):
    checked_out_at: Optional[datetime.datetime] = None
    status: Optional[Literal[
        "checked_in", "in_diagnosis", "awaiting_quote", "in_service", "awaiting_pickup", "completed"
    ]] = None


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
    status: Literal["draft", "issued", "approved", "declined", "expired"] = Field(
        ..., description="draft, issued, approved, declined, expired"
    )
    total_amount: decimal.Decimal = Field(..., ge=0)
    drafted_at: datetime.datetime
    valid_until: datetime.date
    issued_at: Optional[datetime.datetime] = None
    decline_reason: Optional[str] = Field(None, max_length=500)


class QuoteCreate(BaseModel):
    customer_id: uuid.UUID
    vehicle_id: str = Field(..., min_length=17, max_length=17)
    visit_id: Optional[uuid.UUID] = None
    status: Literal["draft", "issued", "approved", "declined", "expired"] = "draft"
    total_amount: decimal.Decimal = Field(..., ge=0)
    drafted_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    valid_until: datetime.date
    issued_at: Optional[datetime.datetime] = None
    decline_reason: Optional[str] = Field(None, max_length=500)


class QuoteUpdate(BaseModel):
    status: Optional[Literal["draft", "issued", "approved", "declined", "expired"]] = None
    total_amount: Optional[decimal.Decimal] = Field(None, ge=0)
    valid_until: Optional[datetime.date] = None
    issued_at: Optional[datetime.datetime] = None
    decline_reason: Optional[str] = Field(None, max_length=500)


class QuoteResponse(QuoteBase):
    quote_id: uuid.UUID
    has_work_order: bool = Field(default=False)
    model_config = ConfigDict(from_attributes=True)


# DEPOSIT
class DepositBase(BaseModel):
    quote_id: uuid.UUID
    customer_id: uuid.UUID
    work_order_id: Optional[uuid.UUID] = None
    amount: decimal.Decimal = Field(..., gt=0)
    status: Literal["collected", "applied", "refunded"] = Field(..., description="collected, applied, refunded")
    collected_at: datetime.datetime
    invoice_id: Optional[uuid.UUID] = None
    refunded_at: Optional[datetime.datetime] = None
    refund_amount: Optional[decimal.Decimal] = Field(None, ge=0)


class DepositCreate(BaseModel):
    quote_id: uuid.UUID
    customer_id: uuid.UUID
    work_order_id: Optional[uuid.UUID] = None
    amount: decimal.Decimal = Field(..., gt=0)
    status: Literal["collected", "applied", "refunded"] = "collected"
    collected_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))


class DepositUpdate(BaseModel):
    work_order_id: Optional[uuid.UUID] = None
    status: Optional[Literal["collected", "applied", "refunded"]] = None
    invoice_id: Optional[uuid.UUID] = None
    refunded_at: Optional[datetime.datetime] = None
    refund_amount: Optional[decimal.Decimal] = Field(None, ge=0)


class DepositResponse(DepositBase):
    deposit_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# ================================================================
# SECTION 4: Job Execution
# ================================================================

# WORK ORDER
class WorkOrderBase(BaseModel):
    quote_id: uuid.UUID
    visit_id: Optional[uuid.UUID] = None
    vehicle_id: str = Field(..., min_length=17, max_length=17)
    customer_id: uuid.UUID
    bay_id: Optional[uuid.UUID] = None
    status: Literal["created", "scheduled", "paused", "active", "closed", "archived"] = Field(
        ..., description="created, scheduled, paused, active, closed, archived"
    )
    authorized_amount: decimal.Decimal = Field(..., ge=0)
    promised_date: Optional[datetime.date] = None
    created_at: datetime.datetime
    scheduled_at: Optional[datetime.datetime] = None
    paused_at: Optional[datetime.datetime] = None
    pause_reason: Optional[str] = Field(None, max_length=500)
    closed_at: Optional[datetime.datetime] = None
    archived_at: Optional[datetime.datetime] = None
    diagnostic_bypassed: bool = False
    bypass_reason: Optional[str] = Field(None, max_length=500)


class WorkOrderCreate(BaseModel):
    quote_id: uuid.UUID
    visit_id: Optional[uuid.UUID] = None
    vehicle_id: str = Field(..., min_length=17, max_length=17)
    customer_id: uuid.UUID
    status: Literal["created", "scheduled", "paused", "active", "closed", "archived"] = "created"
    authorized_amount: decimal.Decimal = Field(..., ge=0)
    promised_date: Optional[datetime.date] = None
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    diagnostic_bypassed: bool = False
    bypass_reason: Optional[str] = Field(None, max_length=500)


class WorkOrderUpdate(BaseModel):
    bay_id: Optional[uuid.UUID] = None
    status: Optional[Literal["created", "scheduled", "paused", "active", "closed", "archived"]] = None
    authorized_amount: Optional[decimal.Decimal] = Field(None, ge=0)
    promised_date: Optional[datetime.date] = None
    scheduled_at: Optional[datetime.datetime] = None
    paused_at: Optional[datetime.datetime] = None
    pause_reason: Optional[str] = Field(None, max_length=500)
    closed_at: Optional[datetime.datetime] = None
    archived_at: Optional[datetime.datetime] = None
    diagnostic_bypassed: Optional[bool] = None
    bypass_reason: Optional[str] = Field(None, max_length=500)


class WorkOrderResponse(WorkOrderBase):
    work_order_id: uuid.UUID
    total_cost: decimal.Decimal
    has_invoice: bool = False
    line_items: List["LineItemResponse"] = []
    model_config = ConfigDict(from_attributes=True)


# LINE ITEM
class LineItemBase(BaseModel):
    work_order_id: uuid.UUID
    description: str = Field(..., max_length=500)
    billing_mode: Literal["flat_rate", "hourly"] = Field(..., description="flat_rate or hourly")
    price: decimal.Decimal = Field(..., ge=0)
    status: Literal["not_started", "gated", "in_progress", "on_hold", "completed"] = Field(
        ..., description="not_started, gated, in_progress, on_hold, completed"
    )
    hold_reason: Optional[str] = Field(None, max_length=500)
    started_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None
    is_complimentary: bool = False
    warranty_required: bool = False


class LineItemCreate(LineItemBase):
    pass


class LineItemUpdate(BaseModel):
    description: Optional[str] = Field(None, max_length=500)
    billing_mode: Optional[Literal["flat_rate", "hourly"]] = Field(None, description="flat_rate or hourly")
    price: Optional[decimal.Decimal] = Field(None, ge=0)
    status: Optional[Literal["not_started", "gated", "in_progress", "on_hold", "completed"]] = None
    hold_reason: Optional[str] = Field(None, max_length=500)
    started_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None
    is_complimentary: Optional[bool] = None
    warranty_required: Optional[bool] = None


class LineItemResponse(LineItemBase):
    line_item_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# CHANGE ORDER
class ChangeOrderBase(BaseModel):
    work_order_id: uuid.UUID
    line_item_id: uuid.UUID
    finding_id: Optional[uuid.UUID] = None
    reason: str = Field(..., max_length=500)
    delta_amount: decimal.Decimal
    approval_status: Literal["issued", "approved", "declined"] = Field(..., description="issued, approved, declined")
    approved_by: Optional[str] = Field(None, max_length=255)
    approved_at: Optional[datetime.datetime] = None
    decline_reason: Optional[str] = Field(None, max_length=500)


class ChangeOrderCreate(ChangeOrderBase):
    pass


class ChangeOrderUpdate(BaseModel):
    approval_status: Optional[Literal["issued", "approved", "declined"]] = None
    approved_by: Optional[str] = Field(None, max_length=255)
    approved_at: Optional[datetime.datetime] = None
    decline_reason: Optional[str] = Field(None, max_length=500)


class ChangeOrderResponse(ChangeOrderBase):
    change_order_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# DIAGNOSTIC FINDING
class DiagnosticFindingBase(BaseModel):
    report_id: uuid.UUID
    description: str = Field(..., max_length=1000)
    recommended_service: Optional[str] = Field(None, max_length=500)
    is_critical: bool = False


class DiagnosticFindingCreate(DiagnosticFindingBase):
    pass


class DiagnosticFindingUpdate(BaseModel):
    description: Optional[str] = Field(None, max_length=1000)
    recommended_service: Optional[str] = Field(None, max_length=500)
    is_critical: Optional[bool] = None


# DIAGNOSTIC TEMPLATE
class DiagnosticTemplateItemBase(BaseModel):
    description: str = Field(..., max_length=500)


class DiagnosticTemplateItemCreate(DiagnosticTemplateItemBase):
    pass


class DiagnosticTemplateItemResponse(DiagnosticTemplateItemBase):
    item_id: uuid.UUID
    template_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


class DiagnosticTemplateBase(BaseModel):
    name: str = Field(..., max_length=200)
    is_active: bool = True


class DiagnosticTemplateCreate(DiagnosticTemplateBase):
    items: List[DiagnosticTemplateItemCreate] = []


class DiagnosticTemplateResponse(DiagnosticTemplateBase):
    template_id: uuid.UUID
    items: List[DiagnosticTemplateItemResponse] = []
    model_config = ConfigDict(from_attributes=True)


class DiagnosticFindingResponse(DiagnosticFindingBase):
    finding_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# DIAGNOSTIC
class DiagnosticBase(BaseModel):
    visit_id: uuid.UUID
    vehicle_id: str = Field(..., min_length=17, max_length=17)
    tech_id: uuid.UUID
    performed_at: datetime.datetime
    status: Literal["in_progress", "completed"] = Field(..., description="in_progress, completed")


class DiagnosticCreate(DiagnosticBase):
    pass


class DiagnosticUpdate(BaseModel):
    status: Optional[Literal["in_progress", "completed"]] = None


class DiagnosticResponse(DiagnosticBase):
    report_id: uuid.UUID
    findings: List[DiagnosticFindingResponse] = []
    model_config = ConfigDict(from_attributes=True)


# QUALITY CHECK
class QualityCheckBase(BaseModel):
    line_item_id: uuid.UUID
    tech_id: uuid.UUID
    performed_at: datetime.datetime
    status: Literal["passed", "failed"] = Field(..., description="passed or failed")


class QualityCheckCreate(QualityCheckBase):
    pass


class QualityCheckResponse(QualityCheckBase):
    qc_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# ================================================================
# SECTION 5: Shop Resources
# ================================================================

# BAY
class BayBase(BaseModel):
    bay_type: str = Field(..., max_length=100)
    status: Literal["available", "held", "confirmed", "occupied", "cleaning", "maintenance"] = Field(
        ..., description="available, held, confirmed, occupied, cleaning, maintenance"
    )
    current_work_order_id: Optional[uuid.UUID] = None
    held_until: Optional[datetime.datetime] = None


class BayCreate(BayBase):
    pass


class BayUpdate(BaseModel):
    bay_type: Optional[str] = Field(None, max_length=100)
    status: Optional[Literal["available", "held", "confirmed", "occupied", "cleaning", "maintenance"]] = None
    current_work_order_id: Optional[uuid.UUID] = None
    held_until: Optional[datetime.datetime] = None


class BayResponse(BayBase):
    bay_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# LABOR ENTRY
class LaborEntryBase(BaseModel):
    tech_id: uuid.UUID
    line_item_id: uuid.UUID
    work_date: datetime.date
    hours: decimal.Decimal = Field(..., gt=0)


class LaborEntryCreate(LaborEntryBase):
    pass


class LaborEntryResponse(LaborEntryBase):
    labor_entry_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# ================================================================
# SECTION 6: Parts & Procurement
# ================================================================

# PART INSTANCE
class PartInstanceBase(BaseModel):
    part_id: uuid.UUID
    po_line_item_id: Optional[uuid.UUID] = None
    line_item_id: Optional[uuid.UUID] = None
    serial_or_lot_number: Optional[str] = Field(None, max_length=100)
    status: Literal[
        "ordered", "shipped", "received", "inspected", "rejected", "returned", "installed"
    ] = Field(..., description="ordered, shipped, received, inspected, rejected, returned, installed")
    received_at: Optional[datetime.datetime] = None
    inspected_at: Optional[datetime.datetime] = None
    rejection_reason: Optional[str] = Field(None, max_length=500)
    installed_at: Optional[datetime.datetime] = None


class PartInstanceCreate(PartInstanceBase):
    pass


class PartInstanceUpdate(BaseModel):
    po_line_item_id: Optional[uuid.UUID] = None
    line_item_id: Optional[uuid.UUID] = None
    serial_or_lot_number: Optional[str] = Field(None, max_length=100)
    status: Optional[Literal[
        "ordered", "shipped", "received", "inspected", "rejected", "returned", "installed"
    ]] = None
    received_at: Optional[datetime.datetime] = None
    inspected_at: Optional[datetime.datetime] = None
    rejection_reason: Optional[str] = Field(None, max_length=500)
    installed_at: Optional[datetime.datetime] = None


class PartInstanceResponse(PartInstanceBase):
    part_instance_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# PURCHASE ORDER
class PurchaseOrderBase(BaseModel):
    vendor_id: uuid.UUID
    status: Literal["submitted", "confirmed", "partially_shipped", "complete", "cancelled"] = Field(
        ..., description="submitted, confirmed, partially_shipped, complete, cancelled"
    )
    submitted_at: datetime.datetime
    confirmed_at: Optional[datetime.datetime] = None
    expected_delivery: Optional[datetime.date] = None
    cancellation_reason: Optional[str] = Field(None, max_length=500)


class PurchaseOrderCreate(BaseModel):
    vendor_id: uuid.UUID
    status: Literal["submitted", "confirmed", "partially_shipped", "complete", "cancelled"] = "submitted"
    submitted_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))


class PurchaseOrderUpdate(BaseModel):
    status: Optional[Literal["submitted", "confirmed", "partially_shipped", "complete", "cancelled"]] = None
    confirmed_at: Optional[datetime.datetime] = None
    expected_delivery: Optional[datetime.date] = None
    cancellation_reason: Optional[str] = Field(None, max_length=500)


class PurchaseOrderResponse(PurchaseOrderBase):
    po_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# PO LINE ITEM
class PoLineItemBase(BaseModel):
    po_id: uuid.UUID
    part_id: uuid.UUID
    qty_ordered: int = Field(..., ge=0)
    qty_shipped: int = Field(..., ge=0)
    qty_received: int = Field(..., ge=0)


class PoLineItemCreate(PoLineItemBase):
    pass


class PoLineItemUpdate(BaseModel):
    qty_ordered: Optional[int] = Field(None, ge=0)
    qty_shipped: Optional[int] = Field(None, ge=0)
    qty_received: Optional[int] = Field(None, ge=0)


class PoLineItemResponse(PoLineItemBase):
    po_line_item_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# CORE
class CoreBase(BaseModel):
    part_id: uuid.UUID
    charge_amount: decimal.Decimal = Field(..., ge=0)
    return_status: Literal["charged", "shipped", "credited"] = Field(..., description="charged, shipped, credited")
    shipped_at: Optional[datetime.datetime] = None


class CoreCreate(CoreBase):
    pass


class CoreUpdate(BaseModel):
    charge_amount: Optional[decimal.Decimal] = Field(None, ge=0)
    return_status: Optional[Literal["charged", "shipped", "credited"]] = None
    shipped_at: Optional[datetime.datetime] = None


class CoreResponse(CoreBase):
    core_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# CREDIT MEMO
class CreditMemoBase(BaseModel):
    vendor_id: uuid.UUID
    amount: decimal.Decimal = Field(..., ge=0)
    status: Literal["pending", "issued"] = Field(..., description="pending, issued")
    core_id: Optional[uuid.UUID] = None
    part_instance_id: Optional[uuid.UUID] = None
    issued_at: Optional[datetime.datetime] = None


class CreditMemoCreate(CreditMemoBase):
    pass


class CreditMemoUpdate(BaseModel):
    amount: Optional[decimal.Decimal] = Field(None, ge=0)
    status: Optional[Literal["pending", "issued"]] = None
    issued_at: Optional[datetime.datetime] = None


class CreditMemoResponse(CreditMemoBase):
    credit_memo_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# ================================================================
# SECTION 7: Billing & Financials
# ================================================================

# INVOICE
class InvoiceBase(BaseModel):
    work_order_id: uuid.UUID
    customer_id: uuid.UUID
    status: Literal["issued", "disputed", "paid", "voided", "credited"] = Field(
        ..., description="issued, disputed, paid, voided, credited"
    )
    amount_due: decimal.Decimal = Field(..., ge=0)
    issued_at: datetime.datetime
    warranty_id: Optional[uuid.UUID] = None
    credit_amount: Optional[decimal.Decimal] = Field(None, ge=0)
    credit_reason: Optional[str] = Field(None, max_length=500)
    tax_rate: Optional[decimal.Decimal] = Field(None, ge=0)
    tax_amount: Optional[decimal.Decimal] = Field(None, ge=0)


class InvoiceCreate(BaseModel):
    work_order_id: uuid.UUID
    customer_id: uuid.UUID
    status: Literal["issued", "disputed", "paid", "voided", "credited"] = "issued"
    amount_due: decimal.Decimal = Field(..., ge=0)
    issued_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))


class InvoiceUpdate(BaseModel):
    status: Optional[Literal["issued", "disputed", "paid", "voided", "credited"]] = None
    amount_due: Optional[decimal.Decimal] = Field(None, ge=0)
    warranty_id: Optional[uuid.UUID] = None
    credit_amount: Optional[decimal.Decimal] = Field(None, ge=0)
    credit_reason: Optional[str] = Field(None, max_length=500)


class InvoiceResponse(InvoiceBase):
    invoice_id: uuid.UUID
    total_balance: decimal.Decimal
    safepay_tracker_id: Optional[str] = None
    safepay_checkout_url: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)



class InvoiceDetailResponse(InvoiceResponse):
    labor_entries: List[LaborEntryResponse] = []
    part_instances: List[PartInstanceResponse] = []
    model_config = ConfigDict(from_attributes=True)


# DISPUTE
class DisputeBase(BaseModel):
    invoice_id: uuid.UUID
    opened_by: Literal["customer", "shop"] = Field(..., description="customer or shop")
    reason: str = Field(..., max_length=1000)
    status: Literal["open", "under_review", "resolved"] = Field(..., description="open, under_review, resolved")
    opened_at: datetime.datetime
    resolved_at: Optional[datetime.datetime] = None
    resolution: Optional[str] = Field(None, max_length=1000)


class DisputeCreate(DisputeBase):
    pass


class DisputeUpdate(BaseModel):
    status: Optional[Literal["open", "under_review", "resolved"]] = None
    resolved_at: Optional[datetime.datetime] = None
    resolution: Optional[str] = Field(None, max_length=1000)
    credit_amount: Optional[decimal.Decimal] = Field(None, ge=0)
    credit_reason: Optional[str] = Field(None, max_length=500)


class DisputeResponse(DisputeBase):
    dispute_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# PAYMENT
class PaymentBase(BaseModel):
    invoice_id: uuid.UUID
    amount: decimal.Decimal = Field(..., gt=0)
    method: str = Field(..., max_length=50)
    collected_at: datetime.datetime
    payer_id: Optional[uuid.UUID] = None
    stripe_payment_intent_id: Optional[str] = None
    stripe_checkout_session_id: Optional[str] = None
    stripe_charge_id: Optional[str] = None
    stripe_refund_id: Optional[str] = None


class PaymentCreate(PaymentBase):
    pass


class PaymentResponse(PaymentBase):
    payment_id: uuid.UUID
    refunded_at: Optional[datetime.datetime] = None
    refund_amount: Optional[decimal.Decimal] = None
    refund_reason: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class StripeCheckoutRequest(BaseModel):
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class StripeCheckoutResponse(BaseModel):
    session_id: str
    checkout_url: str
    invoice_id: uuid.UUID
    amount: decimal.Decimal


class StripePaymentStatusResponse(BaseModel):
    payment_id: uuid.UUID
    stripe_status: str
    stripe_payment_intent_id: Optional[str] = None
    amount: decimal.Decimal
    currency: str = "usd"


# STORAGE CHARGE
class StorageChargeBase(BaseModel):
    visit_id: uuid.UUID
    daily_rate: decimal.Decimal = Field(..., ge=0)
    start_date: datetime.date
    days_accrued: int = Field(..., ge=0)


class StorageChargeCreate(StorageChargeBase):
    pass


class StorageChargeUpdate(BaseModel):
    daily_rate: Optional[decimal.Decimal] = Field(None, ge=0)
    start_date: Optional[datetime.date] = None
    days_accrued: Optional[int] = Field(None, ge=0)


class StorageChargeResponse(StorageChargeBase):
    storage_charge_id: uuid.UUID
    total_charge: decimal.Decimal
    model_config = ConfigDict(from_attributes=True)


# ================================================================
# SECTION 8: Warranties
# ================================================================

# WARRANTY
class WarrantyBase(BaseModel):
    work_order_id: uuid.UUID
    covers_labor: bool = Field(default=False)
    covers_parts: bool = Field(default=False)
    coverage_type: Optional[str] = Field(None, max_length=100)
    term: Optional[str] = Field(None, max_length=100)
    start_date: Optional[datetime.date] = None


class WarrantyCreate(WarrantyBase):
    pass


class WarrantyUpdate(BaseModel):
    covers_labor: Optional[bool] = None
    covers_parts: Optional[bool] = None
    coverage_type: Optional[str] = Field(None, max_length=100)
    term: Optional[str] = Field(None, max_length=100)
    start_date: Optional[datetime.date] = None


class WarrantyResponse(WarrantyBase):
    warranty_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# WARRANTY CLAIM
class WarrantyClaimBase(BaseModel):
    warranty_id: uuid.UUID
    claim_date: datetime.date
    status: Literal["filed", "approved", "denied", "resolved"] = Field(
        ..., description="filed, approved, denied, resolved"
    )
    resolution: Optional[str] = Field(None, max_length=1000)


class WarrantyClaimCreate(WarrantyClaimBase):
    pass


class WarrantyClaimUpdate(BaseModel):
    status: Optional[Literal["filed", "approved", "denied", "resolved"]] = None
    resolution: Optional[str] = Field(None, max_length=1000)


class WarrantyClaimResponse(WarrantyClaimBase):
    claim_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# ================================================================
# SECTION 9: Authentication & Users
# ================================================================

class UserBase(BaseModel):
    username: str = Field(..., max_length=100)
    email: str = Field(..., max_length=255)
    role: Literal["manager", "advisor", "technician", "customer"] = Field(
        default="customer", description="manager, advisor, technician, customer"
    )
    customer_id: Optional[uuid.UUID] = None
    tech_id: Optional[uuid.UUID] = None

    @field_validator("email", mode="before")
    @classmethod
    def check_email(cls, v):
        return _validate_email_str(v)


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)


class UserResponse(UserBase):
    user_id: uuid.UUID
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# ================================================================
# SECTION 10: Reporting Schemas (Phase 2)
# ================================================================

class RevenueByMethod(BaseModel):
    method: str
    total: decimal.Decimal
    count: int


class DailyRevenueReport(BaseModel):
    date: datetime.date
    total_revenue: decimal.Decimal
    invoice_count: int
    breakdown_by_method: List[RevenueByMethod]


class OutstandingARItem(BaseModel):
    invoice_id: uuid.UUID
    customer_name: str
    customer_id: uuid.UUID
    amount_due: decimal.Decimal
    tax_amount: decimal.Decimal
    total_balance: decimal.Decimal
    issued_at: datetime.datetime
    days_outstanding: int


class OutstandingARReport(BaseModel):
    total_outstanding: decimal.Decimal
    invoice_count: int
    items: List[OutstandingARItem]


class TechProductivityItem(BaseModel):
    tech_id: uuid.UUID
    name: str
    total_hours: decimal.Decimal
    total_labor_value: decimal.Decimal
    line_items_completed: int


class TechProductivityReport(BaseModel):
    start_date: datetime.date
    end_date: datetime.date
    technicians: List[TechProductivityItem]


# ================================================================
# SECTION 11: Refund Schemas (Phase 2)
# ================================================================

class RefundRequest(BaseModel):
    amount: decimal.Decimal = Field(..., gt=0)
    reason: str = Field(..., max_length=500)


class PaymentRefundResponse(BaseModel):
    payment_id: uuid.UUID
    invoice_id: uuid.UUID
    amount: decimal.Decimal
    method: str
    collected_at: datetime.datetime
    payer_id: Optional[uuid.UUID] = None
    refunded_at: Optional[datetime.datetime] = None
    refund_amount: Optional[decimal.Decimal] = None
    refund_reason: Optional[str] = None
    stripe_payment_intent_id: Optional[str] = None
    stripe_checkout_session_id: Optional[str] = None
    stripe_charge_id: Optional[str] = None
    stripe_refund_id: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


# ================================================================
# SECTION 12: Vehicle Service History Schemas (Phase 2)
# ================================================================

class ServiceHistoryLineItem(BaseModel):
    description: str
    billing_mode: str
    price: decimal.Decimal
    status: str


class ServiceHistoryEntry(BaseModel):
    work_order_id: uuid.UUID
    status: str
    created_at: datetime.datetime
    closed_at: Optional[datetime.datetime] = None
    quote_total: decimal.Decimal
    line_items: List[ServiceHistoryLineItem]
    invoice_amount: Optional[decimal.Decimal] = None
    invoice_status: Optional[str] = None
    total_paid: Optional[decimal.Decimal] = None


class VehicleServiceHistory(BaseModel):
    vin: str
    make: str
    model: str
    year: int
    customer_name: str
    total_visits: int
    total_spent: decimal.Decimal
    history: List[ServiceHistoryEntry]


# ================================================================
# SECTION 13: Canned Service / Service Menu Schemas (Phase 2)
# ================================================================

class CannedServiceBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    category: Optional[str] = Field(None, max_length=100)
    billing_mode: Literal["flat_rate", "hourly"] = Field(default="flat_rate", description="flat_rate or hourly")
    default_price: decimal.Decimal = Field(default=decimal.Decimal("0.00"), ge=0)
    estimated_hours: Optional[decimal.Decimal] = Field(None, ge=0)
    is_active: bool = True


class CannedServiceCreate(CannedServiceBase):
    pass


class CannedServiceUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    category: Optional[str] = Field(None, max_length=100)
    billing_mode: Optional[Literal["flat_rate", "hourly"]] = None
    default_price: Optional[decimal.Decimal] = Field(None, ge=0)
    estimated_hours: Optional[decimal.Decimal] = Field(None, ge=0)
    is_active: Optional[bool] = None


class CannedServiceResponse(CannedServiceBase):
    service_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# ================================================================
# SECTION 14: User Admin & Password Reset Schemas (Phase 3)
# ================================================================

class PasswordResetRequest(BaseModel):
    email: str

    @field_validator("email", mode="before")
    @classmethod
    def check_email(cls, v):
        return _validate_email_str(v)


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6)


class AdminPasswordReset(BaseModel):
    new_password: str = Field(..., min_length=6)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)


class UserUpdate(BaseModel):
    email: Optional[str] = None
    role: Optional[Literal["manager", "advisor", "technician", "customer"]] = None
    is_active: Optional[bool] = None
    customer_id: Optional[uuid.UUID] = None
    tech_id: Optional[uuid.UUID] = None

    @field_validator("email", mode="before")
    @classmethod
    def check_email(cls, v):
        return _validate_email_str(v)


# ================================================================
# SECTION 15: File Attachment Schemas (Phase 3)
# ================================================================

class FileAttachmentResponse(BaseModel):
    file_id: uuid.UUID
    entity_type: str
    entity_id: str
    original_filename: str
    file_size: int
    mime_type: str
    uploaded_by: Optional[uuid.UUID] = None
    uploaded_at: datetime.datetime
    description: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


# ================================================================
# SECTION 16: Audit Trail Schemas (Phase 3)
# ================================================================

class AuditLogResponse(BaseModel):
    log_id: uuid.UUID
    entity_type: str
    entity_id: str
    action: str
    actor_id: Optional[uuid.UUID] = None
    actor_username: Optional[str] = None
    timestamp: datetime.datetime
    changes: Optional[dict] = None
    model_config = ConfigDict(from_attributes=True)


# ================================================================
# SECTION 17: Generic Envelope Wrapper for Pagination
# ================================================================

T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    total: int
    limit: int
    offset: int
    items: List[T]
