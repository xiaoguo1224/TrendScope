"""stage 03 analysis persistence

Revision ID: 0002_stage_03
Revises: 0001_stage_01
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_stage_03"
down_revision = "0001_stage_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_analysis_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("content_item_id", sa.Integer(), sa.ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("text_analysis", sa.JSON(), nullable=True),
        sa.Column("visual_analyses", sa.JSON(), nullable=False),
        sa.Column("content_analysis", sa.JSON(), nullable=True),
        sa.Column("analysis_error", sa.Text(), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_content_analysis_records_content_item_id", "content_analysis_records", ["content_item_id"])
    op.create_table(
        "trend_analysis_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("research_task_id", sa.Integer(), sa.ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_trend_analysis_records_research_task_id", "trend_analysis_records", ["research_task_id"])


def downgrade() -> None:
    op.drop_table("trend_analysis_records")
    op.drop_table("content_analysis_records")
