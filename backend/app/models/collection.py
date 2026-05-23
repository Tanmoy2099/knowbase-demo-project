from app.core.db import db
from .base import TimestampMixin, generate_uuid
from .tag import slugify


class Collection(TimestampMixin, db.Model):
    __tablename__ = "collections"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    name = db.Column(db.Text, nullable=False, unique=True)
    slug = db.Column(db.Text, nullable=False, unique=True)
    description = db.Column(db.Text)
    ai_suggested = db.Column(db.Boolean, nullable=False, default=False)

    collection_items = db.relationship(
        "CollectionItem",
        back_populates="collection",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "ai_suggested": self.ai_suggested,
            "created_at": self.created_at.isoformat(),
        }


class CollectionItem(db.Model):
    __tablename__ = "collection_items"

    collection_id = db.Column(
        db.String(36),
        db.ForeignKey("collections.id", ondelete="CASCADE"),
        primary_key=True,
    )
    content_item_id = db.Column(
        db.String(36),
        db.ForeignKey("content_items.id", ondelete="CASCADE"),
        primary_key=True,
    )

    collection = db.relationship("Collection", back_populates="collection_items")
    content_item = db.relationship("ContentItem", back_populates="collection_items")
