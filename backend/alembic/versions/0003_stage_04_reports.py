"""stage 04 concepts prompts and reports

Revision ID: 0003_stage_04
Revises: 0002_stage_03
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_stage_04"
down_revision = "0002_stage_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "creative_concept_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("research_task_id", sa.Integer(), sa.ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("concept", sa.Text(), nullable=False),
        sa.Column("target_audience", sa.JSON(), nullable=False),
        sa.Column("scenario", sa.JSON(), nullable=False),
        sa.Column("style", sa.String(length=500), nullable=False),
        sa.Column("main_elements", sa.JSON(), nullable=False),
        sa.Column("trend_basis", sa.JSON(), nullable=False),
        sa.Column("differentiation", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_creative_concept_records_research_task_id", "creative_concept_records", ["research_task_id"])
    op.create_table(
        "image_prompt_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("creative_concept_id", sa.Integer(), sa.ForeignKey("creative_concept_records.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("output_language", sa.String(length=50), nullable=False),
        sa.Column("output_style", sa.String(length=500), nullable=False),
        sa.Column("hero_prompt", sa.Text(), nullable=False),
        sa.Column("detail_prompt", sa.Text(), nullable=False),
        sa.Column("lifestyle_prompt", sa.Text(), nullable=False),
        sa.Column("cover_prompt", sa.Text(), nullable=False),
        sa.Column("negative_prompt", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_image_prompt_records_creative_concept_id", "image_prompt_records", ["creative_concept_id"])
    op.create_table(
        "report_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("research_task_id", sa.Integer(), sa.ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("report_path", sa.String(length=2048), nullable=False),
        sa.Column("prompts_path", sa.String(length=2048), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_report_records_research_task_id", "report_records", ["research_task_id"])


def downgrade() -> None:
    op.drop_table("report_records")
    op.drop_table("image_prompt_records")
    op.drop_table("creative_concept_records")
