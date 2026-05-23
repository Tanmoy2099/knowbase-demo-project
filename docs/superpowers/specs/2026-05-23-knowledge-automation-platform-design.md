# AI-Powered Knowledge Automation Platform — Design Spec

**Date:** 2026-05-23  
**Status:** Approved

---

## Overview

A production-grade, single-user personal knowledge base. Users save links, notes, PDFs, and YouTube URLs. AI automatically organizes content into collections and tags, generates summaries, and builds topic relationships. n8n handles workflow automation for content fetching and scheduled maintenance. The entire stack runs locally via Docker Compose.

---

## 1. System Architecture

### Services

| Service    | Port  | Role                                      |
|------------|-------|-------------------------------------------|
| `frontend` | 3000  | Next.js (TypeScript, App Router)          |
| `backend`  | 5000  | Flask (Python, gunicorn in production)    |
| `postgres` | 5432  | Primary data store (PostgreSQL 16)        |
| `n8n`      | 5678  | Workflow automation                       |
| `ollama`   | 11434 | Local AI — optional Docker profile       |

### Data Flow — Content Save

1. User submits link / note / PDF / YouTube URL via Next.js UI
2. `POST /api/content` → Flask validates input, saves raw item to Postgres (`status: pending`), returns item ID immediately
3. Flask calls n8n REST API to trigger the ingestion workflow
4. n8n fetches external content (webpage scrape, PDF download, YouTube transcript)
5. n8n calls back `POST /api/webhooks/n8n` with raw content + HMAC-SHA256 signature
6. Flask verifies signature, runs AI pipeline: summarize → extract tags → assign collection
7. Flask updates Postgres (`status: enriched`); frontend reflects update via polling or SSE

### AI Provider Factory

```
AIProvider (ABC)
  ├── OpenAIProvider    — GPT-4o / GPT-4o-mini
  ├── MistralProvider   — mistral-large / mistral-small
  └── OllamaProvider    — any locally pulled model

get_provider(config) → selected via AI_PROVIDER env var
```

Provider is selected at startup. Swapping providers requires only an env var change — no code changes.

---

## 2. Folder Structure

```
/
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js App Router pages and layouts
│   │   ├── components/       # Reusable UI components
│   │   ├── hooks/            # Custom React hooks
│   │   ├── lib/              # Typed API client, utilities
│   │   └── types/            # Shared TypeScript types
│   ├── tests/
│   │   ├── unit/             # Vitest
│   │   └── e2e/              # Playwright
│   ├── next.config.ts
│   └── package.json
│
├── backend/
│   ├── app/
│   │   ├── api/              # Flask blueprints: content, collections, tags, webhooks, admin
│   │   ├── ai/               # AIProvider ABC + OpenAI, Mistral, Ollama implementations
│   │   ├── services/         # Business logic: content_service, ai_service, sync_service
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── workflows/        # n8n workflow JSON definitions (versioned source of truth)
│   │   └── core/             # Config, DB init, security middleware, HMAC utils
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   ├── migrations/           # Alembic migrations
│   ├── requirements.txt
│   └── pyproject.toml        # pytest config, ruff, mypy
│
├── docker-compose.yml
├── docker-compose.override.yml   # dev: hot-reload, exposed debug ports
└── .env.example
```

---

## 3. Service Responsibilities

### Flask Backend
- Owns all business logic and AI prompt orchestration
- Validates and persists all user input
- Triggers n8n workflows via n8n REST API
- Verifies HMAC signatures on all inbound n8n webhook calls
- Runs workflow sync on startup
- Exposes REST API consumed by Next.js frontend

### Next.js Frontend
- Renders UI: save form, content list, collection/tag views
- Communicates with Flask via typed API client in `lib/`
- Polls or uses SSE to reflect enrichment status updates
- No business logic — thin client

### n8n
- Triggered by Flask on content save events
- Handles all external I/O: HTTP scraping, PDF fetch, YouTube transcript API
- Fires scheduled maintenance workflows (re-indexing, relationship graph updates)
- Calls back to Flask webhook with results; never writes to Postgres directly

### PostgreSQL
- Single source of truth for all data
- Accessed only by Flask (never directly by n8n or frontend)

### Ollama (optional)
- Runs local LLM inference when `AI_PROVIDER=ollama`
- Activated via `docker compose --profile ollama up`

---

## 4. Database Schema

```sql
-- Core content
content_items (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  type          VARCHAR(20) NOT NULL,   -- link | note | pdf | youtube
  raw_url       TEXT,
  title         TEXT,
  body          TEXT,
  status        VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending | fetching | enriched | failed
  created_at    TIMESTAMPTZ DEFAULT now(),
  updated_at    TIMESTAMPTZ DEFAULT now()
)

-- AI-generated summaries
summaries (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content_item_id UUID NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
  text            TEXT NOT NULL,
  ai_provider     VARCHAR(50),
  model           VARCHAR(100),
  created_at      TIMESTAMPTZ DEFAULT now()
)

-- Taxonomy
tags (
  id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name  TEXT NOT NULL UNIQUE,
  slug  TEXT NOT NULL UNIQUE
)

content_tags (
  content_item_id UUID REFERENCES content_items(id) ON DELETE CASCADE,
  tag_id          UUID REFERENCES tags(id) ON DELETE CASCADE,
  PRIMARY KEY (content_item_id, tag_id)
)

collections (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name          TEXT NOT NULL UNIQUE,
  slug          TEXT NOT NULL UNIQUE,
  description   TEXT,
  ai_suggested  BOOLEAN DEFAULT false,
  created_at    TIMESTAMPTZ DEFAULT now()
)

collection_items (
  collection_id   UUID REFERENCES collections(id) ON DELETE CASCADE,
  content_item_id UUID REFERENCES content_items(id) ON DELETE CASCADE,
  PRIMARY KEY (collection_id, content_item_id)
)

-- Topic relationship graph
topic_relations (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id     UUID NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
  target_id     UUID NOT NULL REFERENCES content_items(id) ON DELETE CASCADE,
  relation_type VARCHAR(50),              -- related | prerequisite | contradicts | extends
  strength      FLOAT CHECK (strength BETWEEN 0 AND 1),
  created_at    TIMESTAMPTZ DEFAULT now()
)

-- Workflow sync state
workflow_sync (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workflow_name    TEXT NOT NULL UNIQUE,
  n8n_workflow_id  TEXT,
  hash             TEXT NOT NULL,          -- SHA-256 of workflow JSON
  last_synced_at   TIMESTAMPTZ DEFAULT now()
)
```

---

## 5. Workflow Sync Strategy

Workflow JSON definitions live in `backend/app/workflows/` and are the source of truth. On every Flask startup, `sync_service.sync_workflows()` runs:

1. Read all `*.json` files from the workflows directory
2. Compute SHA-256 hash of each file's content
3. Load all rows from `workflow_sync` table
4. For each workflow file:
   - **Hash unchanged** → skip (no n8n API call)
   - **Hash changed** → `PUT /api/v1/workflows/{n8n_workflow_id}` → update `workflow_sync` row
   - **New file** → `POST /api/v1/workflows` → insert `workflow_sync` row with returned ID
5. Log all sync actions; treat n8n API failures as startup warnings, not fatal errors

**Idempotency guarantee:** The same workflow file always produces the same hash. Re-running sync on an unchanged file is always a no-op.

**HMAC validation:** n8n signs all webhook POST bodies with `HMAC-SHA256` using a shared secret (`N8N_WEBHOOK_SECRET` env var). Flask rejects any webhook call with a missing or invalid `X-N8N-Signature` header with `401`.

---

## 6. API Design

### Content
```
POST   /api/content              Save item; triggers n8n ingestion workflow; returns item ID + status
GET    /api/content              List items (filters: tag, collection, type, q, status; pagination)
GET    /api/content/:id          Item detail: body + summary + tags + collections + related items
PATCH  /api/content/:id          Update title; override AI-assigned tags or collection
DELETE /api/content/:id
```

### Collections
```
GET    /api/collections          List all collections with item counts
POST   /api/collections          Create manually
PATCH  /api/collections/:id      Rename or update description
DELETE /api/collections/:id
```

### Tags
```
GET    /api/tags                 List all tags with item counts
```

### Webhooks
```
POST   /api/webhooks/n8n         Receive enriched content from n8n (HMAC-verified)
```

### Admin
```
POST   /api/admin/sync-workflows  Manually re-trigger workflow sync
GET    /api/admin/health          Returns status of DB connection, n8n connectivity, AI provider
```

### Request/Response
- All request bodies validated with **Pydantic v2** models; invalid input returns `422` with field-level errors
- All responses use a consistent envelope: `{ data, meta, error }`
- Pagination via `?page=1&per_page=20` on list endpoints

---

## 7. Security Design

| Layer | Mechanism |
|---|---|
| HTTP headers | Flask-Talisman: HSTS, CSP, X-Frame-Options, X-Content-Type-Options |
| Rate limiting | Flask-Limiter: 60 req/min general; 10 req/min on `POST /api/content` |
| Input validation | Pydantic v2 strict models on all request bodies |
| SQL | SQLAlchemy ORM exclusively — zero raw SQL |
| CORS | Only `http://localhost:3000` allowed |
| Webhook auth | HMAC-SHA256 on all n8n→Flask calls; reject unsigned requests |
| File uploads | MIME type validation (not extension-only); 50MB limit; stored outside webroot |
| Secrets | Loaded via `python-dotenv`; validated at startup — missing required keys raise `ImproperlyConfigured` and halt boot |
| Database user | Runtime Postgres user has `SELECT`, `INSERT`, `UPDATE`, `DELETE` only — no `CREATE`, `DROP`, `ALTER` |

---

## 8. Testing Strategy

### Backend — pytest

**Unit tests** (`backend/tests/unit/`):
- AI provider implementations with mocked HTTP clients — assert on prompt structure, parsed output types
- Workflow sync hash-diffing logic — new / changed / unchanged scenarios
- HMAC signature validation logic
- Pydantic model validation edge cases

**Integration tests** (`backend/tests/integration/`):
- Full API route tests against a real PostgreSQL instance via `testcontainers-python`
- Content save → status transitions
- Webhook ingestion pipeline end-to-end (Flask only, n8n mocked)

### Frontend — Vitest

**Unit tests** (`frontend/tests/unit/`):
- Component rendering with mock data
- Custom hooks (content list state, tag/collection filter state)
- Typed API client: request construction, error handling

### E2E — Playwright

**Scenarios** (`frontend/tests/e2e/`):
- Save a link → content appears with `enriched` status, summary and tags visible
- Save a YouTube URL → transcript fetched, summary generated
- AI-suggested collection auto-assigned; user can override
- Manual tag override persists across page refresh
- Admin health endpoint returns healthy status

---

## 9. Docker Architecture

```yaml
# docker-compose.yml
services:
  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:5000
    depends_on: [backend]
    networks: [knowbase-net]

  backend:
    build: ./backend
    ports: ["5000:5000"]
    env_file: .env
    depends_on:
      postgres: { condition: service_healthy }
      n8n:      { condition: service_healthy }
    networks: [knowbase-net]

  postgres:
    image: postgres:16-alpine
    ports: ["5432:5432"]
    volumes: [postgres-data:/var/lib/postgresql/data]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $POSTGRES_USER"]
    networks: [knowbase-net]

  n8n:
    image: n8nio/n8n:latest
    ports: ["5678:5678"]
    volumes: [n8n-data:/home/node/.n8n]
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:5678/healthz"]
    networks: [knowbase-net]

  ollama:
    image: ollama/ollama:latest
    ports: ["11434:11434"]
    volumes: [ollama-data:/root/.ollama]
    profiles: [ollama]
    networks: [knowbase-net]

networks:
  knowbase-net:

volumes:
  postgres-data:
  n8n-data:
  ollama-data:
```

`docker-compose.override.yml` adds hot-reload mounts and debug env vars for local development. Never committed with real secrets.

---

## 10. Git Branching Strategy

- `main` is always production-ready and passing
- Every feature from the implementation order gets its own branch: `feature/<name>`
  - Examples: `feature/docker-skeleton`, `feature/ai-factory`, `feature/content-api`
- A branch merges to `main` only when:
  - All pytest tests pass
  - All Vitest tests pass
  - All Playwright E2E tests relevant to that feature pass
- No direct commits to `main`

---

## 11. Environment Variable Strategy

All secrets and config live in `.env` (never committed). `.env.example` is committed with placeholder values.

```bash
# AI Provider
AI_PROVIDER=openai              # openai | mistral | ollama
OPENAI_API_KEY=
MISTRAL_API_KEY=
OLLAMA_BASE_URL=http://ollama:11434

# Database
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=knowbase
POSTGRES_USER=knowbase
POSTGRES_PASSWORD=

# n8n
N8N_BASE_URL=http://n8n:5678
N8N_API_KEY=
N8N_WEBHOOK_SECRET=             # HMAC shared secret for webhook verification

# Flask
FLASK_ENV=development           # development | production
SECRET_KEY=                     # Flask session secret
CORS_ORIGIN=http://localhost:3000
```

Flask validates all required vars at startup and raises `ImproperlyConfigured` with the missing key name before accepting any requests.

---

## 12. Implementation Order

| Step | Branch | Scope |
|---|---|---|
| 1 | `feature/docker-skeleton` | Docker Compose, all services, health checks, `.env.example` |
| 2 | `feature/flask-scaffold` | Flask app structure, blueprints, config, DB init, Alembic setup |
| 3 | `feature/db-models` | SQLAlchemy models, initial Alembic migration |
| 4 | `feature/ai-factory` | AIProvider ABC, all three providers, unit tests |
| 5 | `feature/content-api` | Content CRUD endpoints, Pydantic validation, pytest integration tests |
| 6 | `feature/workflow-sync` | n8n workflow JSON definitions, startup sync mechanism, unit tests |
| 7 | `feature/n8n-pipeline` | n8n workflows, Flask webhook, full ingestion pipeline |
| 8 | `feature/frontend` | Next.js save form, content list, collection/tag views, Vitest unit tests |
| 9 | `feature/e2e-tests` | Playwright E2E scenarios wired into Docker Compose test profile |
