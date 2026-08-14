"""add task-level model analysis records

Revision ID: 0008_task_level_analysis
Revises: 0007_model_gateway
Create Date: 2026-08-14
"""

import sqlalchemy as sa
from alembic import op


revision = "0008_task_level_analysis"
down_revision = "0007_model_gateway"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_analysis_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("research_task_id", sa.Integer(), sa.ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("analysis_error", sa.Text(), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_task_analysis_records_research_task_id", "task_analysis_records", ["research_task_id"])


def downgrade() -> None:
    op.drop_index("ix_task_analysis_records_research_task_id", table_name="task_analysis_records")
    op.drop_table("task_analysis_records")
