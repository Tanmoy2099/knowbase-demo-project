import json
import structlog
from mistralai import Mistral
from ..base import AIProvider
from ..types import SummarizeContext, SummaryResult, TagResult, CollectionSuggestion
from ..retry import with_ai_retry
from .openai_provider import SUMMARIZE_SYSTEM_PROMPT, TAG_EXTRACTION_SYSTEM_PROMPT, COLLECTION_SYSTEM_PROMPT

logger = structlog.get_logger()


class MistralProvider(AIProvider):
    def __init__(self, config):
        api_key = getattr(config, "MISTRAL_API_KEY", None) or config.get("MISTRAL_API_KEY", "")
        self.client = Mistral(api_key=api_key)
        self.fast_model = "mistral-small-latest"
        self.quality_model = "mistral-large-latest"
        self.model = self.fast_model

    @with_ai_retry
    def summarize(self, content: str, context: SummarizeContext) -> SummaryResult:
        truncated = content[:8000]
        user_msg = f"Content type: {context.content_type}\n"
        if context.title:
            user_msg += f"Title: {context.title}\n"
        user_msg += f"\nContent:\n{truncated}"

        response = self.client.chat.complete(
            model=self.model,
            messages=[
                {"role": "system", "content": SUMMARIZE_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=300,
            temperature=0.3,
        )
        text = response.choices[0].message.content or ""
        return SummaryResult(text=text.strip(), model=self.model, provider="mistral")

    @with_ai_retry
    def extract_tags(self, content: str) -> list[TagResult]:
        truncated = content[:6000]
        response = self.client.chat.complete(
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
            items = parsed if isinstance(parsed, list) else parsed.get("tags", [])
            return [TagResult(name=t["name"], slug=t["slug"]) for t in items[:8] if "name" in t and "slug" in t]
        except (json.JSONDecodeError, KeyError):
            logger.warning("Failed to parse tags JSON from Mistral", raw=raw[:200])
            return []

    @with_ai_retry
    def suggest_collection(self, content: str, existing_collections: list[str]) -> CollectionSuggestion | None:
        truncated = content[:5000]
        collections_str = ", ".join(existing_collections) if existing_collections else "none"
        user_msg = f"Existing collections: {collections_str}\n\nContent:\n{truncated}"

        response = self.client.chat.complete(
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
            logger.warning("Failed to parse collection JSON from Mistral", raw=raw[:200])
            return None
