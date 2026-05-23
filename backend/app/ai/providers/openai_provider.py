import json
import structlog
from openai import OpenAI
from ..base import AIProvider
from ..types import SummarizeContext, SummaryResult, TagResult, CollectionSuggestion, EnrichmentResult
from ..retry import with_ai_retry

logger = structlog.get_logger()

SUMMARIZE_SYSTEM_PROMPT = (
    "You are a knowledge organizer. Summarize the provided content in 2-4 sentences, "
    "focusing on key insights and takeaways. Be concise and precise. "
    "Respond with plain text only."
)

TAG_EXTRACTION_SYSTEM_PROMPT = (
    "You are a content tagger. Extract 3-8 relevant tags from the content. "
    'Return ONLY a JSON array: [{"name": "Tag Name", "slug": "tag-name"}, ...]. '
    "Tags should be specific topics. Slugs must be lowercase with hyphens."
)

COLLECTION_SYSTEM_PROMPT = (
    "You are a content organizer. Given content and existing collections, "
    "assign the content to the best existing collection or suggest a new one. "
    'Return ONLY JSON: {"name": "Collection Name", "slug": "collection-slug", '
    '"description": "One sentence description.", "confidence": 0.85, "is_new": false}. '
    "Return null if the content does not clearly belong to any category."
)


class OpenAIProvider(AIProvider):
    def __init__(self, config):
        api_key = getattr(config, "OPENAI_API_KEY", None) or config.get("OPENAI_API_KEY", "")
        self.client = OpenAI(api_key=api_key)
        self.fast_model = "gpt-4o-mini"
        self.quality_model = "gpt-4o"
        self.model = self.fast_model

    @with_ai_retry
    def summarize(self, content: str, context: SummarizeContext) -> SummaryResult:
        truncated = content[:8000]
        user_msg = f"Content type: {context.content_type}\n"
        if context.title:
            user_msg += f"Title: {context.title}\n"
        user_msg += f"\nContent:\n{truncated}"

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SUMMARIZE_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=300,
            temperature=0.3,
        )
        text = response.choices[0].message.content or ""
        return SummaryResult(text=text.strip(), model=self.model, provider="openai")

    @with_ai_retry
    def extract_tags(self, content: str) -> list[TagResult]:
        truncated = content[:6000]
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": TAG_EXTRACTION_SYSTEM_PROMPT},
                {"role": "user", "content": truncated},
            ],
            response_format={"type": "json_object"},
            max_tokens=200,
            temperature=0.1,
        )
        raw = response.choices[0].message.content or "[]"
        try:
            parsed = json.loads(raw)
            # Handle both {"tags": [...]} and [...]
            items = parsed if isinstance(parsed, list) else parsed.get("tags", [])
            return [TagResult(name=t["name"], slug=t["slug"]) for t in items[:8] if "name" in t and "slug" in t]
        except (json.JSONDecodeError, KeyError):
            logger.warning("Failed to parse tags JSON", raw=raw[:200])
            return []

    @with_ai_retry
    def suggest_collection(self, content: str, existing_collections: list[str]) -> CollectionSuggestion | None:
        truncated = content[:5000]
        collections_str = ", ".join(existing_collections) if existing_collections else "none"
        user_msg = f"Existing collections: {collections_str}\n\nContent:\n{truncated}"

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": COLLECTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
            max_tokens=150,
            temperature=0.1,
        )
        raw = response.choices[0].message.content or "null"
        try:
            parsed = json.loads(raw)
            if not parsed:
                return None
            return CollectionSuggestion(
                name=parsed["name"],
                slug=parsed["slug"],
                description=parsed.get("description", ""),
                confidence=float(parsed.get("confidence", 0.7)),
                is_new=bool(parsed.get("is_new", True)),
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            logger.warning("Failed to parse collection JSON", raw=raw[:200])
            return None
