"""Stripe payment gateway fields

Revision ID: c1d2e3f4a5b6
Revises: b9c4d5e6f7g8
Create Date: 2026-08-14 18:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, Sequence[str], None] = 'b9c4d5e6f7g8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Customer: Add stripe_customer_id
    op.add_column('customer', sa.Column('stripe_customer_id', sa.String(length=255), nullable=True))
    op.create_index('idx_customer_stripe_id', 'customer', ['stripe_customer_id'])

    # 2. Payment: Add Stripe tracking fields
    op.add_column('payment', sa.Column('stripe_payment_intent_id', sa.String(length=255), nullable=True))
    op.add_column('payment', sa.Column('stripe_checkout_session_id', sa.String(length=255), nullable=True))
    op.add_column('payment', sa.Column('stripe_charge_id', sa.String(length=255), nullable=True))
    op.add_column('payment', sa.Column('stripe_refund_id', sa.String(length=255), nullable=True))
    op.create_index('idx_payment_stripe_pi', 'payment', ['stripe_payment_intent_id'])
    op.create_index('idx_payment_stripe_session', 'payment', ['stripe_checkout_session_id'])


def downgrade() -> None:
    op.drop_index('idx_payment_stripe_session', table_name='payment')
    op.drop_index('idx_payment_stripe_pi', table_name='payment')
    op.drop_column('payment', 'stripe_refund_id')
    op.drop_column('payment', 'stripe_charge_id')
    op.drop_column('payment', 'stripe_checkout_session_id')
    op.drop_column('payment', 'stripe_payment_intent_id')

    op.drop_index('idx_customer_stripe_id', table_name='customer')
    op.drop_column('customer', 'stripe_customer_id')
