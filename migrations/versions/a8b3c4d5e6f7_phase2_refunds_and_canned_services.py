"""Phase 2: payment refund fields and canned_service table

Revision ID: a8b3c4d5e6f7
Revises: 7b2c9d4e5f6a
Create Date: 2026-08-14 14:48:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8b3c4d5e6f7'
down_revision: Union[str, Sequence[str], None] = '7b2c9d4e5f6a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Payment refund fields
    op.add_column('payment', sa.Column('refunded_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('payment', sa.Column('refund_amount', sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column('payment', sa.Column('refund_reason', sa.String(length=500), nullable=True))

    # 2. Canned service table
    op.create_table(
        'canned_service',
        sa.Column('service_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.String(length=1000), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('billing_mode', sa.String(length=20), server_default=sa.text("'flat_rate'::character varying"), nullable=False),
        sa.Column('default_price', sa.Numeric(precision=10, scale=2), server_default=sa.text("'0.00'::numeric"), nullable=False),
        sa.Column('estimated_hours', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.CheckConstraint(
            "billing_mode::text = ANY (ARRAY['flat_rate'::character varying, 'hourly'::character varying]::text[])",
            name='canned_service_billing_mode_check'
        ),
        sa.PrimaryKeyConstraint('service_id', name='canned_service_pkey')
    )


def downgrade() -> None:
    # 2. Canned service
    op.drop_table('canned_service')

    # 1. Payment
    op.drop_column('payment', 'refund_reason')
    op.drop_column('payment', 'refund_amount')
    op.drop_column('payment', 'refunded_at')
