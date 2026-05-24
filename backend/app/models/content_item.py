from app.core.db import db
from .base import TimestampMixin, generate_uuid


class ContentItem(TimestampMixin, db.Model):
    __tablename__ = "content_items"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    type = db.Column(db.String(20), nullable=False)
    raw_url = db.Column(db.Text)
    title = db.Column(db.Text)
    body = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    extra_context = db.Column(db.Text, nullable=True)      # user-supplied additional context
    user_instructions = db.Column(db.Text, nullable=True)  # user-supplied AI instructions

    __table_args__ = (
        db.Index("ix_content_items_type", "type"),
        db.Index("ix_content_items_created_at", "created_at"),
    )

    summaries = db.relationship(
        "Summary",
        back_populates="content_item",
        cascade="all, delete-orphan",
        lazy="select",
    )
    content_tags = db.relationship(
        "ContentTag",
        back_populates="content_item",
        cascade="all, delete-orphan",
        lazy="select",
    )
    collection_items = db.relationship(
        "CollectionItem",
        back_populates="content_item",
        cascade="all, delete-orphan",
        lazy="select",
    )

    @property
    def latest_summary(self):
        if self.summaries:
            return max(self.summaries, key=lambda s: s.created_at)
        return None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "raw_url": self.raw_url,
            "title": self.title,
            "body": self.body,
            "status": self.status,
            "extra_context": self.extra_context,
            "user_instructions": self.user_instructions,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def to_detail_dict(self) -> dict:
        from app.services.content_service import get_related_items
        d = self.to_dict()
        d["summary"] = self.latest_summary.to_dict() if self.latest_summary else None
        d["tags"] = [ct.tag.to_dict() for ct in self.content_tags]
        d["collections"] = [ci.collection.to_dict() for ci in self.collection_items]
        d["related_items"] = get_related_items(self.id)
        return d
