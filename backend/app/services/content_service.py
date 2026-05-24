import structlog
from sqlalchemy.orm import joinedload

from app.core.db import db
from app.models.content_item import ContentItem
from app.models.tag import Tag, ContentTag, slugify
from app.models.collection import Collection, CollectionItem

logger = structlog.get_logger()


def create_content_item(
    type_: str,
    raw_url: str | None = None,
    title: str | None = None,
    body: str | None = None,
    extra_context: str | None = None,
    user_instructions: str | None = None,
) -> ContentItem:
    item = ContentItem(
        type=type_,
        raw_url=raw_url,
        title=title,
        body=body,
        extra_context=extra_context,
        user_instructions=user_instructions,
    )
    db.session.add(item)
    db.session.commit()
    logger.info("Created content item", id=item.id, type=type_)
    return item


def list_content_items(
    tag: str | None = None,
    collection: str | None = None,
    type_: str | None = None,
    q: str | None = None,
    status: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[ContentItem], int]:
    query = ContentItem.query

    if type_:
        query = query.filter(ContentItem.type == type_)
    if status:
        query = query.filter(ContentItem.status == status)
    if q:
        query = query.filter(
            db.or_(
                ContentItem.title.ilike(f"%{q}%"),
                ContentItem.body.ilike(f"%{q}%"),
                ContentItem.raw_url.ilike(f"%{q}%"),
            )
        )
    if tag:
        query = query.join(ContentTag).join(Tag).filter(Tag.slug == slugify(tag))
    if collection:
        query = (
            query.join(CollectionItem)
            .join(Collection)
            .filter(Collection.slug == collection)
        )

    total = query.count()
    items = (
        query.order_by(ContentItem.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return items, total


def get_content_item(item_id: str) -> ContentItem | None:
    return ContentItem.query.get(item_id)


def get_content_item_detail(item_id: str) -> ContentItem | None:
    """Load item with all relationships eagerly."""
    return (
        ContentItem.query.options(
            joinedload(ContentItem.summaries),
            joinedload(ContentItem.content_tags).joinedload(ContentTag.tag),
            joinedload(ContentItem.collection_items).joinedload(CollectionItem.collection),
        )
        .filter(ContentItem.id == item_id)
        .first()
    )


def update_content_item(
    item_id: str,
    title: str | None = None,
    tag_names: list[str] | None = None,
    collection_id: str | None = None,
) -> ContentItem | None:
    item = ContentItem.query.get(item_id)
    if not item:
        return None

    if title is not None:
        item.title = title

    if tag_names is not None:
        # Replace all tags
        ContentTag.query.filter_by(content_item_id=item_id).delete()
        for name in tag_names:
            tag = Tag.get_or_create(name)
            db.session.add(ContentTag(content_item_id=item_id, tag_id=tag.id))

    if collection_id is not None:
        CollectionItem.query.filter_by(content_item_id=item_id).delete()
        if collection_id:  # empty string = remove from all collections
            db.session.add(
                CollectionItem(collection_id=collection_id, content_item_id=item_id)
            )

    db.session.commit()
    return item


def delete_content_item(item_id: str) -> bool:
    item = ContentItem.query.get(item_id)
    if not item:
        return False
    db.session.delete(item)
    db.session.commit()
    # Remove tags that no longer have any associated content
    orphaned = (
        db.session.query(Tag)
        .outerjoin(ContentTag, ContentTag.tag_id == Tag.id)
        .filter(ContentTag.tag_id.is_(None))
        .all()
    )
    if orphaned:
        for tag in orphaned:
            db.session.delete(tag)
        db.session.commit()
    return True


def extract_pdf_text(file_path: str) -> str:
    """Extract plain text from a PDF file using pypdf."""
    from pypdf import PdfReader
    reader = PdfReader(file_path)
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text.strip())
    return "\n\n".join(pages)


def get_related_items(item_id: str, limit: int = 5) -> list[dict]:
    """Return content items related to item_id, ordered by strength descending."""
    from app.models.topic_relation import TopicRelation

    relations = (
        TopicRelation.query
        .filter(
            db.or_(
                TopicRelation.source_id == item_id,
                TopicRelation.target_id == item_id,
            )
        )
        .order_by(TopicRelation.strength.desc())
        .limit(limit)
        .all()
    )

    result = []
    for rel in relations:
        related_id = rel.target_id if rel.source_id == item_id else rel.source_id
        related = ContentItem.query.get(related_id)
        if related:
            d = related.to_dict()
            d["relation_strength"] = rel.strength
            d["relation_type"] = rel.relation_type
            result.append(d)
    return result
