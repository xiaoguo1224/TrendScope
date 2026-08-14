"""add AI provider protocol selection

Revision ID: 0005_ai_protocol
Revises: 0004_unique_indexes
Create Date: 2026-08-14
"""

import sqlalchemy as sa
from alembic import op


revision = "0005_ai_protocol"
down_revision = "0004_unique_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_provider_configs", sa.Column("protocol", sa.String(length=50), nullable=False, server_default="auto"))


def downgrade() -> None:
    op.drop_column("ai_provider_configs", "protocol")
