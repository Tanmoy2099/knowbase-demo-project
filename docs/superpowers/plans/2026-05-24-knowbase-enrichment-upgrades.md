# Knowbase Enrichment Upgrades Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add YouTube transcript extraction, AI-generated titles, extra-context/instructions input fields, and a cron job to recover stuck pending items.

**Architecture:** All five features extend the existing Flask + Ollama + n8n stack. DB columns `extra_context` and `user_instructions` are added via Alembic. The AI enrichment pipeline (`ai_service.py`) receives these fields and threads them through provider prompts. YouTube transcript is fetched in `webhooks.py` using `youtube-transcript-api`. The stuck-item cron is a new n8n workflow that calls a new Flask admin endpoint. Frontend form gains two new optional textarea fields.

**Tech Stack:** Flask, SQLAlchemy/Alembic (Postgres), Ollama via httpx, youtube-transcript-api, n8n, Next.js/React, TypeScript.

---

## File Map

| File | Change |
|---|---|
| `backend/requirements.txt` | Add `youtube-transcript-api` |
| `backend/app/models/content_item.py` | Add `extra_context`, `user_instructions` columns |
| `backend/migrations/versions/0002_extra_context_instructions.py` | New Alembic migration |
| `backend/app/services/content_service.py` | Accept new fields in `create_content_item` |
| `backend/app/api/content.py` | Accept new fields in `CreateContentRequest` |
| `backend/app/api/webhooks.py` | YouTube transcript fetch; pass context+instructions to enrichment |
| `backend/app/api/admin.py` | New `GET /api/admin/stuck-items` endpoint |
| `backend/app/ai/types.py` | Add `user_instructions`, `extra_context` to `SummarizeContext`; add `TitleResult` |
| `backend/app/ai/base.py` | Add `suggest_title()` abstract method |
| `backend/app/ai/providers/openai_provider.py` | Implement `suggest_title()`; update `summarize()` prompt to use instructions/context |
| `backend/app/ai/providers/ollama_provider.py` | Same |
| `backend/app/ai/providers/mistral_provider.py` | Same |
| `backend/app/services/ai_service.py` | Call `suggest_title()` when title missing; pass context+instructions |
| `backend/app/workflows/retry_stuck_items.json` | New n8n workflow (10-min cron) |
| `frontend/src/types/index.ts` | Add `extra_context`, `user_instructions` to `ContentItem` and `CreateContentRequest` |
| `frontend/src/components/ContentSaveForm.tsx` | Add two new optional textarea fields |

---

## Task 1: Add youtube-transcript-api dependency

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add the package**

In `backend/requirements.txt`, add after the `pypdf` line:
```
youtube-transcript-api==1.0.3
```

- [ ] **Step 2: Verify it installs in the container**

```bash
docker exec knowbase-backend pip install youtube-transcript-api==1.0.3
```
Expected: `Successfully installed youtube-transcript-api-1.0.3`

- [ ] **Step 3: Commit**

```bash
cd /Users/codeclouds-tanmoy/projects/Demo-AI-project
git add backend/requirements.txt
git commit -m "chore: add youtube-transcript-api dependency"
```

---

## Task 2: Database migration — extra_context and user_instructions

**Files:**
- Modify: `backend/app/models/content_item.py`
- Create: `backend/migrations/versions/0002_extra_context_instructions.py`

- [ ] **Step 1: Add columns to the model**

In `backend/app/models/content_item.py`, add two columns after `status`:
```python
status = db.Column(db.String(20), nullable=False, default="pending", index=True)
extra_context = db.Column(db.Text, nullable=True)      # user-supplied additional context
user_instructions = db.Column(db.Text, nullable=True)  # user-supplied AI instructions
```

Also update `to_dict()` to expose both fields:
```python
def to_dict(self) -> dict:
    return {
        "id": self.id,
        "type": self.type,
        "raw_url": self.raw_url,
        "title": self.title,
        "body": self.body,
        "status": self.status,
        "extra_context": self.extra_context,
        "user_instructions": self.user_instructions,
        "created_at": self.created_at.isoformat(),
        "updated_at": self.updated_at.isoformat(),
    }
```

- [ ] **Step 2: Generate the migration**

```bash
docker exec knowbase-backend flask db migrate -m "add extra_context and user_instructions to content_items"
```

Expected: Creates `backend/migrations/versions/0002_*.py`

- [ ] **Step 3: Verify the generated migration looks correct**

Open the generated file. It should contain:
```python
op.add_column('content_items', sa.Column('extra_context', sa.Text(), nullable=True))
op.add_column('content_items', sa.Column('user_instructions', sa.Text(), nullable=True))
```

- [ ] **Step 4: Run the migration**

```bash
docker exec knowbase-backend flask db upgrade
```
Expected: `Running upgrade ... -> ...`

- [ ] **Step 5: Confirm columns exist in DB**

```bash
docker exec knowbase-postgres psql -U knowbase -d knowbase -c "\d content_items" | grep -E "extra_context|user_instructions"
```
Expected: both column names appear.

- [ ] **Step 6: Rename the file to use sequential prefix**

Rename the generated file to `0002_extra_context_instructions.py` so it matches the project naming convention.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/content_item.py backend/migrations/
git commit -m "feat: add extra_context and user_instructions columns to content_items"
```

---

## Task 3: Backend API — accept and store new fields

**Files:**
- Modify: `backend/app/services/content_service.py`
- Modify: `backend/app/api/content.py`

- [ ] **Step 1: Update `create_content_item` to accept new fields**

In `backend/app/services/content_service.py`, update the function signature and body:
```python
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
```

- [ ] **Step 2: Update `CreateContentRequest` Pydantic model in content.py**

In `backend/app/api/content.py`, update `CreateContentRequest`:
```python
class CreateContentRequest(BaseModel):
    type: Literal["link", "note", "pdf", "youtube"]
    raw_url: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None
    extra_context: Optional[str] = None      # user additional context for AI
    user_instructions: Optional[str] = None  # user AI behavior instructions
```

- [ ] **Step 3: Pass new fields through in `create_content()`**

In the `create_content()` route function, update the `create_content_item` call:
```python
item = content_service.create_content_item(
    type_=payload.type,
    raw_url=payload.raw_url,
    title=payload.title,
    body=payload.body,
    extra_context=payload.extra_context,
    user_instructions=payload.user_instructions,
)
```

- [ ] **Step 4: Smoke-test via curl**

```bash
curl -s -X POST http://localhost:5001/api/content \
  -H "Content-Type: application/json" \
  -d '{"type":"note","body":"test","extra_context":"some context","user_instructions":"focus on security implications"}' \
  | python3 -m json.tool | grep -E "extra_context|user_instructions|id"
```
Expected: response includes `"extra_context": "some context"` and `"user_instructions": "focus on security implications"`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/content_service.py backend/app/api/content.py
git commit -m "feat: accept extra_context and user_instructions in content API"
```

---

## Task 4: AI types and base — TitleResult + context fields + suggest_title

**Files:**
- Modify: `backend/app/ai/types.py`
- Modify: `backend/app/ai/base.py`

- [ ] **Step 1: Update `SummarizeContext` and add `TitleResult` in types.py**

Replace the full content of `backend/app/ai/types.py`:
```python
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SummarizeContext:
    content_type: str              # link|note|pdf|youtube
    title: Optional[str] = None
    extra_context: Optional[str] = None      # user-supplied extra context
    user_instructions: Optional[str] = None  # user-supplied AI instructions


@dataclass
class SummaryResult:
    text: str
    model: str
    provider: str


@dataclass
class TitleResult:
    title: str


@dataclass
class TagResult:
    name: str
    slug: str


@dataclass
class CollectionSuggestion:
    name: str
    slug: str
    description: str
    confidence: float
    is_new: bool


@dataclass
class EnrichmentResult:
    summary: SummaryResult
    tags: list[TagResult]
    collection: Optional[CollectionSuggestion]
    suggested_title: Optional[TitleResult] = None
```

- [ ] **Step 2: Add `suggest_title()` abstract method to base.py**

Replace `backend/app/ai/base.py`:
```python
from abc import ABC, abstractmethod
from .types import SummarizeContext, SummaryResult, TagResult, CollectionSuggestion, EnrichmentResult, TitleResult


class AIProvider(ABC):
    @abstractmethod
    def summarize(self, content: str, context: SummarizeContext) -> SummaryResult: ...

    @abstractmethod
    def extract_tags(self, content: str) -> list[TagResult]: ...

    @abstractmethod
    def suggest_collection(self, content: str, existing_collections: list[str]) -> CollectionSuggestion | None: ...

    @abstractmethod
    def suggest_title(self, content: str, content_type: str) -> TitleResult: ...

    def enrich(
        self,
        content: str,
        context: SummarizeContext,
        existing_collections: list[str],
    ) -> EnrichmentResult:
        summary = self.summarize(content, context)
        tags = self.extract_tags(content)
        collection = self.suggest_collection(content, existing_collections)
        title = self.suggest_title(content, context.content_type)
        return EnrichmentResult(
            summary=summary,
            tags=tags,
            collection=collection,
            suggested_title=title,
        )
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/ai/types.py backend/app/ai/base.py
git commit -m "feat: add TitleResult, suggest_title() to AI base; extend SummarizeContext"
```

---

## Task 5: Implement suggest_title and update summarize prompts in all providers

**Files:**
- Modify: `backend/app/ai/providers/openai_provider.py`
- Modify: `backend/app/ai/providers/ollama_provider.py`
- Modify: `backend/app/ai/providers/mistral_provider.py`

- [ ] **Step 1: Update prompts and add suggest_title in openai_provider.py**

Update `SUMMARIZE_SYSTEM_PROMPT` and add `TITLE_SYSTEM_PROMPT` at the top of `backend/app/ai/providers/openai_provider.py`:

```python
SUMMARIZE_SYSTEM_PROMPT = (
    "You are a knowledge organizer. Write a detailed summary of the provided content. "
    "Structure your response as follows:\n"
    "1. **Overview** (2-3 sentences): What is this content about and why does it matter?\n"
    "2. **Key Points** (4-8 bullet points): The most important ideas, concepts, or findings.\n"
    "3. **Takeaways** (1-2 sentences): What should the reader remember or act on?\n\n"
    "Be thorough — a good summary should let someone understand the content without reading the original. "
    "Use plain text with markdown formatting (**, bullet points). Do not add a title."
)

TITLE_SYSTEM_PROMPT = (
    "You are a content librarian. Generate a concise, descriptive title (5-10 words) "
    "for the provided content. The title should clearly convey the main topic. "
    "Return ONLY the title text — no quotes, no punctuation at the end, no explanation."
)
```

Add `suggest_title()` method to `OpenAIProvider`:
```python
@with_ai_retry
def suggest_title(self, content: str, content_type: str) -> TitleResult:
    from ..types import TitleResult
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
```

Update `summarize()` in `OpenAIProvider` to inject user instructions and extra context:
```python
@with_ai_retry
def summarize(self, content: str, context: SummarizeContext) -> SummaryResult:
    truncated = content[:12000]
    user_msg = f"Content type: {context.content_type}\n"
    if context.title:
        user_msg += f"Title: {context.title}\n"
    if context.extra_context:
        user_msg += f"\nAdditional context from user:\n{context.extra_context}\n"
    if context.user_instructions:
        user_msg += f"\nUser instructions (prioritize these):\n{context.user_instructions}\n"
    user_msg += f"\nContent:\n{truncated}"

    result = self.client.chat.completions.create(
        model=self.fast_model,
        messages=[
            {"role": "system", "content": SUMMARIZE_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=1000,
        temperature=0.3,
    )
    text = result.choices[0].message.content.strip()
    return SummaryResult(text=text, model=self.fast_model, provider="openai")
```

- [ ] **Step 2: Add suggest_title to OllamaProvider in ollama_provider.py**

Add the import at the top:
```python
from ..types import SummarizeContext, SummaryResult, TagResult, CollectionSuggestion, TitleResult
```

Add the `suggest_title()` method and update `summarize()` to use context fields:
```python
@with_ai_retry
def suggest_title(self, content: str, content_type: str) -> TitleResult:
    truncated = content[:3000]
    raw = self._chat([
        {"role": "system", "content": TITLE_SYSTEM_PROMPT},
        {"role": "user", "content": f"Content type: {content_type}\n\n{truncated}"},
    ])
    title = raw.strip().strip('"').strip("'").split("\n")[0][:120]
    return TitleResult(title=title)

@with_ai_retry
def summarize(self, content: str, context: SummarizeContext) -> SummaryResult:
    truncated = content[:12000]
    user_msg = f"Content type: {context.content_type}\n"
    if context.title:
        user_msg += f"Title: {context.title}\n"
    if context.extra_context:
        user_msg += f"\nAdditional context from user:\n{context.extra_context}\n"
    if context.user_instructions:
        user_msg += f"\nUser instructions (prioritize these):\n{context.user_instructions}\n"
    user_msg += f"\nContent:\n{truncated}"

    text = self._chat([
        {"role": "system", "content": SUMMARIZE_SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ])
    return SummaryResult(text=text.strip(), model=self.model, provider="ollama")
```

Note: `TITLE_SYSTEM_PROMPT` is imported from `openai_provider` — add it to the import line at the top of `ollama_provider.py`:
```python
from .openai_provider import SUMMARIZE_SYSTEM_PROMPT, TAG_EXTRACTION_SYSTEM_PROMPT, COLLECTION_SYSTEM_PROMPT, TITLE_SYSTEM_PROMPT
```

- [ ] **Step 3: Add suggest_title to MistralProvider in mistral_provider.py**

Add `TITLE_SYSTEM_PROMPT` to the import:
```python
from .openai_provider import SUMMARIZE_SYSTEM_PROMPT, TAG_EXTRACTION_SYSTEM_PROMPT, COLLECTION_SYSTEM_PROMPT, TITLE_SYSTEM_PROMPT
```

Add the method (Mistral uses the same client interface pattern as OpenAI):
```python
@with_ai_retry
def suggest_title(self, content: str, content_type: str) -> TitleResult:
    from ..types import TitleResult
    truncated = content[:3000]
    result = self.client.chat.complete(
        model="mistral-small-latest",
        messages=[
            {"role": "system", "content": TITLE_SYSTEM_PROMPT},
            {"role": "user", "content": f"Content type: {content_type}\n\n{truncated}"},
        ],
        max_tokens=30,
        temperature=0.3,
    )
    title = result.choices[0].message.content.strip().strip('"').strip("'")
    return TitleResult(title=title)
```

Update `summarize()` in `MistralProvider` to inject the context fields (same pattern as OpenAI):
```python
@with_ai_retry
def summarize(self, content: str, context: SummarizeContext) -> SummaryResult:
    truncated = content[:12000]
    user_msg = f"Content type: {context.content_type}\n"
    if context.title:
        user_msg += f"Title: {context.title}\n"
    if context.extra_context:
        user_msg += f"\nAdditional context from user:\n{context.extra_context}\n"
    if context.user_instructions:
        user_msg += f"\nUser instructions (prioritize these):\n{context.user_instructions}\n"
    user_msg += f"\nContent:\n{truncated}"
    result = self.client.chat.complete(
        model="mistral-small-latest",
        messages=[
            {"role": "system", "content": SUMMARIZE_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=1000,
        temperature=0.3,
    )
    text = result.choices[0].message.content.strip()
    return SummaryResult(text=text, model="mistral-small-latest", provider="mistral")
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/ai/providers/
git commit -m "feat: add suggest_title() to all AI providers; inject extra_context and user_instructions into summarize"
```

---

## Task 6: Update ai_service.py — title generation + pass new context fields

**Files:**
- Modify: `backend/app/services/ai_service.py`

- [ ] **Step 1: Update `enrich_content_item` signature and body**

Replace the full function in `backend/app/services/ai_service.py`:

```python
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

        # Save collection
        if enrichment.collection:
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
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/ai_service.py
git commit -m "feat: auto-generate title when missing; pass extra_context and user_instructions to AI"
```

---

## Task 7: YouTube transcript extraction in webhooks.py

**Files:**
- Modify: `backend/app/api/webhooks.py`

- [ ] **Step 1: Replace `_fetch_content` with transcript-aware version**

Replace the entire content of `backend/app/api/webhooks.py`:

```python
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
            from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
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
```

- [ ] **Step 2: Rebuild backend image to install youtube-transcript-api**

```bash
cd /Users/codeclouds-tanmoy/projects/Demo-AI-project
docker compose up -d --build backend
```
Wait ~60s for build. Then verify:
```bash
docker exec knowbase-backend python -c "from youtube_transcript_api import YouTubeTranscriptApi; print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Quick smoke test — save a YouTube URL and check the log**

```bash
ITEM=$(curl -s -X POST http://localhost:5001/api/content \
  -H "Content-Type: application/json" \
  -d '{"type":"youtube","raw_url":"https://www.youtube.com/watch?v=aircAruvnKk","title":"Test transcript"}')
echo $ITEM | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])"
```

Wait 90s then check:
```bash
docker logs knowbase-backend --since 2m 2>&1 | grep -E "transcript|chars|enrichment complete"
```
Expected: `YouTube transcript extracted  chars=NNNN` and `Content enrichment complete`.

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/webhooks.py backend/requirements.txt
git commit -m "feat: extract YouTube transcript for richer AI enrichment"
```

---

## Task 8: Stuck-items admin endpoint + n8n retry cron workflow

**Files:**
- Modify: `backend/app/api/admin.py`
- Create: `backend/app/workflows/retry_stuck_items.json`

- [ ] **Step 1: Add `GET /api/admin/stuck-items` endpoint**

Add to `backend/app/api/admin.py`:
```python
@admin_bp.get("/stuck-items")
def stuck_items():
    """Return pending items older than 10 minutes for retry."""
    from datetime import datetime, timezone, timedelta
    from app.models.content_item import ContentItem
    from app.core.db import db

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    items = ContentItem.query.filter(
        ContentItem.status.in_(["pending", "fetching"]),
        ContentItem.created_at < cutoff,
    ).all()

    return jsonify({
        "data": [
            {
                "id": item.id,
                "type": item.type,
                "raw_url": item.raw_url,
                "body": item.body,
                "status": item.status,
            }
            for item in items
        ],
        "error": None,
    })
```

- [ ] **Step 2: Test the endpoint**

```bash
curl -s http://localhost:5001/api/admin/stuck-items | python3 -m json.tool | head -20
```
Expected: JSON with a `data` array (may be empty if no stuck items).

- [ ] **Step 3: Create the n8n retry workflow JSON**

Create `backend/app/workflows/retry_stuck_items.json`:

```json
{
  "name": "Retry Stuck Items",
  "nodes": [
    {
      "parameters": {
        "rule": {
          "interval": [
            {
              "field": "cronExpression",
              "expression": "*/10 * * * *"
            }
          ]
        }
      },
      "id": "rs000001-0000-0000-0000-000000000001",
      "name": "Every 10 Minutes",
      "type": "n8n-nodes-base.scheduleTrigger",
      "typeVersion": 1.2,
      "position": [250, 300]
    },
    {
      "parameters": {
        "method": "GET",
        "url": "http://backend:5000/api/admin/stuck-items",
        "options": { "timeout": 10000 }
      },
      "id": "rs000002-0000-0000-0000-000000000002",
      "name": "Fetch Stuck Items",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [450, 300]
    },
    {
      "parameters": {
        "jsCode": "const resp = $input.first().json;\nconst items = (resp.data || []);\nif (items.length === 0) return [];\nreturn items.map(item => ({ json: item }));"
      },
      "id": "rs000003-0000-0000-0000-000000000003",
      "name": "Extract Items",
      "type": "n8n-nodes-base.code",
      "typeVersion": 2,
      "position": [650, 300]
    },
    {
      "parameters": {
        "method": "POST",
        "url": "=http://backend:5000/webhook/content-ingestion",
        "sendBody": true,
        "specifyBody": "json",
        "jsonBody": "={{ {content_item_id: $json.id, type: $json.type, raw_url: $json.raw_url, body: $json.body} }}",
        "options": { "timeout": 10000 }
      },
      "id": "rs000004-0000-0000-0000-000000000004",
      "name": "Re-trigger Ingestion",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4.2,
      "position": [850, 300]
    }
  ],
  "connections": {
    "Every 10 Minutes": { "main": [[{ "node": "Fetch Stuck Items", "type": "main", "index": 0 }]] },
    "Fetch Stuck Items": { "main": [[{ "node": "Extract Items", "type": "main", "index": 0 }]] },
    "Extract Items": { "main": [[{ "node": "Re-trigger Ingestion", "type": "main", "index": 0 }]] }
  },
  "settings": {
    "executionOrder": "v1",
    "saveDataErrorExecution": "all",
    "saveDataSuccessExecution": "none"
  }
}
```

**Note:** The Re-trigger Ingestion node POSTs to `http://backend:5000/webhook/content-ingestion` — this is the n8n webhook URL that the content ingestion workflow listens on, NOT the Flask `/api/webhooks/n8n` endpoint. The `n8n_client.trigger_ingestion` method pre-computes the HMAC and embeds it in the payload. But re-triggering from n8n directly to the webhook goes through the Content Ingestion n8n workflow which handles signing. 

**Wait** — re-triggering from n8n to `http://backend:5000` won't work because that goes to Flask directly but needs the `_pre_signature` computed by Flask's `trigger_ingestion`. Fix: call Flask's `/api/content/<id>/retry` instead, which is a new endpoint that triggers Flask to call n8n's webhook properly with HMAC pre-computed.

Revise: add a `/api/admin/retry-item/<item_id>` endpoint to admin.py instead:

```python
@admin_bp.post("/retry-item/<item_id>")
def retry_item(item_id: str):
    """Re-trigger n8n ingestion for a single stuck item."""
    from app.models.content_item import ContentItem
    from app.core.n8n_client import N8NClient

    item = ContentItem.query.get(item_id)
    if not item:
        return jsonify({"data": None, "error": {"code": "NOT_FOUND", "message": "Item not found"}}), 404

    item.status = "pending"
    from app.core.db import db
    db.session.commit()

    try:
        n8n = N8NClient(
            base_url=current_app.config["N8N_BASE_URL"],
            api_key=current_app.config["N8N_API_KEY"],
        )
        n8n.trigger_ingestion(
            {
                "content_item_id": item.id,
                "type": item.type,
                "raw_url": item.raw_url,
                "body": item.body,
            },
            webhook_secret=current_app.config.get("N8N_WEBHOOK_SECRET", ""),
        )
        return jsonify({"data": {"status": "re-triggered"}, "error": None})
    except Exception as e:
        logger.warning("Retry trigger failed", item_id=item_id, error=str(e))
        return jsonify({"data": None, "error": {"code": "TRIGGER_FAILED", "message": str(e)}}), 500
```

Update the n8n `Re-trigger Ingestion` node to call this endpoint instead:
```json
{
  "parameters": {
    "method": "POST",
    "url": "=http://backend:5000/api/admin/retry-item/{{ $json.id }}",
    "options": { "timeout": 10000 }
  },
  "id": "rs000004-0000-0000-0000-000000000004",
  "name": "Re-trigger Ingestion",
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.2,
  "position": [850, 300]
}
```

Rebuild the full `retry_stuck_items.json` with this correction applied (Replace Step 3 workflow JSON with the corrected version — change only the Re-trigger Ingestion node url to `=http://backend:5000/api/admin/retry-item/{{ $json.id }}`).

- [ ] **Step 4: Sync the new workflow to n8n**

```bash
curl -s -X POST http://localhost:5001/api/admin/sync-workflows | python3 -m json.tool
```
Expected: `"created": 1` (the new workflow) and remaining skipped.

- [ ] **Step 5: Verify workflow is active in n8n**

```bash
curl -s -H "X-N8N-API-KEY: $(grep N8N_API_KEY /Users/codeclouds-tanmoy/projects/Demo-AI-project/.env | cut -d= -f2-)" \
  "http://localhost:5678/api/v1/workflows" | python3 -c "
import sys,json; d=json.load(sys.stdin)
for w in d['data']: print(w['name'], '|', w['active'])
"
```
Expected: `Retry Stuck Items | True` in the list.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/admin.py backend/app/workflows/retry_stuck_items.json
git commit -m "feat: add stuck-items endpoint and 10-min retry cron workflow"
```

---

## Task 9: Frontend — extra_context and user_instructions fields

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/components/ContentSaveForm.tsx`

- [ ] **Step 1: Update TypeScript types**

In `frontend/src/types/index.ts`, update `ContentItem` and `CreateContentRequest`:

```typescript
export interface ContentItem {
  id: string;
  type: ContentType;
  raw_url: string | null;
  title: string | null;
  body: string | null;
  status: ContentStatus;
  extra_context: string | null;
  user_instructions: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateContentRequest {
  type: ContentType;
  raw_url?: string;
  title?: string;
  body?: string;
  extra_context?: string;
  user_instructions?: string;
}
```

- [ ] **Step 2: Add the two new fields to ContentSaveForm**

Add state variables after the existing ones in `ContentSaveForm.tsx`:
```typescript
const [extraContext, setExtraContext] = useState("");
const [userInstructions, setUserInstructions] = useState("");
```

Add them to the payload before submit:
```typescript
if (extraContext) payload.extra_context = extraContext;
if (userInstructions) payload.user_instructions = userInstructions;
```

Reset them on success:
```typescript
setExtraContext("");
setUserInstructions("");
```

Add the two form fields **after the title field and before the error message**:

```tsx
{/* Extra context */}
<div>
  <label htmlFor="extra_context" className="block text-xs text-gray-400 mb-1">
    Additional context <span className="text-gray-600">(optional)</span>
  </label>
  <textarea
    id="extra_context"
    value={extraContext}
    onChange={(e) => setExtraContext(e.target.value)}
    rows={2}
    placeholder="Any extra information about this content the AI should know..."
    className="w-full rounded-lg bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
  />
</div>

{/* User instructions */}
<div>
  <label htmlFor="user_instructions" className="block text-xs text-gray-400 mb-1">
    AI instructions <span className="text-gray-600">(optional)</span>
  </label>
  <textarea
    id="user_instructions"
    value={userInstructions}
    onChange={(e) => setUserInstructions(e.target.value)}
    rows={2}
    placeholder="What should the AI focus on? e.g. 'Focus on security implications' or 'Summarize for a beginner'"
    className="w-full rounded-lg bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
  />
</div>
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /Users/codeclouds-tanmoy/projects/Demo-AI-project/frontend && npx tsc --noEmit
```
Expected: no output (zero errors).

- [ ] **Step 4: Copy updated files to running container**

```bash
docker cp frontend/src/types/index.ts knowbase-frontend:/app/src/types/index.ts
docker cp frontend/src/components/ContentSaveForm.tsx knowbase-frontend:/app/src/components/ContentSaveForm.tsx
```

Wait 5s for hot-reload, then check:
```bash
docker logs knowbase-frontend --tail 3 2>&1
```
Expected: `✓ Compiled in ...`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/components/ContentSaveForm.tsx
git commit -m "feat: add extra_context and user_instructions fields to save form"
```

---

## Task 10: Integration test — full pipeline with transcript + new fields

- [ ] **Step 1: Save a YouTube item with custom instructions**

```bash
ITEM=$(curl -s -X POST http://localhost:5001/api/content \
  -H "Content-Type: application/json" \
  -d '{
    "type": "youtube",
    "raw_url": "https://www.youtube.com/watch?v=aircAruvnKk",
    "user_instructions": "Focus on the mathematical intuition behind neural networks. Explain for someone with basic calculus knowledge.",
    "extra_context": "3Blue1Brown is known for visual mathematical explanations"
  }')
ID=$(echo $ITEM | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")
echo "Item ID: $ID"
```

- [ ] **Step 2: Wait and check enrichment quality**

```bash
sleep 120
curl -s "http://localhost:5001/api/content/$ID" | python3 -c "
import sys, json
d = json.load(sys.stdin)
item = d.get('data') or {}
print('Status:', item.get('status'))
print('Title:', item.get('title'))
print('Tags:', [t.get('name') for t in item.get('tags', [])])
print()
print(item.get('summary', {}).get('text', '')[:600])
"
```
Expected: `status: enriched`, a descriptive title, and a summary that reflects the custom instruction (mathematical focus).

- [ ] **Step 3: Test stuck-item retry — manually create a stuck item**

```bash
# Insert a stuck item directly (1 hour old, pending)
docker exec knowbase-postgres psql -U knowbase -d knowbase -c "
INSERT INTO content_items (id, type, raw_url, title, status, created_at, updated_at)
VALUES ('stuck-test-1234', 'youtube', 'https://www.youtube.com/watch?v=aircAruvnKk', 'Stuck Test', 'pending', NOW() - INTERVAL '15 minutes', NOW() - INTERVAL '15 minutes');
"

# Check it appears in stuck-items endpoint
curl -s http://localhost:5001/api/admin/stuck-items | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('Stuck items:', len(d['data']))
for item in d['data']:
    print(' -', item['id'], item['status'])
"
```

Expected: `stuck-test-1234` appears in the list.

- [ ] **Step 4: Manually trigger the retry endpoint**

```bash
curl -s -X POST http://localhost:5001/api/admin/retry-item/stuck-test-1234 | python3 -m json.tool
```
Expected: `{"data": {"status": "re-triggered"}, "error": null}`

- [ ] **Step 5: Final commit and cleanup**

```bash
git add -A
git commit -m "feat: complete enrichment upgrades — transcript, title gen, context fields, stuck-item cron"
```
