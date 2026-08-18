"""Add stripe and communication fields

Revision ID: e7b99c07cf0b
Revises: 13a8e2972faa
Create Date: 2026-08-17 18:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7b99c07cf0b'
down_revision: Union[str, Sequence[str], None] = '13a8e2972faa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('customer', sa.Column('email', sa.String(length=255), nullable=True))
    op.add_column('customer', sa.Column('phone', sa.String(length=50), nullable=True))
    op.add_column('customer', sa.Column('stripe_customer_id', sa.String(length=255), nullable=True))

    op.add_column('invoice', sa.Column('stripe_payment_intent_id', sa.String(length=255), nullable=True))
    op.add_column('invoice', sa.Column('stripe_client_secret', sa.String(length=255), nullable=True))

    op.add_column('payment', sa.Column('stripe_charge_id', sa.String(length=255), nullable=True))

    op.create_table('communication_log',
        sa.Column('log_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('customer_id', sa.Uuid(), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('body', sa.String(length=1000), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('status', sa.String(length=50), server_default=sa.text("'sent'::character varying"), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customer.customer_id'], name='comm_log_customer_id_fkey', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('log_id', name='communication_log_pkey')
    )
    op.create_index('idx_comm_log_customer', 'communication_log', ['customer_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_comm_log_customer', table_name='communication_log')
    op.drop_table('communication_log')

    op.drop_column('payment', 'stripe_charge_id')

    op.drop_column('invoice', 'stripe_client_secret')
    op.drop_column('invoice', 'stripe_payment_intent_id')

    op.drop_column('customer', 'stripe_customer_id')
    op.drop_column('customer', 'phone')
    op.drop_column('customer', 'email')
