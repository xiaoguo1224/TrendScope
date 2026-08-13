"""repair unique ORM indexes

Revision ID: 0004_unique_indexes
Revises: 0003_stage_04
Create Date: 2026-08-13
"""

from alembic import op


revision = "0004_unique_indexes"
down_revision = "0003_stage_04"
branch_labels = None
depends_on = None


_UNIQUE_INDEXES = (
    ("ix_app_settings_key", "app_settings", ["key"]),
    ("ix_content_analysis_records_content_item_id", "content_analysis_records", ["content_item_id"]),
    ("ix_trend_analysis_records_research_task_id", "trend_analysis_records", ["research_task_id"]),
    ("ix_image_prompt_records_creative_concept_id", "image_prompt_records", ["creative_concept_id"]),
    ("ix_report_records_research_task_id", "report_records", ["research_task_id"]),
)


def upgrade() -> None:
    for name, table, columns in _UNIQUE_INDEXES:
        op.drop_index(name, table_name=table)
        op.create_index(name, table, columns, unique=True)


def downgrade() -> None:
    for name, table, columns in reversed(_UNIQUE_INDEXES):
        op.drop_index(name, table_name=table)
        op.create_index(name, table, columns)
