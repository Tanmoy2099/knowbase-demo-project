import structlog

from app.core.db import db
from app.models.content_item import ContentItem
from app.models.summary import Summary
from app.models.tag import Tag, ContentTag
from app.models.collection import Collection, CollectionItem

logger = structlog.get_logger()


def enrich_content_item(
    content_item_id: str,
    raw_content: str,
    content_type: str,
) -> None:
    """Run AI enrichment pipeline. Reads extra_context and user_instructions from the DB item."""
    from flask import current_app
    from app.ai.factory import get_provider
    from app.ai.types import SummarizeContext

    item = ContentItem.query.get(content_item_id)
    if not item:
        logger.warning("Content item not found for enrichment", id=content_item_id)
        return

    try:
        item.status = "fetching"
        db.session.commit()

        class _Config:
            def __getattr__(self, name):
                return current_app.config.get(name, "")

        provider = get_provider(_Config())
        context = SummarizeContext(
            content_type=content_type,
            title=item.title,
            extra_context=item.extra_context,
            user_instructions=item.user_instructions,
        )

        content_for_ai = raw_content[:10000]
        enrichment = provider.enrich(content_for_ai, context, _get_collection_names())

        # Auto-set title if not provided by user
        if not item.title and enrichment.suggested_title:
            item.title = enrichment.suggested_title.title

        # Save summary
        summary = Summary(
            content_item_id=content_item_id,
            text=enrichment.summary.text,
            ai_provider=enrichment.summary.provider,
            model=enrichment.summary.model,
        )
        db.session.add(summary)

        # Save tags (replace existing)
        ContentTag.query.filter_by(content_item_id=content_item_id).delete()
        for tag_result in enrichment.tags:
            tag = Tag.get_or_create(tag_result.name)
            db.session.add(ContentTag(content_item_id=content_item_id, tag_id=tag.id))

        # Save collection — only assign if AI is confident enough (>= 0.7)
        if enrichment.collection and enrichment.collection.confidence >= 0.7:
            from sqlalchemy import func
            col = (
                Collection.query
                .filter(func.lower(Collection.name) == enrichment.collection.name.lower())
                .first()
            ) or Collection.query.filter_by(slug=enrichment.collection.slug).first()

            if not col:
                from app.models.tag import slugify
                col = Collection(
                    name=enrichment.collection.name,
                    slug=slugify(enrichment.collection.name),
                    description=enrichment.collection.description,
                    ai_suggested=True,
                )
                db.session.add(col)
                db.session.flush()

            existing = CollectionItem.query.filter_by(
                collection_id=col.id, content_item_id=content_item_id
            ).first()
            if not existing:
                db.session.add(CollectionItem(
                    collection_id=col.id, content_item_id=content_item_id
                ))

        item.status = "enriched"
        db.session.commit()
        logger.info("Content enrichment complete", id=content_item_id, title=item.title)

    except Exception as e:
        db.session.rollback()
        item.status = "failed"
        db.session.commit()
        logger.error("Content enrichment failed", id=content_item_id, error=str(e))


def _get_collection_names() -> list[str]:
    return [c.name for c in Collection.query.with_entities(Collection.name).all()]
