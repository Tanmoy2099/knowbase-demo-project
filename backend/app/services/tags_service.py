from app.models.tag import Tag, ContentTag


def list_tags() -> list[dict]:
    tags = Tag.query.order_by(Tag.name).all()
    result = []
    for t in tags:
        d = t.to_dict()
        d["item_count"] = ContentTag.query.filter_by(tag_id=t.id).count()
        result.append(d)
    return result
