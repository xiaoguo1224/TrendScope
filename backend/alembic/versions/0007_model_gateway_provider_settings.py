"""add model gateway provider settings

Revision ID: 0007_model_gateway
Revises: 0006_remove_ai_protocol
Create Date: 2026-08-14
"""

import sqlalchemy as sa
from alembic import op


revision = "0007_model_gateway"
down_revision = "0006_remove_ai_protocol"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_provider_configs",
        sa.Column("protocol", sa.String(length=50), nullable=False, server_default="auto"),
    )
    op.add_column(
        "ai_provider_configs",
        sa.Column("capabilities", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "ai_provider_configs",
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
    )


def downgrade() -> None:
    op.drop_column("ai_provider_configs", "priority")
    op.drop_column("ai_provider_configs", "capabilities")
    op.drop_column("ai_provider_configs", "protocol")
