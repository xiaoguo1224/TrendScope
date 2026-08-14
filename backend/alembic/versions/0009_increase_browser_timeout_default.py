"""increase browser timeout default for dynamic public pages

Revision ID: 0009_browser_timeout_default
Revises: 0008_task_level_analysis
Create Date: 2026-08-14
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_browser_timeout_default"
down_revision = "0008_task_level_analysis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    table = sa.table("app_settings", sa.column("key", sa.String()), sa.column("value", sa.JSON()))
    row = connection.execute(sa.select(table.c.value).where(table.c.key == "browser_defaults")).scalar_one_or_none()
    if isinstance(row, dict) and row.get("timeout_seconds") == 30:
        connection.execute(table.update().where(table.c.key == "browser_defaults").values(value={**row, "timeout_seconds": 120}))


def downgrade() -> None:
    connection = op.get_bind()
    table = sa.table("app_settings", sa.column("key", sa.String()), sa.column("value", sa.JSON()))
    row = connection.execute(sa.select(table.c.value).where(table.c.key == "browser_defaults")).scalar_one_or_none()
    if isinstance(row, dict) and row.get("timeout_seconds") == 120:
        connection.execute(table.update().where(table.c.key == "browser_defaults").values(value={**row, "timeout_seconds": 30}))
