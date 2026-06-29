from typing import Optional
import datetime
import decimal
import uuid

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, Numeric, PrimaryKeyConstraint, String, UniqueConstraint, Uuid, text, event
from sqlalchemy.sql import func, select
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from sqlalchemy.ext.hybrid import hybrid_property
from app.database import Base

# ================================================================
# SECTION 1: Independent Core Entities (No Foreign Keys)
# ================================================================

class Customer(Base):
    __tablename__ = 'customer'
    __table_args__ = (
        CheckConstraint("customer_type::text = ANY (ARRAY['individual'::character varying, 'fleet'::character varying]::text[])", name='customer_customer_type_check'),
        PrimaryKeyConstraint('customer_id', name='customer_pkey')
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_type: Mapped[str] = mapped_column(String(20), nullable=False)
    tax_exempt: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    billing_address: Mapped[Optional[str]] = mapped_column(String(500))

    appointments: Mapped[list['Appointment']] = relationship('Appointment', back_populates='customer')
    quotes: Mapped[list['Quote']] = relationship('Quote', back_populates='customer')
    visits: Mapped[list['Visit']] = relationship('Visit', back_populates='customer')
    work_orders: Mapped[list['WorkOrder']] = relationship('WorkOrder', back_populates='customer')
    vehicles: Mapped[list['Vehicle']] = relationship('Vehicle', back_populates='customer')
    invoices: Mapped[list['Invoice']] = relationship('Invoice', back_populates='customer')
    deposits: Mapped[list['Deposit']] = relationship('Deposit', back_populates='customer')

    @validates('customer_type')
    def validate_customer_type(self, key, value):
        if value not in ('individual', 'fleet'):
            raise ValueError(f"Invalid customer_type: '{value}'. Must be 'individual' or 'fleet'.")
        return value


class Vendor(Base):
    __tablename__ = 'vendor'
    __table_args__ = (
        PrimaryKeyConstraint('vendor_id', name='vendor_pkey'),
    )

    vendor_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    vendor_type: Mapped[Optional[str]] = mapped_column(String(100))

    purchase_orders: Mapped[list['PurchaseOrder']] = relationship('PurchaseOrder', back_populates='vendor')
    credit_memos: Mapped[list['CreditMemo']] = relationship('CreditMemo', back_populates='vendor')


class Technician(Base):
    __tablename__ = 'technician'
    __table_args__ = (
        CheckConstraint('hourly_rate >= 0::numeric', name='technician_hourly_rate_check'),
        PrimaryKeyConstraint('tech_id', name='technician_pkey')
    )

    tech_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    hourly_rate: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    certifications: Mapped[list['Certification']] = relationship('Certification', back_populates='technician')
    diagnostics: Mapped[list['Diagnostic']] = relationship('Diagnostic', back_populates='technician')
    labor_entries: Mapped[list['LaborEntry']] = relationship('LaborEntry', back_populates='technician')
    quality_checks: Mapped[list['QualityCheck']] = relationship('QualityCheck', back_populates='technician')

    @validates('hourly_rate')
    def validate_hourly_rate(self, key, value):
        decimal_val = decimal.Decimal(str(value))
        if decimal_val < 0:
            raise ValueError("hourly_rate cannot be negative.")
        return decimal_val


class Part(Base):
    __tablename__ = 'part'
    __table_args__ = (
        CheckConstraint('quantity_on_hand >= 0', name='part_quantity_on_hand_check'),
        PrimaryKeyConstraint('part_id', name='part_pkey'),
        UniqueConstraint('part_number', name='part_part_number_key')
    )

    part_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    part_number: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity_on_hand: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    is_returnable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    category: Mapped[Optional[str]] = mapped_column(String(100))

    cores: Mapped[list['Core']] = relationship('Core', back_populates='part')
    po_line_items: Mapped[list['PoLineItem']] = relationship('PoLineItem', back_populates='part')
    part_instances: Mapped[list['PartInstance']] = relationship('PartInstance', back_populates='part')

    @validates('quantity_on_hand')
    def validate_quantity_on_hand(self, key, value):
        if value < 0:
            raise ValueError("quantity_on_hand cannot be negative.")
        return value


class Payer(Base):
    __tablename__ = 'payer'
    __table_args__ = (
        CheckConstraint("payer_type::text = ANY (ARRAY['insurer'::character varying, 'warranty_company'::character varying, 'fleet_account'::character varying]::text[])", name='payer_payer_type_check'),
        PrimaryKeyConstraint('payer_id', name='payer_pkey')
    )

    payer_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    payer_type: Mapped[str] = mapped_column(String(30), nullable=False)
    contact_info: Mapped[Optional[str]] = mapped_column(String(500))
    billing_terms: Mapped[Optional[str]] = mapped_column(String(255))
    account_number: Mapped[Optional[str]] = mapped_column(String(100))

    payments: Mapped[list['Payment']] = relationship('Payment', back_populates='payer')

    @validates('payer_type')
    def validate_payer_type(self, key, value):
        if value not in ('insurer', 'warranty_company', 'fleet_account'):
            raise ValueError(f"Invalid payer_type: '{value}'. Must be 'insurer', 'warranty_company', or 'fleet_account'.")
        return value


# ================================================================
# SECTION 2: First-Level Dependent Entities
# ================================================================

class Vehicle(Base):
    __tablename__ = 'vehicle'
    __table_args__ = (
        CheckConstraint('current_mileage >= 0', name='vehicle_current_mileage_check'),
        CheckConstraint('year >= 1900 AND year <= 2100', name='vehicle_year_check'),
        ForeignKeyConstraint(['customer_id'], ['customer.customer_id'], ondelete='RESTRICT', name='vehicle_customer_id_fkey'),
        PrimaryKeyConstraint('vin', name='vehicle_pkey'),
        Index('idx_vehicle_customer', 'customer_id')
    )

    vin: Mapped[str] = mapped_column(String(17), primary_key=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    make: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    current_mileage: Mapped[Optional[int]] = mapped_column(Integer)

    customer: Mapped['Customer'] = relationship('Customer', back_populates='vehicles')
    appointments: Mapped[list['Appointment']] = relationship('Appointment', back_populates='vehicle')
    quotes: Mapped[list['Quote']] = relationship('Quote', back_populates='vehicle')
    visits: Mapped[list['Visit']] = relationship('Visit', back_populates='vehicle')
    work_orders: Mapped[list['WorkOrder']] = relationship('WorkOrder', back_populates='vehicle')
    diagnostics: Mapped[list['Diagnostic']] = relationship('Diagnostic', back_populates='vehicle')

    @validates('current_mileage')
    def validate_current_mileage(self, key, value):
        if value is not None and value < 0:
            raise ValueError("current_mileage cannot be negative.")
        return value

    @validates('year')
    def validate_year(self, key, value):
        if value < 1900 or value > 2100:
            raise ValueError("year must be between 1900 and 2100.")
        return value


class Certification(Base):
    __tablename__ = 'certification'
    __table_args__ = (
        ForeignKeyConstraint(['tech_id'], ['technician.tech_id'], ondelete='RESTRICT', name='certification_tech_id_fkey'),
        PrimaryKeyConstraint('cert_id', name='certification_pkey'),
        Index('idx_certification_tech', 'tech_id')
    )

    cert_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    tech_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    cert_type: Mapped[str] = mapped_column(String(100), nullable=False)
    expiry_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)

    technician: Mapped['Technician'] = relationship('Technician', back_populates='certifications')


class Bay(Base):
    __tablename__ = 'bay'
    __table_args__ = (
        CheckConstraint("status::text = ANY (ARRAY['available'::character varying, 'held'::character varying, 'confirmed'::character varying, 'occupied'::character varying, 'cleaning'::character varying, 'maintenance'::character varying]::text[])", name='bay_status_check'),
        ForeignKeyConstraint(['current_work_order_id'], ['work_order.work_order_id'], ondelete='SET NULL', name='fk_bay_current_work_order'),
        PrimaryKeyConstraint('bay_id', name='bay_pkey'),
        Index('idx_bay_current_work_order', 'current_work_order_id')
    )

    bay_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'available'::character varying"))
    bay_type: Mapped[Optional[str]] = mapped_column(String(100))
    current_work_order_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    held_until: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))

    appointments: Mapped[list['Appointment']] = relationship('Appointment', back_populates='bay')
    current_work_order: Mapped[Optional['WorkOrder']] = relationship('WorkOrder', foreign_keys=[current_work_order_id], back_populates='current_bays', post_update=True)
    work_orders: Mapped[list['WorkOrder']] = relationship('WorkOrder', foreign_keys='[WorkOrder.bay_id]', back_populates='bay')


# ================================================================
# SECTION 3: Operations & Front-Office Workflow
# ================================================================

class Appointment(Base):
    __tablename__ = 'appointment'
    __table_args__ = (
        CheckConstraint("status::text = ANY (ARRAY['requested'::character varying, 'confirmed'::character varying, 'cancelled'::character varying]::text[])", name='appointment_status_check'),
        ForeignKeyConstraint(['bay_id'], ['bay.bay_id'], ondelete='SET NULL', name='appointment_bay_id_fkey'),
        ForeignKeyConstraint(['customer_id'], ['customer.customer_id'], ondelete='RESTRICT', name='appointment_customer_id_fkey'),
        ForeignKeyConstraint(['vehicle_id'], ['vehicle.vin'], ondelete='RESTRICT', name='appointment_vehicle_id_fkey'),
        PrimaryKeyConstraint('appointment_id', name='appointment_pkey'),
        Index('idx_appointment_bay', 'bay_id'),
        Index('idx_appointment_customer', 'customer_id'),
        Index('idx_appointment_vehicle', 'vehicle_id')
    )

    appointment_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    vehicle_id: Mapped[str] = mapped_column(String(17), nullable=False)
    requested_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'requested'::character varying"))
    bay_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    confirmed_date: Mapped[Optional[datetime.date]] = mapped_column(Date)

    bay: Mapped[Optional['Bay']] = relationship('Bay', back_populates='appointments')
    customer: Mapped['Customer'] = relationship('Customer', back_populates='appointments')
    vehicle: Mapped['Vehicle'] = relationship('Vehicle', back_populates='appointments')
    visits: Mapped[list['Visit']] = relationship('Visit', back_populates='appointment')

    @validates('requested_date')
    def validate_requested_date(self, key, value):
        if isinstance(value, str):
            value = datetime.datetime.strptime(value, "%Y-%m-%d").date()
        elif isinstance(value, datetime.datetime):
            value = value.date()
        if value < datetime.date.today():
            raise ValueError("requested_date cannot be in the past.")
        return value

    @validates('status')
    def validate_status(self, key, value):
        if value not in ('requested', 'confirmed', 'cancelled'):
            raise ValueError(f"Invalid status: '{value}'. Must be 'requested', 'confirmed', or 'cancelled'.")
        return value


class Visit(Base):
    __tablename__ = 'visit'
    __table_args__ = (
        CheckConstraint("status::text = ANY (ARRAY['checked_in'::character varying, 'in_diagnosis'::character varying, 'awaiting_quote'::character varying, 'in_service'::character varying, 'awaiting_pickup'::character varying, 'completed'::character varying]::text[])", name='visit_status_check'),
        ForeignKeyConstraint(['appointment_id'], ['appointment.appointment_id'], ondelete='SET NULL', name='visit_appointment_id_fkey'),
        ForeignKeyConstraint(['customer_id'], ['customer.customer_id'], ondelete='RESTRICT', name='visit_customer_id_fkey'),
        ForeignKeyConstraint(['vehicle_id'], ['vehicle.vin'], ondelete='RESTRICT', name='visit_vehicle_id_fkey'),
        PrimaryKeyConstraint('visit_id', name='visit_pkey'),
        Index('idx_visit_appointment', 'appointment_id'),
        Index('idx_visit_customer', 'customer_id'),
        Index('idx_visit_vehicle', 'vehicle_id')
    )

    visit_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    vehicle_id: Mapped[str] = mapped_column(String(17), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    checked_in_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'checked_in'::character varying"))
    appointment_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    checked_out_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))

    appointment: Mapped[Optional['Appointment']] = relationship('Appointment', back_populates='visits')
    customer: Mapped['Customer'] = relationship('Customer', back_populates='visits')
    vehicle: Mapped['Vehicle'] = relationship('Vehicle', back_populates='visits')
    quotes: Mapped[list['Quote']] = relationship('Quote', back_populates='visit')
    work_orders: Mapped[list['WorkOrder']] = relationship('WorkOrder', back_populates='visit')
    storage_charges: Mapped[list['StorageCharge']] = relationship('StorageCharge', back_populates='visit')
    diagnostics: Mapped[list['Diagnostic']] = relationship('Diagnostic', back_populates='visit')

    @validates('status')
    def validate_status(self, key, value):
        allowed_statuses = {'checked_in', 'in_diagnosis', 'awaiting_quote', 'in_service', 'awaiting_pickup', 'completed'}
        if value not in allowed_statuses:
            raise ValueError(f"Invalid status: '{value}'.")
        
        from sqlalchemy.orm.attributes import NO_VALUE
        from sqlalchemy import inspect
        
        try:
            insp = inspect(self)
            committed = insp.attrs.status.loaded_value
            if committed is not NO_VALUE and committed is not None:
                old_status = committed
                if old_status != value:
                    transitions = {
                        'checked_in': {'in_diagnosis', 'awaiting_quote', 'in_service'},
                        'in_diagnosis': {'awaiting_quote', 'in_service'},
                        'awaiting_quote': {'in_service', 'completed'},
                        'in_service': {'awaiting_pickup'},
                        'awaiting_pickup': {'completed'},
                        'completed': set()
                    }
                    allowed_next = transitions.get(old_status, set())
                    if value not in allowed_next:
                        raise ValueError(f"Invalid state transition from '{old_status}' to '{value}'.")
        except Exception as e:
            if isinstance(e, ValueError):
                raise e
        return value

    @hybrid_property
    def is_active(self) -> bool:
        return self.checked_out_at is None

    @is_active.expression
    def is_active(cls):
        return cls.checked_out_at.is_(None)




class Quote(Base):
    __tablename__ = 'quote'
    __table_args__ = (
        CheckConstraint("status::text = ANY (ARRAY['draft'::character varying, 'issued'::character varying, 'approved'::character varying, 'declined'::character varying, 'expired'::character varying]::text[])", name='quote_status_check'),
        CheckConstraint('total_amount >= 0::numeric', name='quote_total_amount_check'),
        ForeignKeyConstraint(['customer_id'], ['customer.customer_id'], ondelete='RESTRICT', name='quote_customer_id_fkey'),
        ForeignKeyConstraint(['vehicle_id'], ['vehicle.vin'], ondelete='RESTRICT', name='quote_vehicle_id_fkey'),
        ForeignKeyConstraint(['visit_id'], ['visit.visit_id'], ondelete='SET NULL', name='quote_visit_id_fkey'),
        PrimaryKeyConstraint('quote_id', name='quote_pkey'),
        Index('idx_quote_customer', 'customer_id'),
        Index('idx_quote_vehicle', 'vehicle_id'),
        Index('idx_quote_visit', 'visit_id')
    )

    quote_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    vehicle_id: Mapped[str] = mapped_column(String(17), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'draft'::character varying"))
    total_amount: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    drafted_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    valid_until: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    visit_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    issued_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    decline_reason: Mapped[Optional[str]] = mapped_column(String(500))

    customer: Mapped['Customer'] = relationship('Customer', back_populates='quotes')
    vehicle: Mapped['Vehicle'] = relationship('Vehicle', back_populates='quotes')
    visit: Mapped[Optional['Visit']] = relationship('Visit', back_populates='quotes')
    work_order: Mapped['WorkOrder'] = relationship('WorkOrder', uselist=False, back_populates='quote')
    deposits: Mapped[list['Deposit']] = relationship('Deposit', back_populates='quote')

    @validates('total_amount')
    def validate_total_amount(self, key, value):
        decimal_val = decimal.Decimal(str(value))
        if decimal_val < 0:
            raise ValueError("total_amount cannot be negative.")
        return decimal_val

    @validates('status')
    def validate_status(self, key, value):
        if value not in ('draft', 'issued', 'approved', 'declined', 'expired'):
            raise ValueError(f"Invalid status: '{value}'. Must be 'draft', 'issued', 'approved', 'declined', or 'expired'.")
        return value


class WorkOrder(Base):
    __tablename__ = 'work_order'
    __table_args__ = (
        CheckConstraint('authorized_amount >= 0::numeric', name='work_order_authorized_amount_check'),
        CheckConstraint("status::text = ANY (ARRAY['created'::character varying, 'scheduled'::character varying, 'paused'::character varying, 'active'::character varying, 'closed'::character varying, 'archived'::character varying]::text[])", name='work_order_status_check'),
        ForeignKeyConstraint(['bay_id'], ['bay.bay_id'], ondelete='SET NULL', name='work_order_bay_id_fkey'),
        ForeignKeyConstraint(['customer_id'], ['customer.customer_id'], ondelete='RESTRICT', name='work_order_customer_id_fkey'),
        ForeignKeyConstraint(['quote_id'], ['quote.quote_id'], ondelete='RESTRICT', name='work_order_quote_id_fkey'),
        ForeignKeyConstraint(['vehicle_id'], ['vehicle.vin'], ondelete='RESTRICT', name='work_order_vehicle_id_fkey'),
        ForeignKeyConstraint(['visit_id'], ['visit.visit_id'], ondelete='SET NULL', name='work_order_visit_id_fkey'),
        PrimaryKeyConstraint('work_order_id', name='work_order_pkey'),
        UniqueConstraint('quote_id', name='work_order_quote_id_key'),
        Index('idx_work_order_bay', 'bay_id'),
        Index('idx_work_order_customer', 'customer_id'),
        Index('idx_work_order_vehicle', 'vehicle_id'),
        Index('idx_work_order_visit', 'visit_id')
    )

    work_order_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    quote_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    vehicle_id: Mapped[str] = mapped_column(String(17), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'created'::character varying"))
    authorized_amount: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    visit_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    bay_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    promised_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    scheduled_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    paused_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    pause_reason: Mapped[Optional[str]] = mapped_column(String(500))
    closed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    archived_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))

    current_bays: Mapped[list['Bay']] = relationship('Bay', foreign_keys='[Bay.current_work_order_id]', back_populates='current_work_order')
    bay: Mapped[Optional['Bay']] = relationship('Bay', foreign_keys=[bay_id], back_populates='work_orders')
    customer: Mapped['Customer'] = relationship('Customer', back_populates='work_orders')
    quote: Mapped['Quote'] = relationship('Quote', back_populates='work_order')
    vehicle: Mapped['Vehicle'] = relationship('Vehicle', back_populates='work_orders')
    visit: Mapped[Optional['Visit']] = relationship('Visit', back_populates='work_orders')
    line_items: Mapped[list['LineItem']] = relationship('LineItem', back_populates='work_order')
    warranty: Mapped['Warranty'] = relationship('Warranty', uselist=False, back_populates='work_order')
    invoice: Mapped['Invoice'] = relationship('Invoice', uselist=False, back_populates='work_order')
    deposits: Mapped[list['Deposit']] = relationship('Deposit', back_populates='work_order')
    change_orders: Mapped[list['ChangeOrder']] = relationship('ChangeOrder', back_populates='work_order')

    @validates('authorized_amount')
    def validate_authorized_amount(self, key, value):
        decimal_val = decimal.Decimal(str(value))
        if decimal_val < 0:
            raise ValueError("authorized_amount cannot be negative.")
        return decimal_val

    @validates('status')
    def validate_status(self, key, value):
        if value not in ('created', 'scheduled', 'paused', 'active', 'closed', 'archived'):
            raise ValueError(f"Invalid status: '{value}'. Must be 'created', 'scheduled', 'paused', 'active', 'closed', or 'archived'.")
        return value

    @hybrid_property
    def total_cost(self) -> decimal.Decimal:
        from sqlalchemy import inspect
        try:
            insp = inspect(self)
            if 'line_items' in insp.unloaded:
                return decimal.Decimal('0.00')
        except Exception:
            pass
        return sum(item.price for item in self.line_items)

    @total_cost.expression
    def total_cost(cls):
        from app.models.models import LineItem
        return (
            select(func.sum(LineItem.price))
            .where(LineItem.work_order_id == cls.work_order_id)
            .correlate_except(LineItem)
            .scalar_subquery()
        )


# ================================================================
# SECTION 4: Execution / Line Items
# ================================================================

class LineItem(Base):
    __tablename__ = 'line_item'
    __table_args__ = (
        CheckConstraint("billing_mode::text = ANY (ARRAY['flat_rate'::character varying, 'hourly'::character varying]::text[])", name='line_item_billing_mode_check'),
        CheckConstraint('price >= 0::numeric', name='line_item_price_check'),
        CheckConstraint("status::text = ANY (ARRAY['not_started'::character varying, 'gated'::character varying, 'in_progress'::character varying, 'on_hold'::character varying, 'completed'::character varying]::text[])", name='line_item_status_check'),
        ForeignKeyConstraint(['work_order_id'], ['work_order.work_order_id'], ondelete='RESTRICT', name='line_item_work_order_id_fkey'),
        PrimaryKeyConstraint('line_item_id', name='line_item_pkey'),
        Index('idx_line_item_work_order', 'work_order_id')
    )

    line_item_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    work_order_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    billing_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    price: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'not_started'::character varying"))
    hold_reason: Mapped[Optional[str]] = mapped_column(String(500))
    started_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))

    work_order: Mapped['WorkOrder'] = relationship('WorkOrder', back_populates='line_items')
    labor_entries: Mapped[list['LaborEntry']] = relationship('LaborEntry', back_populates='line_item')
    quality_checks: Mapped[list['QualityCheck']] = relationship('QualityCheck', back_populates='line_item')
    part_instances: Mapped[list['PartInstance']] = relationship('PartInstance', back_populates='line_item')
    change_orders: Mapped[list['ChangeOrder']] = relationship('ChangeOrder', back_populates='line_item')

    @validates('price')
    def validate_price(self, key, value):
        decimal_val = decimal.Decimal(str(value))
        if decimal_val < 0:
            raise ValueError("price cannot be negative.")
        return decimal_val

    @validates('billing_mode')
    def validate_billing_mode(self, key, value):
        if value not in ('flat_rate', 'hourly'):
            raise ValueError(f"Invalid billing_mode: '{value}'. Must be 'flat_rate' or 'hourly'.")
        return value

    @validates('status')
    def validate_status(self, key, value):
        if value not in ('not_started', 'gated', 'in_progress', 'on_hold', 'completed'):
            raise ValueError(f"Invalid status: '{value}'. Must be 'not_started', 'gated', 'in_progress', 'on_hold', or 'completed'.")
        return value


class Diagnostic(Base):
    __tablename__ = 'diagnostic'
    __table_args__ = (
        CheckConstraint("status::text = ANY (ARRAY['in_progress'::character varying, 'completed'::character varying]::text[])", name='diagnostic_status_check'),
        ForeignKeyConstraint(['tech_id'], ['technician.tech_id'], ondelete='RESTRICT', name='diagnostic_tech_id_fkey'),
        ForeignKeyConstraint(['vehicle_id'], ['vehicle.vin'], ondelete='RESTRICT', name='diagnostic_vehicle_id_fkey'),
        ForeignKeyConstraint(['visit_id'], ['visit.visit_id'], ondelete='RESTRICT', name='diagnostic_visit_id_fkey'),
        PrimaryKeyConstraint('report_id', name='diagnostic_pkey'),
        Index('idx_diagnostic_tech', 'tech_id'),
        Index('idx_diagnostic_vehicle', 'vehicle_id'),
        Index('idx_diagnostic_visit', 'visit_id')
    )

    report_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    visit_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    vehicle_id: Mapped[str] = mapped_column(String(17), nullable=False)
    tech_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    performed_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'in_progress'::character varying"))

    technician: Mapped['Technician'] = relationship('Technician', back_populates='diagnostics')
    vehicle: Mapped['Vehicle'] = relationship('Vehicle', back_populates='diagnostics')
    visit: Mapped['Visit'] = relationship('Visit', back_populates='diagnostics')
    findings: Mapped[list['DiagnosticFinding']] = relationship('DiagnosticFinding', back_populates='report')


class DiagnosticFinding(Base):
    __tablename__ = 'diagnostic_finding'
    __table_args__ = (
        ForeignKeyConstraint(['report_id'], ['diagnostic.report_id'], ondelete='RESTRICT', name='diagnostic_finding_report_id_fkey'),
        PrimaryKeyConstraint('finding_id', name='diagnostic_finding_pkey'),
        Index('idx_diagnostic_finding_report', 'report_id')
    )

    finding_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    report_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)

    report: Mapped['Diagnostic'] = relationship('Diagnostic', back_populates='findings')
    change_order: Mapped[Optional['ChangeOrder']] = relationship('ChangeOrder', uselist=False, back_populates='finding')


class LaborEntry(Base):
    __tablename__ = 'labor_entry'
    __table_args__ = (
        CheckConstraint('hours > 0::numeric', name='labor_entry_hours_check'),
        ForeignKeyConstraint(['line_item_id'], ['line_item.line_item_id'], ondelete='RESTRICT', name='labor_entry_line_item_id_fkey'),
        ForeignKeyConstraint(['tech_id'], ['technician.tech_id'], ondelete='RESTRICT', name='labor_entry_tech_id_fkey'),
        PrimaryKeyConstraint('labor_entry_id', name='labor_entry_pkey'),
        Index('idx_labor_entry_line_item', 'line_item_id'),
        Index('idx_labor_entry_tech', 'tech_id')
    )

    labor_entry_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    tech_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    line_item_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    work_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    hours: Mapped[decimal.Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    line_item: Mapped['LineItem'] = relationship('LineItem', back_populates='labor_entries')
    technician: Mapped['Technician'] = relationship('Technician', back_populates='labor_entries')

    @validates('hours')
    def validate_hours(self, key, value):
        decimal_val = decimal.Decimal(str(value))
        if decimal_val <= 0:
            raise ValueError("hours must be greater than zero.")
        return decimal_val


class QualityCheck(Base):
    __tablename__ = 'quality_check'
    __table_args__ = (
        CheckConstraint("status::text = ANY (ARRAY['passed'::character varying, 'failed'::character varying]::text[])", name='quality_check_status_check'),
        ForeignKeyConstraint(['line_item_id'], ['line_item.line_item_id'], ondelete='RESTRICT', name='quality_check_line_item_id_fkey'),
        ForeignKeyConstraint(['tech_id'], ['technician.tech_id'], ondelete='RESTRICT', name='quality_check_tech_id_fkey'),
        PrimaryKeyConstraint('qc_id', name='quality_check_pkey'),
        Index('idx_quality_check_line_item', 'line_item_id'),
        Index('idx_quality_check_tech', 'tech_id')
    )

    qc_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    line_item_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    tech_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    performed_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    status: Mapped[str] = mapped_column(String(20), nullable=False)

    line_item: Mapped['LineItem'] = relationship('LineItem', back_populates='quality_checks')
    technician: Mapped['Technician'] = relationship('Technician', back_populates='quality_checks')


class ChangeOrder(Base):
    __tablename__ = 'change_order'
    __table_args__ = (
        CheckConstraint("approval_status::text = ANY (ARRAY['issued'::character varying, 'approved'::character varying, 'declined'::character varying]::text[])", name='change_order_approval_status_check'),
        ForeignKeyConstraint(['finding_id'], ['diagnostic_finding.finding_id'], ondelete='SET NULL', name='change_order_finding_id_fkey'),
        ForeignKeyConstraint(['line_item_id'], ['line_item.line_item_id'], ondelete='RESTRICT', name='change_order_line_item_id_fkey'),
        ForeignKeyConstraint(['work_order_id'], ['work_order.work_order_id'], ondelete='RESTRICT', name='change_order_work_order_id_fkey'),
        PrimaryKeyConstraint('change_order_id', name='change_order_pkey'),
        UniqueConstraint('finding_id', name='change_order_finding_id_key'),
        Index('idx_change_order_line_item', 'line_item_id'),
        Index('idx_change_order_work_order', 'work_order_id')
    )

    change_order_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    work_order_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    line_item_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    delta_amount: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    approval_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'issued'::character varying"))
    finding_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    approved_by: Mapped[Optional[str]] = mapped_column(String(255))
    approved_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    decline_reason: Mapped[Optional[str]] = mapped_column(String(500))

    finding: Mapped[Optional['DiagnosticFinding']] = relationship('DiagnosticFinding', back_populates='change_order')
    line_item: Mapped['LineItem'] = relationship('LineItem', back_populates='change_orders')
    work_order: Mapped['WorkOrder'] = relationship('WorkOrder', back_populates='change_orders')


# ================================================================
# SECTION 5: Procurement & Inventory
# ================================================================

class PurchaseOrder(Base):
    __tablename__ = 'purchase_order'
    __table_args__ = (
        CheckConstraint("status::text = ANY (ARRAY['submitted'::character varying, 'confirmed'::character varying, 'partially_shipped'::character varying, 'complete'::character varying, 'cancelled'::character varying]::text[])", name='purchase_order_status_check'),
        ForeignKeyConstraint(['vendor_id'], ['vendor.vendor_id'], ondelete='RESTRICT', name='purchase_order_vendor_id_fkey'),
        PrimaryKeyConstraint('po_id', name='purchase_order_pkey'),
        Index('idx_purchase_order_vendor', 'vendor_id')
    )

    po_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    vendor_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'submitted'::character varying"))
    submitted_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    confirmed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    expected_delivery: Mapped[Optional[datetime.date]] = mapped_column(Date)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(String(500))

    vendor: Mapped['Vendor'] = relationship('Vendor', back_populates='purchase_orders')
    po_line_items: Mapped[list['PoLineItem']] = relationship('PoLineItem', back_populates='purchase_order')


class PoLineItem(Base):
    __tablename__ = 'po_line_item'
    __table_args__ = (
        CheckConstraint('qty_ordered > 0', name='po_line_item_qty_ordered_check'),
        CheckConstraint('qty_received >= 0', name='po_line_item_qty_received_check'),
        CheckConstraint('qty_shipped >= 0', name='po_line_item_qty_shipped_check'),
        ForeignKeyConstraint(['part_id'], ['part.part_id'], ondelete='RESTRICT', name='po_line_item_part_id_fkey'),
        ForeignKeyConstraint(['po_id'], ['purchase_order.po_id'], ondelete='RESTRICT', name='po_line_item_po_id_fkey'),
        PrimaryKeyConstraint('po_line_item_id', name='po_line_item_pkey'),
        Index('idx_po_line_item_part', 'part_id'),
        Index('idx_po_line_item_po', 'po_id')
    )

    po_line_item_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    po_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    part_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    qty_ordered: Mapped[int] = mapped_column(Integer, nullable=False)
    qty_shipped: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    qty_received: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))

    part: Mapped['Part'] = relationship('Part', back_populates='po_line_items')
    purchase_order: Mapped['PurchaseOrder'] = relationship('PurchaseOrder', back_populates='po_line_items')
    part_instances: Mapped[list['PartInstance']] = relationship('PartInstance', back_populates='po_line_item')


class PartInstance(Base):
    __tablename__ = 'part_instance'
    __table_args__ = (
        CheckConstraint("status::text = ANY (ARRAY['ordered'::character varying, 'shipped'::character varying, 'received'::character varying, 'inspected'::character varying, 'rejected'::character varying, 'returned'::character varying, 'installed'::character varying]::text[])", name='part_instance_status_check'),
        ForeignKeyConstraint(['line_item_id'], ['line_item.line_item_id'], ondelete='SET NULL', name='part_instance_line_item_id_fkey'),
        ForeignKeyConstraint(['part_id'], ['part.part_id'], ondelete='RESTRICT', name='part_instance_part_id_fkey'),
        ForeignKeyConstraint(['po_line_item_id'], ['po_line_item.po_line_item_id'], ondelete='SET NULL', name='part_instance_po_line_item_id_fkey'),
        PrimaryKeyConstraint('part_instance_id', name='part_instance_pkey'),
        Index('idx_part_instance_line_item', 'line_item_id'),
        Index('idx_part_instance_part', 'part_id'),
        Index('idx_part_instance_po_line_item', 'po_line_item_id')
    )

    part_instance_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    part_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'ordered'::character varying"))
    po_line_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    line_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    serial_or_lot_number: Mapped[Optional[str]] = mapped_column(String(100))
    received_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    inspected_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(500))
    installed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))

    line_item: Mapped[Optional['LineItem']] = relationship('LineItem', back_populates='part_instances')
    part: Mapped['Part'] = relationship('Part', back_populates='part_instances')
    po_line_item: Mapped[Optional['PoLineItem']] = relationship('PoLineItem', back_populates='part_instances')
    credit_memos: Mapped[list['CreditMemo']] = relationship('CreditMemo', back_populates='part_instance')


class Core(Base):
    __tablename__ = 'core'
    __table_args__ = (
        CheckConstraint('charge_amount >= 0::numeric', name='core_charge_amount_check'),
        CheckConstraint("return_status::text = ANY (ARRAY['charged'::character varying, 'shipped'::character varying, 'credited'::character varying]::text[])", name='core_return_status_check'),
        ForeignKeyConstraint(['part_id'], ['part.part_id'], ondelete='RESTRICT', name='core_part_id_fkey'),
        PrimaryKeyConstraint('core_id', name='core_pkey'),
        Index('idx_core_part', 'part_id')
    )

    core_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    part_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    charge_amount: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    return_status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'charged'::character varying"))
    shipped_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))

    part: Mapped['Part'] = relationship('Part', back_populates='cores')
    credit_memos: Mapped[list['CreditMemo']] = relationship('CreditMemo', back_populates='core')


class CreditMemo(Base):
    __tablename__ = 'credit_memo'
    __table_args__ = (
        CheckConstraint('amount >= 0::numeric', name='credit_memo_amount_check'),
        CheckConstraint('core_id IS NOT NULL AND part_instance_id IS NULL OR core_id IS NULL AND part_instance_id IS NOT NULL', name='chk_credit_memo_exactly_one_source'),
        CheckConstraint("status::text = ANY (ARRAY['pending'::character varying, 'issued'::character varying]::text[])", name='credit_memo_status_check'),
        ForeignKeyConstraint(['core_id'], ['core.core_id'], ondelete='RESTRICT', name='credit_memo_core_id_fkey'),
        ForeignKeyConstraint(['part_instance_id'], ['part_instance.part_instance_id'], ondelete='RESTRICT', name='credit_memo_part_instance_id_fkey'),
        ForeignKeyConstraint(['vendor_id'], ['vendor.vendor_id'], ondelete='RESTRICT', name='credit_memo_vendor_id_fkey'),
        PrimaryKeyConstraint('credit_memo_id', name='credit_memo_pkey'),
        Index('idx_credit_memo_core', 'core_id'),
        Index('idx_credit_memo_part_instance', 'part_instance_id'),
        Index('idx_credit_memo_vendor', 'vendor_id')
    )

    credit_memo_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    vendor_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    amount: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'::character varying"))
    core_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    part_instance_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    issued_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))

    core: Mapped[Optional['Core']] = relationship('Core', back_populates='credit_memos')
    part_instance: Mapped[Optional['PartInstance']] = relationship('PartInstance', back_populates='credit_memos')
    vendor: Mapped['Vendor'] = relationship('Vendor', back_populates='credit_memos')

    @validates('amount')
    def validate_amount(self, key, value):
        decimal_val = decimal.Decimal(str(value))
        if decimal_val < 0:
            raise ValueError("amount cannot be negative.")
        return decimal_val

    @validates('status')
    def validate_status(self, key, value):
        if value not in ('pending', 'issued'):
            raise ValueError(f"Invalid status: '{value}'. Must be 'pending' or 'issued'.")
        return value

    @validates('core_id', 'part_instance_id')
    def validate_sources(self, key, value):
        other_key = 'part_instance_id' if key == 'core_id' else 'core_id'
        other_value = getattr(self, other_key)
        if value is not None and other_value is not None:
            raise ValueError("CreditMemo must have exactly one source: either core_id or part_instance_id, not both.")
        return value


# ================================================================
# SECTION 6: Billing & Financials
# ================================================================

class Invoice(Base):
    __tablename__ = 'invoice'
    __table_args__ = (
        CheckConstraint('amount_due >= 0::numeric', name='invoice_amount_due_check'),
        CheckConstraint("status::text = ANY (ARRAY['issued'::character varying, 'disputed'::character varying, 'paid'::character varying, 'voided'::character varying, 'credited'::character varying]::text[])", name='invoice_status_check'),
        ForeignKeyConstraint(['customer_id'], ['customer.customer_id'], ondelete='RESTRICT', name='invoice_customer_id_fkey'),
        ForeignKeyConstraint(['warranty_id'], ['warranty.warranty_id'], ondelete='SET NULL', name='invoice_warranty_id_fkey'),
        ForeignKeyConstraint(['work_order_id'], ['work_order.work_order_id'], ondelete='RESTRICT', name='invoice_work_order_id_fkey'),
        PrimaryKeyConstraint('invoice_id', name='invoice_pkey'),
        UniqueConstraint('work_order_id', name='invoice_work_order_id_key'),
        Index('idx_invoice_customer', 'customer_id'),
        Index('idx_invoice_warranty', 'warranty_id')
    )

    invoice_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    work_order_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'issued'::character varying"))
    amount_due: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    issued_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    warranty_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    credit_amount: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(10, 2))
    credit_reason: Mapped[Optional[str]] = mapped_column(String(500))

    customer: Mapped['Customer'] = relationship('Customer', back_populates='invoices')
    warranty: Mapped[Optional['Warranty']] = relationship('Warranty', back_populates='invoices')
    work_order: Mapped['WorkOrder'] = relationship('WorkOrder', back_populates='invoice')
    deposits: Mapped[list['Deposit']] = relationship('Deposit', back_populates='invoice')
    disputes: Mapped[list['Dispute']] = relationship('Dispute', back_populates='invoice')
    payments: Mapped[list['Payment']] = relationship('Payment', back_populates='invoice')

    @hybrid_property
    def total_balance(self) -> decimal.Decimal:
        credit = self.credit_amount if self.credit_amount is not None else decimal.Decimal('0.00')
        return self.amount_due - credit

    @total_balance.expression
    def total_balance(cls):
        return cls.amount_due - func.coalesce(cls.credit_amount, decimal.Decimal('0.00'))


class Dispute(Base):
    __tablename__ = 'dispute'
    __table_args__ = (
        CheckConstraint("opened_by::text = ANY (ARRAY['customer'::character varying, 'shop'::character varying]::text[])", name='dispute_opened_by_check'),
        CheckConstraint("status::text = ANY (ARRAY['open'::character varying, 'under_review'::character varying, 'resolved'::character varying]::text[])", name='dispute_status_check'),
        ForeignKeyConstraint(['invoice_id'], ['invoice.invoice_id'], ondelete='RESTRICT', name='dispute_invoice_id_fkey'),
        PrimaryKeyConstraint('dispute_id', name='dispute_pkey'),
        Index('idx_dispute_invoice', 'invoice_id')
    )

    dispute_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    invoice_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    opened_by: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'open'::character varying"))
    opened_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    resolved_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    resolution: Mapped[Optional[str]] = mapped_column(String(1000))

    invoice: Mapped['Invoice'] = relationship('Invoice', back_populates='disputes')


class Payment(Base):
    __tablename__ = 'payment'
    __table_args__ = (
        CheckConstraint('amount > 0::numeric', name='payment_amount_check'),
        ForeignKeyConstraint(['invoice_id'], ['invoice.invoice_id'], ondelete='RESTRICT', name='payment_invoice_id_fkey'),
        ForeignKeyConstraint(['payer_id'], ['payer.payer_id'], ondelete='SET NULL', name='payment_payer_id_fkey'),
        PrimaryKeyConstraint('payment_id', name='payment_pkey'),
        Index('idx_payment_invoice', 'invoice_id'),
        Index('idx_payment_payer', 'payer_id')
    )

    payment_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    invoice_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    amount: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    method: Mapped[str] = mapped_column(String(50), nullable=False)
    collected_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    payer_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)

    invoice: Mapped['Invoice'] = relationship('Invoice', back_populates='payments')
    payer: Mapped[Optional['Payer']] = relationship('Payer', back_populates='payments')

    @validates('amount')
    def validate_amount(self, key, value):
        decimal_val = decimal.Decimal(str(value))
        if decimal_val <= 0:
            raise ValueError("amount must be greater than zero.")
        return decimal_val


class Deposit(Base):
    __tablename__ = 'deposit'
    __table_args__ = (
        CheckConstraint('amount > 0::numeric', name='deposit_amount_check'),
        CheckConstraint("status::text = ANY (ARRAY['collected'::character varying, 'applied'::character varying, 'refunded'::character varying]::text[])", name='deposit_status_check'),
        ForeignKeyConstraint(['customer_id'], ['customer.customer_id'], ondelete='RESTRICT', name='deposit_customer_id_fkey'),
        ForeignKeyConstraint(['invoice_id'], ['invoice.invoice_id'], ondelete='SET NULL', name='deposit_invoice_id_fkey'),
        ForeignKeyConstraint(['quote_id'], ['quote.quote_id'], ondelete='RESTRICT', name='deposit_quote_id_fkey'),
        ForeignKeyConstraint(['work_order_id'], ['work_order.work_order_id'], ondelete='SET NULL', name='deposit_work_order_id_fkey'),
        PrimaryKeyConstraint('deposit_id', name='deposit_pkey'),
        Index('idx_deposit_customer', 'customer_id'),
        Index('idx_deposit_invoice', 'invoice_id'),
        Index('idx_deposit_quote', 'quote_id'),
        Index('idx_deposit_work_order', 'work_order_id')
    )

    deposit_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    quote_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    amount: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'collected'::character varying"))
    collected_at: Mapped[datetime.datetime] = mapped_column(DateTime(True), nullable=False, server_default=text('now()'))
    work_order_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    refunded_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(True))
    refund_amount: Mapped[Optional[decimal.Decimal]] = mapped_column(Numeric(10, 2))

    customer: Mapped['Customer'] = relationship('Customer', back_populates='deposits')
    invoice: Mapped[Optional['Invoice']] = relationship('Invoice', back_populates='deposits')
    quote: Mapped['Quote'] = relationship('Quote', back_populates='deposits')
    work_order: Mapped[Optional['WorkOrder']] = relationship('WorkOrder', back_populates='deposits')

    @validates('amount')
    def validate_amount(self, key, value):
        decimal_val = decimal.Decimal(str(value))
        if decimal_val <= 0:
            raise ValueError("amount must be greater than zero.")
        return decimal_val

    @validates('status')
    def validate_status(self, key, value):
        if value not in ('collected', 'applied', 'refunded'):
            raise ValueError(f"Invalid status: '{value}'. Must be 'collected', 'applied', or 'refunded'.")
        return value


class StorageCharge(Base):
    __tablename__ = 'storage_charge'
    __table_args__ = (
        CheckConstraint('daily_rate >= 0::numeric', name='storage_charge_daily_rate_check'),
        CheckConstraint('days_accrued >= 0', name='storage_charge_days_accrued_check'),
        ForeignKeyConstraint(['visit_id'], ['visit.visit_id'], ondelete='RESTRICT', name='storage_charge_visit_id_fkey'),
        PrimaryKeyConstraint('storage_charge_id', name='storage_charge_pkey'),
        Index('idx_storage_charge_visit', 'visit_id')
    )

    storage_charge_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    visit_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    daily_rate: Mapped[decimal.Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    start_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    days_accrued: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))

    visit: Mapped['Visit'] = relationship('Visit', back_populates='storage_charges')

    @validates('daily_rate')
    def validate_daily_rate(self, key, value):
        decimal_val = decimal.Decimal(str(value))
        if decimal_val < 0:
            raise ValueError("daily_rate cannot be negative.")
        return decimal_val

    @validates('days_accrued')
    def validate_days_accrued(self, key, value):
        if value < 0:
            raise ValueError("days_accrued cannot be negative.")
        return value

    @hybrid_property
    def total_charge(self) -> decimal.Decimal:
        return self.daily_rate * self.days_accrued

    @total_charge.expression
    def total_charge(cls):
        return cls.daily_rate * cls.days_accrued


# ================================================================
# SECTION 7: Warranties
# ================================================================

class Warranty(Base):
    __tablename__ = 'warranty'
    __table_args__ = (
        ForeignKeyConstraint(['work_order_id'], ['work_order.work_order_id'], ondelete='RESTRICT', name='warranty_work_order_id_fkey'),
        PrimaryKeyConstraint('warranty_id', name='warranty_pkey'),
        UniqueConstraint('work_order_id', name='warranty_work_order_id_key')
    )

    warranty_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    work_order_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    covers_labor: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    covers_parts: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    coverage_type: Mapped[Optional[str]] = mapped_column(String(100))
    term: Mapped[Optional[str]] = mapped_column(String(100))
    start_date: Mapped[Optional[datetime.date]] = mapped_column(Date)

    work_order: Mapped['WorkOrder'] = relationship('WorkOrder', back_populates='warranty')
    invoices: Mapped[list['Invoice']] = relationship('Invoice', back_populates='warranty')
    warranty_claims: Mapped[list['WarrantyClaim']] = relationship('WarrantyClaim', back_populates='warranty')


class WarrantyClaim(Base):
    __tablename__ = 'warranty_claim'
    __table_args__ = (
        CheckConstraint("status::text = ANY (ARRAY['filed'::character varying, 'approved'::character varying, 'denied'::character varying, 'resolved'::character varying]::text[])", name='warranty_claim_status_check'),
        ForeignKeyConstraint(['warranty_id'], ['warranty.warranty_id'], ondelete='RESTRICT', name='warranty_claim_warranty_id_fkey'),
        PrimaryKeyConstraint('claim_id', name='warranty_claim_pkey'),
        Index('idx_warranty_claim_warranty', 'warranty_id')
    )

    claim_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    warranty_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    claim_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'filed'::character varying"))
    resolution: Mapped[Optional[str]] = mapped_column(String(1000))

    warranty: Mapped['Warranty'] = relationship('Warranty', back_populates='warranty_claims')


# ================================================================
# SECTION 8: Event Listeners (Triggers & Side-Effects)
# ================================================================

@event.listens_for(Deposit.work_order, 'set')
def receive_set_work_order(target, value, oldvalue, initiator):
    if value is not None:
        value.status = 'scheduled'

@event.listens_for(Deposit.work_order_id, 'set')
def receive_set_work_order_id(target, value, oldvalue, initiator):
    if value is not None:
        from sqlalchemy import inspect
        insp = inspect(target)
        session = insp.session
        if session:
            from app.models.models import WorkOrder
            parent = session.identity_map.get((WorkOrder, (value,)))
            if parent:
                parent.status = 'scheduled'

@event.listens_for(WorkOrder.status, 'set')
def receive_work_order_status_set(target, value, oldvalue, initiator):
    if value == 'closed' and oldvalue != 'closed':
        target.closed_at = datetime.datetime.now(datetime.timezone.utc)

@event.listens_for(Visit.checked_out_at, 'set')
def receive_visit_checked_out_at_set(target, value, oldvalue, initiator):
    if value is not None:
        target.status = 'completed'

@event.listens_for(Appointment.status, 'set')
def receive_appointment_status_set(target, value, oldvalue, initiator):
    if value == 'confirmed' and target.bay:
        target.bay.status = 'confirmed'


class User(Base):
    __tablename__ = 'user_account'
    __table_args__ = (
        PrimaryKeyConstraint('user_id', name='user_account_pkey'),
        UniqueConstraint('username', name='user_account_username_key'),
        UniqueConstraint('email', name='user_account_email_key'),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, server_default=text('gen_random_uuid()'))
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, server_default=text("'customer'"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey('customer.customer_id', ondelete='SET NULL'), nullable=True)
    tech_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, ForeignKey('technician.tech_id', ondelete='SET NULL'), nullable=True)

    customer: Mapped[Optional['Customer']] = relationship('Customer')
    technician: Mapped[Optional['Technician']] = relationship('Technician')

    @validates('role')
    def validate_role(self, key, value):
        valid_roles = ('manager', 'advisor', 'technician', 'customer')
        if value not in valid_roles:
            raise ValueError(f"Invalid role: '{value}'. Must be one of {valid_roles}.")
        return value
