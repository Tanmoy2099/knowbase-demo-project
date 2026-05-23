from app.core.db import db
from .base import generate_uuid, utcnow


class TopicRelation(db.Model):
    __tablename__ = "topic_relations"

    id = db.Column(db.String(36), primary_key=True, default=generate_uuid)
    source_id = db.Column(
        db.String(36),
        db.ForeignKey("content_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_id = db.Column(
        db.String(36),
        db.ForeignKey("content_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relation_type = db.Column(db.String(50))  # related|prerequisite|contradicts|extends
    strength = db.Column(db.Float)
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        db.CheckConstraint(
            "strength >= 0 AND strength <= 1",
            name="ck_topic_relations_strength_range",
        ),
        db.UniqueConstraint("source_id", "target_id", name="uq_topic_relations_pair"),
    )

    source = db.relationship("ContentItem", foreign_keys=[source_id])
    target = db.relationship("ContentItem", foreign_keys=[target_id])

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "strength": self.strength,
            "created_at": self.created_at.isoformat(),
        }
