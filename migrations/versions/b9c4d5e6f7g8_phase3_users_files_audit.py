"""Phase 3: password reset tokens, file attachments, and audit log tables

Revision ID: b9c4d5e6f7g8
Revises: a8b3c4d5e6f7
Create Date: 2026-08-14 17:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9c4d5e6f7g8'
down_revision: Union[str, Sequence[str], None] = 'a8b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Password Reset Token Table
    op.create_table(
        'password_reset_token',
        sa.Column('token_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('token_hash', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user_account.user_id'], ondelete='CASCADE', name='password_reset_token_user_id_fkey'),
        sa.PrimaryKeyConstraint('token_id', name='password_reset_token_pkey')
    )
    op.create_index('idx_password_reset_token_user', 'password_reset_token', ['user_id'])

    # 2. File Attachment Table
    op.create_table(
        'file_attachment',
        sa.Column('file_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.String(length=255), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('stored_filename', sa.String(length=255), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('uploaded_by', sa.Uuid(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(['uploaded_by'], ['user_account.user_id'], ondelete='SET NULL', name='file_attachment_uploaded_by_fkey'),
        sa.PrimaryKeyConstraint('file_id', name='file_attachment_pkey')
    )
    op.create_index('idx_file_attachment_entity', 'file_attachment', ['entity_type', 'entity_id'])
    op.create_index('idx_file_attachment_uploader', 'file_attachment', ['uploaded_by'])

    # 3. Audit Log Table
    op.create_table(
        'audit_log',
        sa.Column('log_id', sa.Uuid(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.String(length=255), nullable=False),
        sa.Column('action', sa.String(length=20), nullable=False),
        sa.Column('actor_id', sa.Uuid(), nullable=True),
        sa.Column('actor_username', sa.String(length=100), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('changes', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['actor_id'], ['user_account.user_id'], ondelete='SET NULL', name='audit_log_actor_id_fkey'),
        sa.PrimaryKeyConstraint('log_id', name='audit_log_pkey')
    )
    op.create_index('idx_audit_log_entity', 'audit_log', ['entity_type', 'entity_id'])
    op.create_index('idx_audit_log_actor', 'audit_log', ['actor_id'])
    op.create_index('idx_audit_log_timestamp', 'audit_log', ['timestamp'])


def downgrade() -> None:
    # 3. Audit Log
    op.drop_index('idx_audit_log_timestamp', table_name='audit_log')
    op.drop_index('idx_audit_log_actor', table_name='audit_log')
    op.drop_index('idx_audit_log_entity', table_name='audit_log')
    op.drop_table('audit_log')

    # 2. File Attachment
    op.drop_index('idx_file_attachment_uploader', table_name='file_attachment')
    op.drop_index('idx_file_attachment_entity', table_name='file_attachment')
    op.drop_table('file_attachment')

    # 1. Password Reset Token
    op.drop_index('idx_password_reset_token_user', table_name='password_reset_token')
    op.drop_table('password_reset_token')
