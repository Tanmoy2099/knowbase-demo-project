"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-23

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "content_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("raw_url", sa.Text),
        sa.Column("title", sa.Text),
        sa.Column("body", sa.Text),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_content_items_status", "content_items", ["status"])
    op.create_index("ix_content_items_type", "content_items", ["type"])
    op.create_index("ix_content_items_created_at", "content_items", ["created_at"])

    op.create_table(
        "summaries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("content_item_id", sa.String(36), sa.ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("ai_provider", sa.String(50)),
        sa.Column("model", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_summaries_content_item_id", "summaries", ["content_item_id"])

    op.create_table(
        "tags",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("slug", sa.Text, nullable=False),
        sa.UniqueConstraint("name", name="uq_tags_name"),
        sa.UniqueConstraint("slug", name="uq_tags_slug"),
    )

    op.create_table(
        "collections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("slug", sa.Text, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("ai_suggested", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", name="uq_collections_name"),
        sa.UniqueConstraint("slug", name="uq_collections_slug"),
    )

    op.create_table(
        "content_tags",
        sa.Column("content_item_id", sa.String(36), sa.ForeignKey("content_items.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.String(36), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "collection_items",
        sa.Column("collection_id", sa.String(36), sa.ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("content_item_id", sa.String(36), sa.ForeignKey("content_items.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "topic_relations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_id", sa.String(36), sa.ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relation_type", sa.String(50)),
        sa.Column("strength", sa.Float),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("strength >= 0 AND strength <= 1", name="ck_topic_relations_strength_range"),
        sa.UniqueConstraint("source_id", "target_id", name="uq_topic_relations_pair"),
    )
    op.create_index("ix_topic_relations_source_id", "topic_relations", ["source_id"])
    op.create_index("ix_topic_relations_target_id", "topic_relations", ["target_id"])

    op.create_table(
        "workflow_sync",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workflow_name", sa.Text, nullable=False),
        sa.Column("n8n_workflow_id", sa.Text),
        sa.Column("hash", sa.Text, nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workflow_name", name="uq_workflow_sync_name"),
    )


def downgrade() -> None:
    op.drop_table("workflow_sync")
    op.drop_table("topic_relations")
    op.drop_table("collection_items")
    op.drop_table("content_tags")
    op.drop_table("collections")
    op.drop_table("tags")
    op.drop_table("summaries")
    op.drop_table("content_items")
