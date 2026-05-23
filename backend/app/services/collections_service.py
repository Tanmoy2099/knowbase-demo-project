import structlog

from app.core.db import db
from app.models.collection import Collection, CollectionItem
from app.models.tag import slugify

logger = structlog.get_logger()


def list_collections() -> list[dict]:
    collections = Collection.query.order_by(Collection.name).all()
    result = []
    for c in collections:
        d = c.to_dict()
        d["item_count"] = CollectionItem.query.filter_by(collection_id=c.id).count()
        result.append(d)
    return result


def create_collection(
    name: str,
    description: str | None = None,
    ai_suggested: bool = False,
) -> Collection:
    c = Collection(
        name=name,
        slug=slugify(name),
        description=description,
        ai_suggested=ai_suggested,
    )
    db.session.add(c)
    db.session.commit()
    logger.info("Created collection", id=c.id, name=name)
    return c


def update_collection(
    collection_id: str,
    name: str | None = None,
    description: str | None = None,
) -> Collection | None:
    c = Collection.query.get(collection_id)
    if not c:
        return None
    if name is not None:
        c.name = name
        c.slug = slugify(name)
    if description is not None:
        c.description = description
    db.session.commit()
    return c


def delete_collection(collection_id: str) -> bool:
    c = Collection.query.get(collection_id)
    if not c:
        return False
    db.session.delete(c)
    db.session.commit()
    return True
