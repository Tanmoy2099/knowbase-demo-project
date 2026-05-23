# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered personal knowledge base. Users save links, notes, PDFs, and YouTube URLs. Flask handles all AI orchestration (summarization, tagging, collection assignment via a factory pattern). n8n handles external content fetching and scheduled jobs. The full stack runs locally via Docker Compose.

## Commands

### Docker (primary workflow)
```bash
make up              # start all services
make up-ollama       # include Ollama for local AI
make down            # stop all services
make logs            # tail all logs
make logs-backend    # tail backend only
make migrate         # run Alembic migrations
make migrate-create name="add_column"   # create new migration
make sync-workflows  # manually sync n8n workflows
```

### Backend tests
```bash
make test-backend          # all backend tests
make test-backend-unit     # unit tests only
make test-backend-int      # integration tests only
# or directly:
cd backend && pytest tests/ -v
cd backend && pytest tests/unit/test_ai_factory.py -v
```

### Frontend tests
```bash
make test-frontend         # Vitest unit tests
make test-e2e              # Playwright E2E tests
# or directly:
cd frontend && npm run test
cd frontend && npx playwright test
```

### Shell access
```bash
make shell-backend   # bash into Flask container
make shell-frontend  # sh into Next.js container
make shell-db        # psql into Postgres
```

## Architecture

### Data flow (content save)
1. Next.js `POST /api/content` → Flask validates & saves item (`status: pending`)
2. Flask calls n8n REST API → triggers ingestion workflow
3. n8n fetches external content (scrape/PDF/YouTube oEmbed)
4. n8n signs payload with HMAC-SHA256, POSTs to `POST /api/webhooks/n8n`
5. Flask verifies signature, runs AI enrichment pipeline (summarize → tag → collection)
6. Flask updates item to `status: enriched`; frontend polls every 3s until settled

### AI provider factory
`backend/app/ai/factory.py` — `get_provider(config)` returns the correct `AIProvider` subclass based on `AI_PROVIDER` env var. All three providers (`OpenAIProvider`, `MistralProvider`, `OllamaProvider`) implement the same ABC: `summarize()`, `extract_tags()`, `suggest_collection()`, and the composite `enrich()`.

To add a new provider: implement `AIProvider` ABC in `backend/app/ai/providers/`, register it in `_REGISTRY` in `factory.py`.

### Workflow sync (idempotent)
On every Flask startup, `WorkflowSyncService.sync()` reads all `*.json` files from `backend/app/workflows/`, computes SHA-256 hashes, compares against `workflow_sync` table, and creates/updates/skips via n8n REST API. Safe to re-run — no duplicate imports. Adding a workflow: drop a JSON file in `backend/app/workflows/`, restart Flask.

### n8n → Flask security
All n8n webhook callbacks are HMAC-SHA256 signed (shared secret in `N8N_WEBHOOK_SECRET` env var). Flask validates via `@require_n8n_signature` decorator in `backend/app/core/security.py`. Unsigned requests → 401.

### Database
All models use string UUID PKs generated server-side. `TimestampMixin` provides `created_at`/`updated_at`. Alembic handles migrations — never edit migration files after they've been run. Run `make migrate-create` to generate a new one from model changes.

## Key files

| File | Purpose |
|---|---|
| `backend/app/__init__.py` | App factory — wires all extensions, blueprints, startup sync |
| `backend/app/core/config.py` | `Config` dataclass — validates required env vars at startup |
| `backend/app/ai/factory.py` | Provider registry — add new AI providers here |
| `backend/app/services/sync_service.py` | Workflow sync logic — hash comparison and n8n API calls |
| `backend/app/core/security.py` | HMAC validation + Flask-Talisman security headers |
| `backend/app/workflows/*.json` | n8n workflow definitions (source of truth) |
| `frontend/src/lib/api.ts` | Typed API client — all backend calls go through here |
| `frontend/src/hooks/useContent.ts` | Content list + detail hooks with 3s polling |

## Environment variables

Copy `.env.example` to `.env` before running. Required vars (app won't start without them):
- `SECRET_KEY` — Flask session secret
- `POSTGRES_PASSWORD` — database password
- `N8N_WEBHOOK_SECRET` — HMAC shared secret for n8n callbacks
- `N8N_ENCRYPTION_KEY` — n8n internal encryption (32 chars)

AI provider vars (set the relevant ones for your chosen `AI_PROVIDER`):
- `OPENAI_API_KEY` — for `AI_PROVIDER=openai`
- `MISTRAL_API_KEY` — for `AI_PROVIDER=mistral`
- `OLLAMA_BASE_URL` — for `AI_PROVIDER=ollama` (default: `http://ollama:11434`)

## Branching rules

Every feature gets its own `feature/<name>` branch. Merges to `main` only after all relevant tests pass (pytest + Vitest + applicable Playwright tests). No direct commits to `main`.

## Testing notes

- Backend tests use `Config.for_testing()` → SQLite in-memory, no Postgres needed
- All external calls (OpenAI, Mistral, n8n) are mocked in unit tests
- `clean_db` fixture in `conftest.py` truncates all tables between tests
- Playwright tests mock API routes — they run without a live backend
