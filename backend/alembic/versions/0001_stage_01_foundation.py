"""stage 01 foundation schema

Revision ID: 0001_stage_01
Revises:
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_stage_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    task_status = sa.Enum("PENDING", "EXPANDING_QUERY", "COLLECTING", "RANKING", "ANALYZING", "GENERATING_REPORT", "COMPLETED", "PARTIAL", "FAILED", name="researchtaskstatus")
    op.create_table(
        "research_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("platform", sa.String(length=100), nullable=False),
        sa.Column("topic", sa.String(length=500), nullable=False),
        sa.Column("keywords", sa.JSON(), nullable=False),
        sa.Column("expanded_keywords", sa.JSON(), nullable=True),
        sa.Column("time_range", sa.String(length=100), nullable=False),
        sa.Column("max_items", sa.Integer(), nullable=False),
        sa.Column("research_goals", sa.Text(), nullable=True),
        sa.Column("status", task_status, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_research_tasks_platform", "research_tasks", ["platform"])
    op.create_table(
        "content_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("research_task_id", sa.Integer(), sa.ForeignKey("research_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(length=100), nullable=False), sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False), sa.Column("title", sa.String(length=1000)), sa.Column("text", sa.Text()),
        sa.Column("author_name", sa.String(length=255)), sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("like_count", sa.Integer()), sa.Column("favorite_count", sa.Integer()), sa.Column("comment_count", sa.Integer()),
        sa.Column("share_count", sa.Integer()), sa.Column("view_count", sa.Integer()), sa.Column("media_type", sa.String(length=50)),
        sa.Column("image_urls", sa.JSON(), nullable=False), sa.Column("local_image_paths", sa.JSON(), nullable=False), sa.Column("video_urls", sa.JSON(), nullable=False),
        sa.Column("query_keyword", sa.String(length=255)), sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("raw_data", sa.JSON()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("research_task_id", "platform", "external_id", name="uq_task_platform_external"),
    )
    for name, columns in [("ix_content_items_research_task_id", ["research_task_id"]), ("ix_content_items_platform", ["platform"]), ("ix_content_items_published_at", ["published_at"]), ("ix_content_items_collected_at", ["collected_at"]), ("ix_content_items_task_published", ["research_task_id", "published_at"]), ("ix_content_items_task_collected", ["research_task_id", "collected_at"])]:
        op.create_index(name, "content_items", columns)
    op.create_table("content_metric_snapshots", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("content_item_id", sa.Integer(), sa.ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False), sa.Column("like_count", sa.Integer()), sa.Column("favorite_count", sa.Integer()), sa.Column("comment_count", sa.Integer()), sa.Column("share_count", sa.Integer()), sa.Column("view_count", sa.Integer()), sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False))
    op.create_index("ix_content_metric_snapshots_content_item_id", "content_metric_snapshots", ["content_item_id"])
    op.create_table("app_settings", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("key", sa.String(length=100), nullable=False, unique=True), sa.Column("value", sa.JSON(), nullable=False), sa.Column("description", sa.Text()), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False))
    op.create_index("ix_app_settings_key", "app_settings", ["key"])
    op.create_table("platform_configs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(length=100), nullable=False, unique=True), sa.Column("search_url_template", sa.String(length=2048)), sa.Column("selectors", sa.JSON(), nullable=False), sa.Column("parser_rules", sa.JSON(), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False))
    op.create_table("ai_provider_configs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(length=100), nullable=False), sa.Column("provider_type", sa.String(length=30), nullable=False), sa.Column("base_url", sa.String(length=2048)), sa.Column("model_name", sa.String(length=255)), sa.Column("api_key", sa.Text()), sa.Column("timeout_seconds", sa.Integer(), nullable=False), sa.Column("max_retries", sa.Integer(), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False), sa.UniqueConstraint("provider_type", "name", name="uq_provider_type_name"))
    op.create_table("prompt_templates", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(length=100), nullable=False, unique=True), sa.Column("purpose", sa.String(length=100), nullable=False), sa.Column("template", sa.Text(), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False))
    op.create_table("ranking_configs", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(length=100), nullable=False, unique=True), sa.Column("enabled", sa.Boolean(), nullable=False), sa.Column("like_weight", sa.Float(), nullable=False), sa.Column("favorite_weight", sa.Float(), nullable=False), sa.Column("comment_weight", sa.Float(), nullable=False), sa.Column("share_weight", sa.Float(), nullable=False), sa.Column("view_weight", sa.Float(), nullable=False), sa.Column("freshness_half_life_hours", sa.Integer(), nullable=False), sa.Column("growth_window_hours", sa.Integer(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False))


def downgrade() -> None:
    for table in ["ranking_configs", "prompt_templates", "ai_provider_configs", "platform_configs", "app_settings", "content_metric_snapshots", "content_items", "research_tasks"]:
        op.drop_table(table)
