import json
import httpx
import structlog
from ..base import AIProvider
from ..types import SummarizeContext, SummaryResult, TagResult, CollectionSuggestion
from ..retry import with_ai_retry
from .openai_provider import SUMMARIZE_SYSTEM_PROMPT, TAG_EXTRACTION_SYSTEM_PROMPT, COLLECTION_SYSTEM_PROMPT

logger = structlog.get_logger()


class OllamaProvider(AIProvider):
    def __init__(self, config):
        base_url = getattr(config, "OLLAMA_BASE_URL", None) or config.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
        model = getattr(config, "OLLAMA_MODEL", None) or config.get("OLLAMA_MODEL", "llama3.2")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = 120.0

    def _chat(self, messages: list[dict], json_mode: bool = False) -> str:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if json_mode:
            payload["format"] = "json"

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "")

    @with_ai_retry
    def summarize(self, content: str, context: SummarizeContext) -> SummaryResult:
        truncated = content[:8000]
        user_msg = f"Content type: {context.content_type}\n"
        if context.title:
            user_msg += f"Title: {context.title}\n"
        user_msg += f"\nContent:\n{truncated}"

        text = self._chat([
            {"role": "system", "content": SUMMARIZE_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ])
        return SummaryResult(text=text.strip(), model=self.model, provider="ollama")

    @with_ai_retry
    def extract_tags(self, content: str) -> list[TagResult]:
        truncated = content[:6000]
        raw = self._chat([
            {"role": "system", "content": TAG_EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": truncated},
        ], json_mode=True)
        try:
            parsed = json.loads(raw)
            items = parsed if isinstance(parsed, list) else parsed.get("tags", [])
            return [TagResult(name=t["name"], slug=t["slug"]) for t in items[:8] if "name" in t and "slug" in t]
        except (json.JSONDecodeError, KeyError):
            logger.warning("Failed to parse tags JSON from Ollama", raw=raw[:200])
            return []

    @with_ai_retry
    def suggest_collection(self, content: str, existing_collections: list[str]) -> CollectionSuggestion | None:
        truncated = content[:5000]
        collections_str = ", ".join(existing_collections) if existing_collections else "none"
        user_msg = f"Existing collections: {collections_str}\n\nContent:\n{truncated}"

        raw = self._chat([
            {"role": "system", "content": COLLECTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ], json_mode=True)
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
            logger.warning("Failed to parse collection JSON from Ollama", raw=raw[:200])
            return None
