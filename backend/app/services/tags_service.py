from app.models.tag import Tag, ContentTag
from app.core.db import db


def list_tags() -> list[dict]:
    # INNER JOIN excludes orphan tags (tags with no associated content items)
    rows = (
        db.session.query(Tag, db.func.count(ContentTag.tag_id).label("item_count"))
        .join(ContentTag, ContentTag.tag_id == Tag.id)
        .group_by(Tag.id)
        .order_by(Tag.name)
        .all()
    )
    return [
        {"id": t.id, "name": t.name, "slug": t.slug, "item_count": count}
        for t, count in rows
    ]
