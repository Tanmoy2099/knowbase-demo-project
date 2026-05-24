import json
import structlog
from openai import OpenAI
from ..base import AIProvider
from ..types import SummarizeContext, SummaryResult, TagResult, CollectionSuggestion, EnrichmentResult, TitleResult
from ..retry import with_ai_retry

logger = structlog.get_logger()

SUMMARIZE_SYSTEM_PROMPT = (
    "You are a knowledge organizer. Write a detailed summary of the provided content. "
    "Structure your response as follows:\n"
    "1. **Overview** (2-3 sentences): What is this content about and why does it matter?\n"
    "2. **Key Points** (4-8 bullet points): The most important ideas, concepts, or findings.\n"
    "3. **Takeaways** (1-2 sentences): What should the reader remember or act on?\n\n"
    "Be thorough — a good summary should let someone understand the content without reading the original. "
    "Use plain text with markdown formatting (**, bullet points). Do not add a title."
)

TAG_EXTRACTION_SYSTEM_PROMPT = (
    "You are a content tagger. Extract 3-8 relevant tags from the content. "
    'Return ONLY a JSON array: [{"name": "Tag Name", "slug": "tag-name"}, ...]. '
    "Tags should be specific topics. Slugs must be lowercase with hyphens."
)

COLLECTION_SYSTEM_PROMPT = (
    "You are a strict content organizer. Your job is to assign content to a collection ONLY when there is a clear, obvious topical match.\n\n"
    "Rules:\n"
    "- If an existing collection clearly matches the content topic, return it with confidence >= 0.75.\n"
    "- If no existing collection clearly matches, suggest a NEW one (is_new: true) with confidence >= 0.75.\n"
    "- If you are unsure or the content is too general to categorize, return null.\n"
    "- NEVER assign to a collection just because it exists — the match must be obvious.\n\n"
    'Return ONLY JSON: {"name": "Collection Name", "slug": "collection-slug", '
    '"description": "One sentence description.", "confidence": 0.85, "is_new": false}\n'
    "OR return: null"
)

TITLE_SYSTEM_PROMPT = (
    "You are a content librarian. Generate a concise, descriptive title (5-10 words) "
    "for the provided content. The title should clearly convey the main topic. "
    "Return ONLY the title text — no quotes, no punctuation at the end, no explanation."
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
        if context.extra_context:
            user_msg += f"\nAdditional context from user:\n{context.extra_context}\n"
        if context.user_instructions:
            user_msg += f"\nUser instructions (prioritize these):\n{context.user_instructions}\n"
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
    def suggest_title(self, content: str, content_type: str) -> TitleResult:
        truncated = content[:3000]
        result = self.client.chat.completions.create(
            model=self.fast_model,
            messages=[
                {"role": "system", "content": TITLE_SYSTEM_PROMPT},
                {"role": "user", "content": f"Content type: {content_type}\n\n{truncated}"},
            ],
            max_tokens=30,
            temperature=0.3,
        )
        title = result.choices[0].message.content.strip().strip('"').strip("'")
        return TitleResult(title=title)

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
