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


# DEPOSIT
class DepositBase(BaseModel):
    quote_id: uuid.UUID
    customer_id: uuid.UUID
    work_order_id: Optional[uuid.UUID] = None
    amount: decimal.Decimal = Field(..., gt=0)
    status: str = Field(..., description="collected, applied, refunded")
    collected_at: datetime.datetime
    invoice_id: Optional[uuid.UUID] = None
    refunded_at: Optional[datetime.datetime] = None
    refund_amount: Optional[decimal.Decimal] = Field(None, ge=0)

class DepositCreate(BaseModel):
    quote_id: uuid.UUID
    customer_id: uuid.UUID
    work_order_id: Optional[uuid.UUID] = None
    amount: decimal.Decimal = Field(..., gt=0)
    status: str = "collected"
    collected_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))

class DepositUpdate(BaseModel):
    work_order_id: Optional[uuid.UUID] = None
    status: Optional[str] = None
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
    status: str = Field(..., description="created, scheduled, paused, active, closed, archived")
    authorized_amount: decimal.Decimal = Field(..., ge=0)
    promised_date: Optional[datetime.date] = None
    created_at: datetime.datetime

class WorkOrderCreate(BaseModel):
    quote_id: uuid.UUID
    visit_id: Optional[uuid.UUID] = None
    vehicle_id: str = Field(..., min_length=17, max_length=17)
    customer_id: uuid.UUID
    status: str = "created"
    authorized_amount: decimal.Decimal = Field(..., ge=0)
    promised_date: Optional[datetime.date] = None
    created_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))

class WorkOrderUpdate(BaseModel):
    bay_id: Optional[uuid.UUID] = None
    status: Optional[str] = None
    authorized_amount: Optional[decimal.Decimal] = Field(None, ge=0)
    promised_date: Optional[datetime.date] = None
    scheduled_at: Optional[datetime.datetime] = None
    paused_at: Optional[datetime.datetime] = None
    pause_reason: Optional[str] = Field(None, max_length=500)
    closed_at: Optional[datetime.datetime] = None
    archived_at: Optional[datetime.datetime] = None

class WorkOrderResponse(WorkOrderBase):
    work_order_id: uuid.UUID
    total_cost: decimal.Decimal
    model_config = ConfigDict(from_attributes=True)


# LINE ITEM
class LineItemBase(BaseModel):
    work_order_id: uuid.UUID
    description: str = Field(..., max_length=500)
    billing_mode: str = Field(..., description="flat_rate or hourly")
    price: decimal.Decimal = Field(..., ge=0)
    status: str = Field(..., description="not_started, gated, in_progress, on_hold, completed")
    hold_reason: Optional[str] = Field(None, max_length=500)
    started_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None

class LineItemCreate(LineItemBase):
    pass

class LineItemUpdate(BaseModel):
    description: Optional[str] = Field(None, max_length=500)
    billing_mode: Optional[str] = Field(None, description="flat_rate or hourly")
    price: Optional[decimal.Decimal] = Field(None, ge=0)
    status: Optional[str] = None
    hold_reason: Optional[str] = Field(None, max_length=500)
    started_at: Optional[datetime.datetime] = None
    completed_at: Optional[datetime.datetime] = None

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
    approval_status: str = Field(..., description="issued, approved, declined")
    approved_by: Optional[str] = Field(None, max_length=255)
    approved_at: Optional[datetime.datetime] = None
    decline_reason: Optional[str] = Field(None, max_length=500)

class ChangeOrderCreate(ChangeOrderBase):
    pass

class ChangeOrderUpdate(BaseModel):
    approval_status: Optional[str] = None
    approved_by: Optional[str] = Field(None, max_length=255)
    approved_at: Optional[datetime.datetime] = None
    decline_reason: Optional[str] = Field(None, max_length=500)

class ChangeOrderResponse(ChangeOrderBase):
    change_order_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# DIAGNOSTIC
class DiagnosticBase(BaseModel):
    visit_id: uuid.UUID
    vehicle_id: str = Field(..., min_length=17, max_length=17)
    tech_id: uuid.UUID
    performed_at: datetime.datetime
    status: str = Field(..., description="in_progress, completed")

class DiagnosticCreate(DiagnosticBase):
    pass

class DiagnosticUpdate(BaseModel):
    status: Optional[str] = None

class DiagnosticResponse(DiagnosticBase):
    report_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# DIAGNOSTIC FINDING
class DiagnosticFindingBase(BaseModel):
    report_id: uuid.UUID
    description: str = Field(..., max_length=1000)

class DiagnosticFindingCreate(DiagnosticFindingBase):
    pass

class DiagnosticFindingUpdate(BaseModel):
    description: Optional[str] = Field(None, max_length=1000)

class DiagnosticFindingResponse(DiagnosticFindingBase):
    finding_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# QUALITY CHECK
class QualityCheckBase(BaseModel):
    line_item_id: uuid.UUID
    tech_id: uuid.UUID
    performed_at: datetime.datetime
    status: str = Field(..., description="passed or failed")

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
    status: str = Field(..., description="available, held, confirmed, occupied, cleaning, maintenance")
    current_work_order_id: Optional[uuid.UUID] = None
    held_until: Optional[datetime.datetime] = None

class BayCreate(BayBase):
    pass

class BayUpdate(BaseModel):
    bay_type: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = None
    current_work_order_id: Optional[uuid.UUID] = None
    held_until: Optional[datetime.datetime] = None

class BayResponse(BayBase):
    bay_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# CERTIFICATION
class CertificationBase(BaseModel):
    tech_id: uuid.UUID
    cert_type: str = Field(..., max_length=100)
    expiry_date: datetime.date

class CertificationCreate(CertificationBase):
    pass

class CertificationResponse(CertificationBase):
    cert_id: uuid.UUID
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
    status: str = Field(..., description="ordered, shipped, received, inspected, rejected, returned, installed")
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
    status: Optional[str] = None
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
    status: str = Field(..., description="submitted, confirmed, partially_shipped, complete, cancelled")
    submitted_at: datetime.datetime
    confirmed_at: Optional[datetime.datetime] = None
    expected_delivery: Optional[datetime.date] = None
    cancellation_reason: Optional[str] = Field(None, max_length=500)

class PurchaseOrderCreate(BaseModel):
    vendor_id: uuid.UUID
    status: str = "submitted"
    submitted_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))

class PurchaseOrderUpdate(BaseModel):
    status: Optional[str] = None
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
    return_status: str = Field(..., description="charged, shipped, credited")
    shipped_at: Optional[datetime.datetime] = None

class CoreCreate(CoreBase):
    pass

class CoreUpdate(BaseModel):
    charge_amount: Optional[decimal.Decimal] = Field(None, ge=0)
    return_status: Optional[str] = None
    shipped_at: Optional[datetime.datetime] = None

class CoreResponse(CoreBase):
    core_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


# CREDIT MEMO
class CreditMemoBase(BaseModel):
    vendor_id: uuid.UUID
    amount: decimal.Decimal = Field(..., ge=0)
    status: str = Field(..., description="pending, issued")
    core_id: Optional[uuid.UUID] = None
    part_instance_id: Optional[uuid.UUID] = None
    issued_at: Optional[datetime.datetime] = None

class CreditMemoCreate(CreditMemoBase):
    pass

class CreditMemoUpdate(BaseModel):
    amount: Optional[decimal.Decimal] = Field(None, ge=0)
    status: Optional[str] = None
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
    status: str = Field(..., description="issued, disputed, paid, voided, credited")
    amount_due: decimal.Decimal = Field(..., ge=0)
    issued_at: datetime.datetime
    warranty_id: Optional[uuid.UUID] = None
    credit_amount: Optional[decimal.Decimal] = Field(None, ge=0)
    credit_reason: Optional[str] = Field(None, max_length=500)

class InvoiceCreate(BaseModel):
    work_order_id: uuid.UUID
    customer_id: uuid.UUID
    status: str = "issued"
    amount_due: decimal.Decimal = Field(..., ge=0)
    issued_at: datetime.datetime = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))

class InvoiceUpdate(BaseModel):
    status: Optional[str] = None
    amount_due: Optional[decimal.Decimal] = Field(None, ge=0)
    warranty_id: Optional[uuid.UUID] = None
    credit_amount: Optional[decimal.Decimal] = Field(None, ge=0)
    credit_reason: Optional[str] = Field(None, max_length=500)

class InvoiceResponse(InvoiceBase):
    invoice_id: uuid.UUID
    total_balance: decimal.Decimal
    model_config = ConfigDict(from_attributes=True)


# DISPUTE
class DisputeBase(BaseModel):
    invoice_id: uuid.UUID
    opened_by: str = Field(..., description="customer or shop")
    reason: str = Field(..., max_length=1000)
    status: str = Field(..., description="open, under_review, resolved")
    opened_at: datetime.datetime
    resolved_at: Optional[datetime.datetime] = None
    resolution: Optional[str] = Field(None, max_length=1000)

class DisputeCreate(DisputeBase):
    pass

class DisputeUpdate(BaseModel):
    status: Optional[str] = None
    resolved_at: Optional[datetime.datetime] = None
    resolution: Optional[str] = Field(None, max_length=1000)

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

class PaymentCreate(PaymentBase):
    pass

class PaymentResponse(PaymentBase):
    payment_id: uuid.UUID
    model_config = ConfigDict(from_attributes=True)


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
