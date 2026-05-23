import re

from app.core.db import db
from .base import generate_uuid


def slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


class Tag(db.Model):
    __tablename__ = "tags"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    name = db.Column(db.Text, nullable=False, unique=True)
    slug = db.Column(db.Text, nullable=False, unique=True)

    content_tags = db.relationship(
        "ContentTag",
        back_populates="tag",
        cascade="all, delete-orphan",
        lazy="select",
    )

    @classmethod
    def get_or_create(cls, name: str) -> "Tag":
        slug = slugify(name)
        tag = cls.query.filter_by(slug=slug).first()
        if not tag:
            from app.core.db import db as _db
            tag = cls(name=name, slug=slug)
            _db.session.add(tag)
            _db.session.flush()
        return tag

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "slug": self.slug}


class ContentTag(db.Model):
    __tablename__ = "content_tags"

    content_item_id = db.Column(
        db.String(36),
        db.ForeignKey("content_items.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id = db.Column(
        db.String(36),
        db.ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )

    content_item = db.relationship("ContentItem", back_populates="content_tags")
    tag = db.relationship("Tag", back_populates="content_tags")
