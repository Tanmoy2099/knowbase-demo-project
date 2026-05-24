.PHONY: start start-openai start-mistral clean \
        up up-ollama down down-v build rebuild logs logs-backend logs-frontend \
        ps shell-backend shell-frontend shell-db migrate migrate-create \
        test test-backend test-backend-unit test-backend-int test-frontend \
        test-e2e sync-workflows help

# ─────────────────────────────────────────────────────────────────────────────
# One-command startup
# ─────────────────────────────────────────────────────────────────────────────

start: ## Full setup and start using local Ollama (default)
	@bash start.sh ollama

start-openai: ## Full setup and start using OpenAI
	@bash start.sh openai

start-mistral: ## Full setup and start using Mistral
	@bash start.sh mistral

clean: ## Remove all containers, volumes, images, node_modules, and build artifacts
	docker compose down -v --remove-orphans 2>/dev/null || true
	docker images --format "{{.Repository}} {{.ID}}" | grep -E "knowbase|demo-ai-project" | awk '{print $$2}' | xargs -r docker rmi -f 2>/dev/null || true
	docker image prune -f 2>/dev/null || true
	rm -rf frontend/node_modules frontend/.next frontend/tsconfig.tsbuildinfo
	find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find backend -name "*.pyc" -delete 2>/dev/null || true
	rm -rf data/postgres data/n8n data/mailpit
	@echo "✓ Cleaned up everything"

# ─────────────────────────────────────────────────────────────────────────────
# Container lifecycle
# ─────────────────────────────────────────────────────────────────────────────

up: ## Start all services in the background (development mode)
	docker compose up -d

up-ollama: ## Start all services including the Ollama LLM runtime
	docker compose --profile ollama up -d

down: ## Stop and remove containers (volumes are preserved)
	docker compose down

down-v: ## Stop and remove containers AND all named volumes (destructive)
	docker compose down -v

build: ## Build (or rebuild) all images without using the cache
	docker compose build --no-cache

rebuild: ## Full stop → rebuild → start cycle
	$(MAKE) down && $(MAKE) build && $(MAKE) up

# ─────────────────────────────────────────────────────────────────────────────
# Observability
# ─────────────────────────────────────────────────────────────────────────────

logs: ## Tail logs for all services
	docker compose logs -f

logs-backend: ## Tail logs for the backend service only
	docker compose logs -f backend

logs-frontend: ## Tail logs for the frontend service only
	docker compose logs -f frontend

ps: ## Show status of all running containers
	docker compose ps

# ─────────────────────────────────────────────────────────────────────────────
# Interactive shells
# ─────────────────────────────────────────────────────────────────────────────

shell-backend: ## Open a bash shell inside the backend container
	docker compose exec backend bash

shell-frontend: ## Open a sh shell inside the frontend container
	docker compose exec frontend sh

shell-db: ## Open a psql shell connected to the knowbase database
	docker compose exec postgres psql -U $${POSTGRES_USER:-knowbase} -d $${POSTGRES_DB:-knowbase}

# ─────────────────────────────────────────────────────────────────────────────
# Database migrations (Alembic)
# ─────────────────────────────────────────────────────────────────────────────

migrate: ## Apply all pending Alembic migrations
	docker compose exec backend alembic upgrade head

migrate-create: ## Create a new Alembic revision (usage: make migrate-create name="add users table")
	docker compose exec backend alembic revision --autogenerate -m "$(name)"

# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

test: ## Run the full test suite (backend + frontend)
	$(MAKE) test-backend && $(MAKE) test-frontend

test-backend: ## Run all backend tests with verbose output
	docker compose exec backend pytest tests/ -v

test-backend-unit: ## Run backend unit tests only
	docker compose exec backend pytest tests/unit/ -v

test-backend-int: ## Run backend integration tests only
	docker compose exec backend pytest tests/integration/ -v

test-frontend: ## Run frontend Jest/Vitest test suite
	docker compose exec frontend npm run test

test-e2e: ## Run Playwright end-to-end tests
	docker compose exec frontend npx playwright test

# ─────────────────────────────────────────────────────────────────────────────
# n8n workflow utilities
# ─────────────────────────────────────────────────────────────────────────────

sync-workflows: ## Sync n8n workflows via WorkflowSyncService
	docker compose exec backend python -c "from app import create_app; app = create_app(); \
	    from app.services.sync_service import WorkflowSyncService; \
	    with app.app_context(): WorkflowSyncService().sync()"

# ─────────────────────────────────────────────────────────────────────────────
# Help
# ─────────────────────────────────────────────────────────────────────────────

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
