"""Phase 1: customer contact fields, part pricing, vehicle license plate, and invoice tax fields

Revision ID: 7b2c9d4e5f6a
Revises: 13a8e2972faa
Create Date: 2026-08-14 14:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7b2c9d4e5f6a'
down_revision: Union[str, Sequence[str], None] = 'c285749d2193'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Customer contact fields
    op.add_column('customer', sa.Column('phone', sa.String(length=20), nullable=True))
    op.add_column('customer', sa.Column('email', sa.String(length=255), nullable=True))
    op.add_column('customer', sa.Column('secondary_phone', sa.String(length=20), nullable=True))
    op.add_column('customer', sa.Column('notes', sa.String(length=1000), nullable=True))

    # 2. Part pricing and descriptive fields
    op.add_column('part', sa.Column('name', sa.String(length=255), server_default=sa.text("''::character varying"), nullable=False))
    op.add_column('part', sa.Column('description', sa.String(length=1000), nullable=True))
    op.add_column('part', sa.Column('cost_price', sa.Numeric(precision=10, scale=2), server_default=sa.text("'0.00'::numeric"), nullable=False))
    op.add_column('part', sa.Column('retail_price', sa.Numeric(precision=10, scale=2), server_default=sa.text("'0.00'::numeric"), nullable=False))

    # 3. Vehicle license plate
    op.add_column('vehicle', sa.Column('license_plate', sa.String(length=15), nullable=True))

    # 4. Invoice tax fields
    op.add_column('invoice', sa.Column('tax_rate', sa.Numeric(precision=5, scale=4), nullable=True))
    op.add_column('invoice', sa.Column('tax_amount', sa.Numeric(precision=10, scale=2), nullable=True))


def downgrade() -> None:
    # 4. Invoice
    op.drop_column('invoice', 'tax_amount')
    op.drop_column('invoice', 'tax_rate')

    # 3. Vehicle
    op.drop_column('vehicle', 'license_plate')

    # 2. Part
    op.drop_column('part', 'retail_price')
    op.drop_column('part', 'cost_price')
    op.drop_column('part', 'description')
    op.drop_column('part', 'name')

    # 1. Customer
    op.drop_column('customer', 'notes')
    op.drop_column('customer', 'secondary_phone')
    op.drop_column('customer', 'email')
    op.drop_column('customer', 'phone')
