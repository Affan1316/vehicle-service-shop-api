"""Initial migration

Revision ID: f4feb787bc44
Revises: 
Create Date: 2026-06-28 16:09:25.107592

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4feb787bc44'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    
    # 1. Independent Tables
    op.create_table('customer',
    sa.Column('customer_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('customer_type', sa.String(length=20), nullable=False),
    sa.Column('tax_exempt', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('billing_address', sa.String(length=500), nullable=True),
    sa.CheckConstraint("customer_type::text = ANY (ARRAY['individual'::character varying, 'fleet'::character varying]::text[])", name='customer_customer_type_check'),
    sa.PrimaryKeyConstraint('customer_id', name='customer_pkey')
    )
    
    op.create_table('part',
    sa.Column('part_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('part_number', sa.String(length=100), nullable=False),
    sa.Column('quantity_on_hand', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('is_returnable', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('category', sa.String(length=100), nullable=True),
    sa.CheckConstraint('quantity_on_hand >= 0', name='part_quantity_on_hand_check'),
    sa.PrimaryKeyConstraint('part_id', name='part_pkey'),
    sa.UniqueConstraint('part_number', name='part_part_number_key')
    )
    
    op.create_table('payer',
    sa.Column('payer_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('payer_type', sa.String(length=30), nullable=False),
    sa.Column('contact_info', sa.String(length=500), nullable=True),
    sa.Column('billing_terms', sa.String(length=255), nullable=True),
    sa.Column('account_number', sa.String(length=100), nullable=True),
    sa.CheckConstraint("payer_type::text = ANY (ARRAY['insurer'::character varying, 'warranty_company'::character varying, 'fleet_account'::character varying]::text[])", name='payer_payer_type_check'),
    sa.PrimaryKeyConstraint('payer_id', name='payer_pkey')
    )
    
    op.create_table('technician',
    sa.Column('tech_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('hourly_rate', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.CheckConstraint('hourly_rate >= 0::numeric', name='technician_hourly_rate_check'),
    sa.PrimaryKeyConstraint('tech_id', name='technician_pkey')
    )
    
    op.create_table('vendor',
    sa.Column('vendor_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('vendor_type', sa.String(length=100), nullable=True),
    sa.PrimaryKeyConstraint('vendor_id', name='vendor_pkey')
    )
    
    op.create_table('bay',
    sa.Column('bay_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'available'::character varying"), nullable=False),
    sa.Column('bay_type', sa.String(length=100), nullable=True),
    sa.Column('current_work_order_id', sa.Uuid(), nullable=True),
    sa.Column('held_until', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status::text = ANY (ARRAY['available'::character varying, 'held'::character varying, 'confirmed'::character varying, 'occupied'::character varying, 'cleaning'::character varying, 'maintenance'::character varying]::text[])", name='bay_status_check'),
    sa.PrimaryKeyConstraint('bay_id', name='bay_pkey')
    )
    op.create_index('idx_bay_current_work_order', 'bay', ['current_work_order_id'], unique=False)

    # 2. First-Level Dependent Tables
    op.create_table('vehicle',
    sa.Column('vin', sa.String(length=17), nullable=False),
    sa.Column('customer_id', sa.Uuid(), nullable=False),
    sa.Column('make', sa.String(length=100), nullable=False),
    sa.Column('model', sa.String(length=100), nullable=False),
    sa.Column('year', sa.Integer(), nullable=False),
    sa.Column('current_mileage', sa.Integer(), nullable=True),
    sa.CheckConstraint('current_mileage >= 0', name='vehicle_current_mileage_check'),
    sa.CheckConstraint('year >= 1900 AND year <= 2100', name='vehicle_year_check'),
    sa.ForeignKeyConstraint(['customer_id'], ['customer.customer_id'], name='vehicle_customer_id_fkey', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('vin', name='vehicle_pkey')
    )
    op.create_index('idx_vehicle_customer', 'vehicle', ['customer_id'], unique=False)

    op.create_table('certification',
    sa.Column('cert_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('tech_id', sa.Uuid(), nullable=False),
    sa.Column('cert_type', sa.String(length=100), nullable=False),
    sa.Column('expiry_date', sa.Date(), nullable=False),
    sa.ForeignKeyConstraint(['tech_id'], ['technician.tech_id'], name='certification_tech_id_fkey', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('cert_id', name='certification_pkey')
    )
    op.create_index('idx_certification_tech', 'certification', ['tech_id'], unique=False)

    op.create_table('core',
    sa.Column('core_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('part_id', sa.Uuid(), nullable=False),
    sa.Column('charge_amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('return_status', sa.String(length=20), server_default=sa.text("'charged'::character varying"), nullable=False),
    sa.Column('shipped_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("return_status::text = ANY (ARRAY['charged'::character varying, 'shipped'::character varying, 'credited'::character varying]::text[])", name='core_return_status_check'),
    sa.CheckConstraint('charge_amount >= 0::numeric', name='core_charge_amount_check'),
    sa.ForeignKeyConstraint(['part_id'], ['part.part_id'], name='core_part_id_fkey', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('core_id', name='core_pkey')
    )
    op.create_index('idx_core_part', 'core', ['part_id'], unique=False)

    op.create_table('purchase_order',
    sa.Column('po_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('vendor_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'submitted'::character varying"), nullable=False),
    sa.Column('submitted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('expected_delivery', sa.Date(), nullable=True),
    sa.Column('cancellation_reason', sa.String(length=500), nullable=True),
    sa.CheckConstraint("status::text = ANY (ARRAY['submitted'::character varying, 'confirmed'::character varying, 'partially_shipped'::character varying, 'complete'::character varying, 'cancelled'::character varying]::text[])", name='purchase_order_status_check'),
    sa.ForeignKeyConstraint(['vendor_id'], ['vendor.vendor_id'], name='purchase_order_vendor_id_fkey', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('po_id', name='purchase_order_pkey')
    )
    op.create_index('idx_purchase_order_vendor', 'purchase_order', ['vendor_id'], unique=False)

    # 3. Second-Level Dependent Tables
    op.create_table('appointment',
    sa.Column('appointment_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('customer_id', sa.Uuid(), nullable=False),
    sa.Column('vehicle_id', sa.String(length=17), nullable=False),
    sa.Column('requested_date', sa.Date(), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'requested'::character varying"), nullable=False),
    sa.Column('bay_id', sa.Uuid(), nullable=True),
    sa.Column('confirmed_date', sa.Date(), nullable=True),
    sa.CheckConstraint("status::text = ANY (ARRAY['requested'::character varying, 'confirmed'::character varying, 'cancelled'::character varying]::text[])", name='appointment_status_check'),
    sa.ForeignKeyConstraint(['bay_id'], ['bay.bay_id'], name='appointment_bay_id_fkey', ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['customer_id'], ['customer.customer_id'], name='appointment_customer_id_fkey', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['vehicle_id'], ['vehicle.vin'], name='appointment_vehicle_id_fkey', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('appointment_id', name='appointment_pkey')
    )
    op.create_index('idx_appointment_bay', 'appointment', ['bay_id'], unique=False)
    op.create_index('idx_appointment_customer', 'appointment', ['customer_id'], unique=False)
    op.create_index('idx_appointment_vehicle', 'appointment', ['vehicle_id'], unique=False)

    op.create_table('po_line_item',
    sa.Column('po_line_item_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('po_id', sa.Uuid(), nullable=False),
    sa.Column('part_id', sa.Uuid(), nullable=False),
    sa.Column('qty_ordered', sa.Integer(), nullable=False),
    sa.Column('qty_shipped', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('qty_received', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.CheckConstraint('qty_ordered > 0', name='po_line_item_qty_ordered_check'),
    sa.CheckConstraint('qty_received >= 0', name='po_line_item_qty_received_check'),
    sa.CheckConstraint('qty_shipped >= 0', name='po_line_item_qty_shipped_check'),
    sa.ForeignKeyConstraint(['part_id'], ['part.part_id'], name='po_line_item_part_id_fkey', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['po_id'], ['purchase_order.po_id'], name='po_line_item_po_id_fkey', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('po_line_item_id', name='po_line_item_pkey')
    )
    op.create_index('idx_po_line_item_part', 'po_line_item', ['part_id'], unique=False)
    op.create_index('idx_po_line_item_po', 'po_line_item', ['po_id'], unique=False)

    # 4. Third-Level Dependent Tables
    op.create_table('visit',
    sa.Column('visit_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('vehicle_id', sa.String(length=17), nullable=False),
    sa.Column('customer_id', sa.Uuid(), nullable=False),
    sa.Column('checked_in_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'checked_in'::character varying"), nullable=False),
    sa.Column('appointment_id', sa.Uuid(), nullable=True),
    sa.Column('checked_out_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status::text = ANY (ARRAY['checked_in'::character varying, 'in_diagnosis'::character varying, 'awaiting_quote'::character varying, 'in_service'::character varying, 'awaiting_pickup'::character varying, 'completed'::character varying]::text[])", name='visit_status_check'),
    sa.ForeignKeyConstraint(['appointment_id'], ['appointment.appointment_id'], name='visit_appointment_id_fkey', ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['customer_id'], ['customer.customer_id'], name='visit_customer_id_fkey', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['vehicle_id'], ['vehicle.vin'], name='visit_vehicle_id_fkey', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('visit_id', name='visit_pkey')
    )
    op.create_index('idx_visit_appointment', 'visit', ['appointment_id'], unique=False)
    op.create_index('idx_visit_customer', 'visit', ['customer_id'], unique=False)
    op.create_index('idx_visit_vehicle', 'visit', ['vehicle_id'], unique=False)

    # 5. Fourth-Level Dependent Tables
    op.create_table('quote',
    sa.Column('quote_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('vehicle_id', sa.String(length=17), nullable=False),
    sa.Column('customer_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'draft'::character varying"), nullable=False),
    sa.Column('total_amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('drafted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('valid_until', sa.Date(), nullable=False),
    sa.Column('visit_id', sa.Uuid(), nullable=True),
    sa.Column('issued_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('decline_reason', sa.String(length=500), nullable=True),
    sa.CheckConstraint("status::text = ANY (ARRAY['draft'::character varying, 'issued'::character varying, 'approved'::character varying, 'declined'::character varying, 'expired'::character varying]::text[])", name='quote_status_check'),
    sa.CheckConstraint('total_amount >= 0::numeric', name='quote_total_amount_check'),
    sa.ForeignKeyConstraint(['customer_id'], ['customer.customer_id'], name='quote_customer_id_fkey', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['vehicle_id'], ['vehicle.vin'], name='quote_vehicle_id_fkey', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['visit_id'], ['visit.visit_id'], name='quote_visit_id_fkey', ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('quote_id', name='quote_pkey')
    )
    op.create_index('idx_quote_customer', 'quote', ['customer_id'], unique=False)
    op.create_index('idx_quote_vehicle', 'quote', ['vehicle_id'], unique=False)
    op.create_index('idx_quote_visit', 'quote', ['visit_id'], unique=False)

    op.create_table('diagnostic',
    sa.Column('report_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('visit_id', sa.Uuid(), nullable=False),
    sa.Column('vehicle_id', sa.String(length=17), nullable=False),
    sa.Column('tech_id', sa.Uuid(), nullable=False),
    sa.Column('performed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'in_progress'::character varying"), nullable=False),
    sa.CheckConstraint("status::text = ANY (ARRAY['in_progress'::character varying, 'completed'::character varying]::text[])", name='diagnostic_status_check'),
    sa.ForeignKeyConstraint(['tech_id'], ['technician.tech_id'], name='diagnostic_tech_id_fkey', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['vehicle_id'], ['vehicle.vin'], name='diagnostic_vehicle_id_fkey', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['visit_id'], ['visit.visit_id'], name='diagnostic_visit_id_fkey', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('report_id', name='diagnostic_pkey')
    )
    op.create_index('idx_diagnostic_tech', 'diagnostic', ['tech_id'], unique=False)
    op.create_index('idx_diagnostic_vehicle', 'diagnostic', ['vehicle_id'], unique=False)
    op.create_index('idx_diagnostic_visit', 'diagnostic', ['visit_id'], unique=False)

    op.create_table('diagnostic_finding',
    sa.Column('finding_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('report_id', sa.Uuid(), nullable=False),
    sa.Column('description', sa.String(length=1000), nullable=False),
    sa.ForeignKeyConstraint(['report_id'], ['diagnostic.report_id'], name='diagnostic_finding_report_id_fkey', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('finding_id', name='diagnostic_finding_pkey')
    )
    op.create_index('idx_diagnostic_finding_report', 'diagnostic_finding', ['report_id'], unique=False)

    op.create_table('storage_charge',
    sa.Column('storage_charge_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('visit_id', sa.Uuid(), nullable=False),
    sa.Column('daily_rate', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('days_accrued', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.CheckConstraint('daily_rate >= 0::numeric', name='storage_charge_daily_rate_check'),
    sa.CheckConstraint('days_accrued >= 0', name='storage_charge_days_accrued_check'),
    sa.ForeignKeyConstraint(['visit_id'], ['visit.visit_id'], name='storage_charge_visit_id_fkey', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('storage_charge_id', name='storage_charge_pkey')
    )
    op.create_index('idx_storage_charge_visit', 'storage_charge', ['visit_id'], unique=False)

    # 6. Fifth-Level Dependent Tables
    op.create_table('work_order',
    sa.Column('work_order_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('quote_id', sa.Uuid(), nullable=False),
    sa.Column('vehicle_id', sa.String(length=17), nullable=False),
    sa.Column('customer_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'created'::character varying"), nullable=False),
    sa.Column('authorized_amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('visit_id', sa.Uuid(), nullable=True),
    sa.Column('bay_id', sa.Uuid(), nullable=True),
    sa.Column('promised_date', sa.Date(), nullable=True),
    sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('paused_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('pause_reason', sa.String(length=500), nullable=True),
    sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status::text = ANY (ARRAY['created'::character varying, 'scheduled'::character varying, 'paused'::character varying, 'active'::character varying, 'closed'::character varying, 'archived'::character varying]::text[])", name='work_order_status_check'),
    sa.CheckConstraint('authorized_amount >= 0::numeric', name='work_order_authorized_amount_check'),
    sa.ForeignKeyConstraint(['bay_id'], ['bay.bay_id'], name='work_order_bay_id_fkey', ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['customer_id'], ['customer.customer_id'], name='work_order_customer_id_fkey', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['quote_id'], ['quote.quote_id'], name='work_order_quote_id_fkey', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['vehicle_id'], ['vehicle.vin'], name='work_order_vehicle_id_fkey', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['visit_id'], ['visit.visit_id'], name='work_order_visit_id_fkey', ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('work_order_id', name='work_order_pkey'),
    sa.UniqueConstraint('quote_id', name='work_order_quote_id_key')
    )
    op.create_index('idx_work_order_bay', 'work_order', ['bay_id'], unique=False)
    op.create_index('idx_work_order_customer', 'work_order', ['customer_id'], unique=False)
    op.create_index('idx_work_order_vehicle', 'work_order', ['vehicle_id'], unique=False)
    op.create_index('idx_work_order_visit', 'work_order', ['visit_id'], unique=False)

    # 7. Sixth-Level Dependent Tables
    op.create_table('line_item',
    sa.Column('line_item_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('work_order_id', sa.Uuid(), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=False),
    sa.Column('billing_mode', sa.String(length=20), nullable=False),
    sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'not_started'::character varying"), nullable=False),
    sa.Column('hold_reason', sa.String(length=500), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("billing_mode::text = ANY (ARRAY['flat_rate'::character varying, 'hourly'::character varying]::text[])", name='line_item_billing_mode_check'),
    sa.CheckConstraint("status::text = ANY (ARRAY['not_started'::character varying, 'gated'::character varying, 'in_progress'::character varying, 'on_hold'::character varying, 'completed'::character varying]::text[])", name='line_item_status_check'),
    sa.CheckConstraint('price >= 0::numeric', name='line_item_price_check'),
    sa.ForeignKeyConstraint(['work_order_id'], ['work_order.work_order_id'], name='line_item_work_order_id_fkey', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('line_item_id', name='line_item_pkey')
    )
    op.create_index('idx_line_item_work_order', 'line_item', ['work_order_id'], unique=False)

    op.create_table('labor_entry',
    sa.Column('labor_entry_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('tech_id', sa.Uuid(), nullable=False),
    sa.Column('line_item_id', sa.Uuid(), nullable=False),
    sa.Column('work_date', sa.Date(), nullable=False),
    sa.Column('hours', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.CheckConstraint('hours > 0::numeric', name='labor_entry_hours_check'),
    sa.ForeignKeyConstraint(['line_item_id'], ['line_item.line_item_id'], name='labor_entry_line_item_id_fkey', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['tech_id'], ['technician.tech_id'], name='labor_entry_tech_id_fkey', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('labor_entry_id', name='labor_entry_pkey')
    )
    op.create_index('idx_labor_entry_line_item', 'labor_entry', ['line_item_id'], unique=False)
    op.create_index('idx_labor_entry_tech', 'labor_entry', ['tech_id'], unique=False)

    op.create_table('quality_check',
    sa.Column('qc_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('line_item_id', sa.Uuid(), nullable=False),
    sa.Column('tech_id', sa.Uuid(), nullable=False),
    sa.Column('performed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.CheckConstraint("status::text = ANY (ARRAY['passed'::character varying, 'failed'::character varying]::text[])", name='quality_check_status_check'),
    sa.ForeignKeyConstraint(['line_item_id'], ['line_item.line_item_id'], name='quality_check_line_item_id_fkey', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['tech_id'], ['technician.tech_id'], name='quality_check_tech_id_fkey', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('qc_id', name='quality_check_pkey')
    )
    op.create_index('idx_quality_check_line_item', 'quality_check', ['line_item_id'], unique=False)
    op.create_index('idx_quality_check_tech', 'quality_check', ['tech_id'], unique=False)

    op.create_table('warranty',
    sa.Column('warranty_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('work_order_id', sa.Uuid(), nullable=False),
    sa.Column('covers_labor', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('covers_parts', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('coverage_type', sa.String(length=100), nullable=True),
    sa.Column('term', sa.String(length=100), nullable=True),
    sa.Column('start_date', sa.Date(), nullable=True),
    sa.ForeignKeyConstraint(['work_order_id'], ['work_order.work_order_id'], name='warranty_work_order_id_fkey', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('warranty_id', name='warranty_pkey'),
    sa.UniqueConstraint('work_order_id', name='warranty_work_order_id_key')
    )

    op.create_table('warranty_claim',
    sa.Column('claim_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('warranty_id', sa.Uuid(), nullable=False),
    sa.Column('claim_date', sa.Date(), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'filed'::character varying"), nullable=False),
    sa.Column('resolution', sa.String(length=1000), nullable=True),
    sa.CheckConstraint("status::text = ANY (ARRAY['filed'::character varying, 'approved'::character varying, 'denied'::character varying, 'resolved'::character varying]::text[])", name='warranty_claim_status_check'),
    sa.ForeignKeyConstraint(['warranty_id'], ['warranty.warranty_id'], name='warranty_claim_warranty_id_fkey', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('claim_id', name='warranty_claim_pkey')
    )
    op.create_index('idx_warranty_claim_warranty', 'warranty_claim', ['warranty_id'], unique=False)

    op.create_table('invoice',
    sa.Column('invoice_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('work_order_id', sa.Uuid(), nullable=False),
    sa.Column('customer_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'issued'::character varying"), nullable=False),
    sa.Column('amount_due', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('issued_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('warranty_id', sa.Uuid(), nullable=True),
    sa.Column('credit_amount', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('credit_reason', sa.String(length=500), nullable=True),
    sa.CheckConstraint("status::text = ANY (ARRAY['issued'::character varying, 'disputed'::character varying, 'paid'::character varying, 'voided'::character varying, 'credited'::character varying]::text[])", name='invoice_status_check'),
    sa.CheckConstraint('amount_due >= 0::numeric', name='invoice_amount_due_check'),
    sa.ForeignKeyConstraint(['customer_id'], ['customer.customer_id'], name='invoice_customer_id_fkey', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['warranty_id'], ['warranty.warranty_id'], name='invoice_warranty_id_fkey', ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['work_order_id'], ['work_order.work_order_id'], name='invoice_work_order_id_fkey', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('invoice_id', name='invoice_pkey'),
    sa.UniqueConstraint('work_order_id', name='invoice_work_order_id_key')
    )
    op.create_index('idx_invoice_customer', 'invoice', ['customer_id'], unique=False)
    op.create_index('idx_invoice_warranty', 'invoice', ['warranty_id'], unique=False)

    op.create_table('deposit',
    sa.Column('deposit_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('quote_id', sa.Uuid(), nullable=False),
    sa.Column('customer_id', sa.Uuid(), nullable=False),
    sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'collected'::character varying"), nullable=False),
    sa.Column('collected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('work_order_id', sa.Uuid(), nullable=True),
    sa.Column('invoice_id', sa.Uuid(), nullable=True),
    sa.Column('refunded_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('refund_amount', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.CheckConstraint("status::text = ANY (ARRAY['collected'::character varying, 'applied'::character varying, 'refunded'::character varying]::text[])", name='deposit_status_check'),
    sa.CheckConstraint('amount > 0::numeric', name='deposit_amount_check'),
    sa.ForeignKeyConstraint(['customer_id'], ['customer.customer_id'], name='deposit_customer_id_fkey', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['invoice_id'], ['invoice.invoice_id'], name='deposit_invoice_id_fkey', ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['quote_id'], ['quote.quote_id'], name='deposit_quote_id_fkey', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['work_order_id'], ['work_order.work_order_id'], name='deposit_work_order_id_fkey', ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('deposit_id', name='deposit_pkey')
    )
    op.create_index('idx_deposit_customer', 'deposit', ['customer_id'], unique=False)
    op.create_index('idx_deposit_invoice', 'deposit', ['invoice_id'], unique=False)
    op.create_index('idx_deposit_quote', 'deposit', ['quote_id'], unique=False)
    op.create_index('idx_deposit_work_order', 'deposit', ['work_order_id'], unique=False)

    op.create_table('dispute',
    sa.Column('dispute_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('invoice_id', sa.Uuid(), nullable=False),
    sa.Column('opened_by', sa.String(length=20), nullable=False),
    sa.Column('reason', sa.String(length=500), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'open'::character varying"), nullable=False),
    sa.Column('opened_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('resolution', sa.String(length=1000), nullable=True),
    sa.CheckConstraint("opened_by::text = ANY (ARRAY['customer'::character varying, 'shop'::character varying]::text[])", name='dispute_opened_by_check'),
    sa.CheckConstraint("status::text = ANY (ARRAY['open'::character varying, 'under_review'::character varying, 'resolved'::character varying]::text[])", name='dispute_status_check'),
    sa.ForeignKeyConstraint(['invoice_id'], ['invoice.invoice_id'], name='dispute_invoice_id_fkey', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('dispute_id', name='dispute_pkey')
    )
    op.create_index('idx_dispute_invoice', 'dispute', ['invoice_id'], unique=False)

    op.create_table('payment',
    sa.Column('payment_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('invoice_id', sa.Uuid(), nullable=False),
    sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('method', sa.String(length=50), nullable=False),
    sa.Column('collected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('payer_id', sa.Uuid(), nullable=True),
    sa.CheckConstraint('amount > 0::numeric', name='payment_amount_check'),
    sa.ForeignKeyConstraint(['invoice_id'], ['invoice.invoice_id'], name='payment_invoice_id_fkey', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['payer_id'], ['payer.payer_id'], name='payment_payer_id_fkey', ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('payment_id', name='payment_pkey')
    )
    op.create_index('idx_payment_invoice', 'payment', ['invoice_id'], unique=False)
    op.create_index('idx_payment_payer', 'payment', ['payer_id'], unique=False)

    op.create_table('change_order',
    sa.Column('change_order_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('work_order_id', sa.Uuid(), nullable=False),
    sa.Column('line_item_id', sa.Uuid(), nullable=False),
    sa.Column('reason', sa.String(length=500), nullable=False),
    sa.Column('delta_amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('approval_status', sa.String(length=20), server_default=sa.text("'issued'::character varying"), nullable=False),
    sa.Column('finding_id', sa.Uuid(), nullable=True),
    sa.Column('approved_by', sa.String(length=255), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('decline_reason', sa.String(length=500), nullable=True),
    sa.CheckConstraint("approval_status::text = ANY (ARRAY['issued'::character varying, 'approved'::character varying, 'declined'::character varying]::text[])", name='change_order_approval_status_check'),
    sa.ForeignKeyConstraint(['finding_id'], ['diagnostic_finding.finding_id'], name='change_order_finding_id_fkey', ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['line_item_id'], ['line_item.line_item_id'], name='change_order_line_item_id_fkey', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['work_order_id'], ['work_order.work_order_id'], name='change_order_work_order_id_fkey', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('change_order_id', name='change_order_pkey'),
    sa.UniqueConstraint('finding_id', name='change_order_finding_id_key')
    )
    op.create_index('idx_change_order_line_item', 'change_order', ['line_item_id'], unique=False)
    op.create_index('idx_change_order_work_order', 'change_order', ['work_order_id'], unique=False)

    op.create_table('part_instance',
    sa.Column('part_instance_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('part_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'ordered'::character varying"), nullable=False),
    sa.Column('po_line_item_id', sa.Uuid(), nullable=True),
    sa.Column('line_item_id', sa.Uuid(), nullable=True),
    sa.Column('serial_or_lot_number', sa.String(length=100), nullable=True),
    sa.Column('received_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('inspected_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('rejection_reason', sa.String(length=500), nullable=True),
    sa.Column('installed_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status::text = ANY (ARRAY['ordered'::character varying, 'shipped'::character varying, 'received'::character varying, 'inspected'::character varying, 'rejected'::character varying, 'returned'::character varying, 'installed'::character varying]::text[])", name='part_instance_status_check'),
    sa.ForeignKeyConstraint(['line_item_id'], ['line_item.line_item_id'], name='part_instance_line_item_id_fkey', ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['part_id'], ['part.part_id'], name='part_instance_part_id_fkey', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['po_line_item_id'], ['po_line_item.po_line_item_id'], name='part_instance_po_line_item_id_fkey', ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('part_instance_id', name='part_instance_pkey')
    )
    op.create_index('idx_part_instance_line_item', 'part_instance', ['line_item_id'], unique=False)
    op.create_index('idx_part_instance_part', 'part_instance', ['part_id'], unique=False)
    op.create_index('idx_part_instance_po_line_item', 'part_instance', ['po_line_item_id'], unique=False)

    op.create_table('part_instance_credit_memos',
    sa.Column('credit_memo_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.PrimaryKeyConstraint('credit_memo_id')
    )

    op.create_table('credit_memo',
    sa.Column('credit_memo_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('vendor_id', sa.Uuid(), nullable=False),
    sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('status', sa.String(length=20), server_default=sa.text("'pending'::character varying"), nullable=False),
    sa.Column('core_id', sa.Uuid(), nullable=True),
    sa.Column('part_instance_id', sa.Uuid(), nullable=True),
    sa.Column('issued_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status::text = ANY (ARRAY['pending'::character varying, 'issued'::character varying]::text[])", name='credit_memo_status_check'),
    sa.CheckConstraint('amount >= 0::numeric', name='credit_memo_amount_check'),
    sa.CheckConstraint('core_id IS NOT NULL AND part_instance_id IS NULL OR core_id IS NULL AND part_instance_id IS NOT NULL', name='chk_credit_memo_exactly_one_source'),
    sa.ForeignKeyConstraint(['core_id'], ['core.core_id'], name='credit_memo_core_id_fkey', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['part_instance_id'], ['part_instance.part_instance_id'], name='credit_memo_part_instance_id_fkey', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['vendor_id'], ['vendor.vendor_id'], name='credit_memo_vendor_id_fkey', ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('credit_memo_id', name='credit_memo_pkey')
    )
    op.create_index('idx_credit_memo_core', 'credit_memo', ['core_id'], unique=False)
    op.create_index('idx_credit_memo_part_instance', 'credit_memo', ['part_instance_id'], unique=False)
    op.create_index('idx_credit_memo_vendor', 'credit_memo', ['vendor_id'], unique=False)

    # 8. Add Circular Dependency Foreign Keys at the end
    op.create_foreign_key('fk_bay_current_work_order', 'bay', 'work_order', ['current_work_order_id'], ['work_order_id'], ondelete='SET NULL')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_bay_current_work_order', 'bay', type_='foreignkey')
    
    op.drop_table('credit_memo')
    op.drop_table('part_instance_credit_memos')
    op.drop_table('part_instance')
    op.drop_table('change_order')
    op.drop_table('payment')
    op.drop_table('dispute')
    op.drop_table('deposit')
    op.drop_table('invoice')
    op.drop_table('warranty_claim')
    op.drop_table('warranty')
    op.drop_table('quality_check')
    op.drop_table('labor_entry')
    op.drop_table('line_item')
    op.drop_table('work_order')
    op.drop_table('storage_charge')
    op.drop_table('diagnostic_finding')
    op.drop_table('diagnostic')
    op.drop_table('quote')
    op.drop_table('visit')
    op.drop_table('po_line_item')
    op.drop_table('appointment')
    op.drop_table('purchase_order')
    op.drop_table('core')
    op.drop_table('certification')
    op.drop_table('vehicle')
    op.drop_table('bay')
    op.drop_table('vendor')
    op.drop_table('technician')
    op.drop_table('payer')
    op.drop_table('part')
    op.drop_table('customer')
