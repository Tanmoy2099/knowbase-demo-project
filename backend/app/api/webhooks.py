import json
import re
import structlog
import httpx
from flask import Blueprint, request, jsonify
from pydantic import BaseModel, ValidationError

from app.core.security import require_n8n_signature
from app.services.ai_service import enrich_content_item

logger = structlog.get_logger()

webhooks_bp = Blueprint("webhooks", __name__)


class N8NWebhookPayload(BaseModel):
    content_item_id: str
    raw_content: str
    content_type: str


def _extract_youtube_id(url: str) -> str | None:
    """Extract YouTube video ID from any youtube.com or youtu.be URL."""
    patterns = [
        r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:embed|shorts)/([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def _fetch_youtube_content(url: str) -> str:
    """Fetch transcript + oEmbed metadata for a YouTube video."""
    video_id = _extract_youtube_id(url)
    transcript_text = ""

    if video_id:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US", "en-GB"])
            transcript_text = " ".join(entry["text"] for entry in transcript)
            logger.info("YouTube transcript extracted", video_id=video_id, chars=len(transcript_text))
        except Exception as e:
            logger.warning("YouTube transcript unavailable", video_id=video_id, error=str(e))

    # Always fetch oEmbed for title/author metadata
    meta = {}
    try:
        resp = httpx.get(
            "https://www.youtube.com/oembed",
            params={"url": url, "format": "json"},
            timeout=10.0,
        )
        resp.raise_for_status()
        meta = resp.json()
    except Exception as e:
        logger.warning("YouTube oEmbed fetch failed", url=url, error=str(e))

    # Combine: metadata header + full transcript
    parts = []
    if meta.get("title"):
        parts.append(f"Title: {meta['title']}")
    if meta.get("author_name"):
        parts.append(f"Channel: {meta['author_name']}")
    if transcript_text:
        parts.append(f"\nFull Transcript:\n{transcript_text}")
    else:
        parts.append(f"\nNo transcript available. URL: {url}")
        if meta:
            parts.append(f"Metadata: {json.dumps(meta)}")

    return "\n".join(parts)


def _fetch_content(content_type: str, raw_content: str) -> str:
    """Resolve raw_content into rich text for AI enrichment."""
    if content_type == "youtube":
        return _fetch_youtube_content(raw_content)

    if content_type == "link":
        try:
            resp = httpx.get(raw_content, timeout=15.0, follow_redirects=True)
            resp.raise_for_status()
            return resp.text[:50_000]
        except Exception as e:
            logger.warning("Webpage fetch failed", url=raw_content, error=str(e))
            return raw_content

    return raw_content


@webhooks_bp.post("/n8n")
@require_n8n_signature
def n8n_webhook():
    try:
        payload = N8NWebhookPayload.model_validate(request.get_json(force=True) or {})
    except ValidationError as e:
        details = [{"field": str(err["loc"]), "message": err["msg"]} for err in e.errors()]
        return jsonify({"data": None, "error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": details}}), 422

    enrichment_text = _fetch_content(payload.content_type, payload.raw_content)

    try:
        enrich_content_item(payload.content_item_id, enrichment_text, payload.content_type)
    except Exception as e:
        logger.error("AI enrichment failed", error=str(e), content_item_id=payload.content_item_id)
        return jsonify({"data": None, "error": {"code": "ENRICHMENT_FAILED", "message": "Content enrichment failed"}}), 500

    return jsonify({"data": {"status": "ok"}, "error": None})
