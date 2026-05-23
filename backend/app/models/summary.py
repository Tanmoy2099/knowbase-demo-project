from app.core.db import db
from .base import TimestampMixin, generate_uuid


class Summary(TimestampMixin, db.Model):
    __tablename__ = "summaries"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    content_item_id = db.Column(
        db.String(36),
        db.ForeignKey("content_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    text = db.Column(db.Text, nullable=False)
    ai_provider = db.Column(db.String(50))
    model = db.Column(db.String(100))

    content_item = db.relationship("ContentItem", back_populates="summaries")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "ai_provider": self.ai_provider,
            "model": self.model,
            "created_at": self.created_at.isoformat(),
        }
