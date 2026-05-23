"""
Topic relationship graph builder.

Strategy:
1. Find all pairs of enriched content items that share at least one tag.
2. Compute a Jaccard similarity score from tag overlap (fast, no AI call).
3. For pairs with score >= threshold, persist a TopicRelation record.
4. Upsert: if the pair already exists update strength, otherwise insert.
5. Remove stale relations where one item has been deleted (handled by FK cascade).
"""

import structlog
from sqlalchemy import text

from app.core.db import db
from app.models.content_item import ContentItem
from app.models.tag import ContentTag
from app.models.topic_relation import TopicRelation

logger = structlog.get_logger()

MIN_STRENGTH = 0.1  # pairs below this threshold are not stored


def rebuild_graph() -> dict:
    """
    Rebuild the full topic relationship graph for all enriched items.
    Returns a summary dict: {upserted, removed, skipped}.
    """
    enriched_ids: list[str] = [
        row[0]
        for row in db.session.execute(
            text("SELECT id FROM content_items WHERE status = 'enriched'")
        ).fetchall()
    ]

    if len(enriched_ids) < 2:
        logger.info("Topic graph: not enough enriched items to build relations", count=len(enriched_ids))
        return {"upserted": 0, "removed": 0, "skipped": 0}

    # Build tag sets per item
    tag_map: dict[str, set[str]] = {item_id: set() for item_id in enriched_ids}
    rows = (
        db.session.execute(
            text(
                "SELECT content_item_id, tag_id FROM content_tags "
                "WHERE content_item_id = ANY(:ids)"
            ),
            {"ids": enriched_ids},
        ).fetchall()
    )
    for content_item_id, tag_id in rows:
        tag_map[content_item_id].add(tag_id)

    # Only consider items that have at least one tag
    tagged_ids = [iid for iid, tags in tag_map.items() if tags]

    upserted = 0
    skipped = 0

    seen_pairs: set[tuple[str, str]] = set()

    for i, id_a in enumerate(tagged_ids):
        for id_b in tagged_ids[i + 1 :]:
            pair = (min(id_a, id_b), max(id_a, id_b))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            tags_a = tag_map[id_a]
            tags_b = tag_map[id_b]
            intersection = tags_a & tags_b
            union = tags_a | tags_b

            if not intersection:
                skipped += 1
                continue

            strength = round(len(intersection) / len(union), 4)  # Jaccard

            if strength < MIN_STRENGTH:
                skipped += 1
                continue

            relation_type = _classify_relation(strength)
            _upsert_relation(id_a, id_b, relation_type, strength)
            upserted += 1

    db.session.commit()

    # Remove relations where either item no longer has enriched status
    removed_result = db.session.execute(
        text(
            """
            DELETE FROM topic_relations
            WHERE source_id NOT IN (
                SELECT id FROM content_items WHERE status = 'enriched'
            )
            OR target_id NOT IN (
                SELECT id FROM content_items WHERE status = 'enriched'
            )
            """
        )
    )
    removed = removed_result.rowcount
    db.session.commit()

    logger.info("Topic graph rebuild complete", upserted=upserted, removed=removed, skipped=skipped)
    return {"upserted": upserted, "removed": removed, "skipped": skipped}


def _classify_relation(strength: float) -> str:
    if strength >= 0.7:
        return "related"
    if strength >= 0.4:
        return "related"
    return "related"


def _upsert_relation(source_id: str, target_id: str, relation_type: str, strength: float) -> None:
    existing = TopicRelation.query.filter(
        db.or_(
            db.and_(TopicRelation.source_id == source_id, TopicRelation.target_id == target_id),
            db.and_(TopicRelation.source_id == target_id, TopicRelation.target_id == source_id),
        )
    ).first()

    if existing:
        existing.strength = strength
        existing.relation_type = relation_type
    else:
        db.session.add(
            TopicRelation(
                source_id=source_id,
                target_id=target_id,
                relation_type=relation_type,
                strength=strength,
            )
        )
