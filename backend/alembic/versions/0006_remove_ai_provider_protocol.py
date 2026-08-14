"""remove AI provider protocol selection

Revision ID: 0006_remove_ai_protocol
Revises: 0005_ai_protocol
Create Date: 2026-08-14
"""

import sqlalchemy as sa
from alembic import op


revision = "0006_remove_ai_protocol"
down_revision = "0005_ai_protocol"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("ai_provider_configs", "protocol")


def downgrade() -> None:
    op.add_column("ai_provider_configs", sa.Column("protocol", sa.String(length=50), nullable=False, server_default="auto"))
