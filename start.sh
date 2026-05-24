#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Knowbase — one-command startup
# Usage:  ./start.sh          (uses Ollama local AI by default)
#         ./start.sh openai   (uses OpenAI)
#         ./start.sh mistral  (uses Mistral)
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
CYAN="\033[36m"
RED="\033[31m"
RESET="\033[0m"

step()  { echo -e "\n${BOLD}${CYAN}▶ $1${RESET}"; }
ok()    { echo -e "${GREEN}✓ $1${RESET}"; }
warn()  { echo -e "${YELLOW}⚠ $1${RESET}"; }
die()   { echo -e "${RED}✗ $1${RESET}" >&2; exit 1; }

AI_PROVIDER="${1:-ollama}"

# ─────────────────────────────────────────────────────────────────────────────
# 1. Prerequisites
# ─────────────────────────────────────────────────────────────────────────────
step "Checking prerequisites"

command -v docker >/dev/null 2>&1 || die "Docker is not installed. Install Docker Desktop: https://www.docker.com/products/docker-desktop"
docker info >/dev/null 2>&1       || die "Docker daemon is not running. Start Docker Desktop and try again."
ok "Docker is running"

if [[ "$AI_PROVIDER" == "ollama" ]]; then
  if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    warn "Ollama is not running on localhost:11434."
    echo "  → Install Ollama: https://ollama.com"
    echo "  → Then run:  ollama pull llama3.2"
    echo "  → Start it and re-run this script, or use:  ./start.sh openai"
    echo ""
    read -rp "Continue anyway? (y/N): " cont
    [[ "${cont,,}" == "y" ]] || exit 1
  else
    ok "Ollama is running"
    # Pull model if missing
    OLLAMA_MODEL=$(grep OLLAMA_MODEL .env 2>/dev/null | cut -d= -f2 || echo "llama3.2")
    if ! curl -s http://localhost:11434/api/tags | grep -q "${OLLAMA_MODEL}"; then
      step "Pulling Ollama model: ${OLLAMA_MODEL}"
      ollama pull "${OLLAMA_MODEL}"
    else
      ok "Model ${OLLAMA_MODEL} already available"
    fi
  fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# 2. Environment file
# ─────────────────────────────────────────────────────────────────────────────
step "Checking environment configuration"

if [[ ! -f .env ]]; then
  cp .env.example .env
  warn ".env file created from .env.example"
  echo ""
  echo "  You must set these values in .env before continuing:"
  echo "  ┌─────────────────────────────────────────────────┐"
  echo "  │  SECRET_KEY        — any random string          │"
  echo "  │  POSTGRES_PASSWORD — database password          │"
  echo "  │  N8N_WEBHOOK_SECRET — any random string         │"
  echo "  │  N8N_ENCRYPTION_KEY — exactly 32 characters     │"
  if [[ "$AI_PROVIDER" == "openai" ]]; then
    echo "  │  OPENAI_API_KEY    — from platform.openai.com   │"
  elif [[ "$AI_PROVIDER" == "mistral" ]]; then
    echo "  │  MISTRAL_API_KEY   — from console.mistral.ai    │"
  fi
  echo "  └─────────────────────────────────────────────────┘"
  echo ""
  read -rp "Press Enter after editing .env to continue…"
fi

# Validate required vars
source_env() {
  set -a
  # shellcheck source=/dev/null
  source .env
  set +a
}
source_env

[[ -z "${SECRET_KEY:-}"         ]] && die "SECRET_KEY is not set in .env"
[[ -z "${POSTGRES_PASSWORD:-}"  ]] && die "POSTGRES_PASSWORD is not set in .env"
[[ -z "${N8N_WEBHOOK_SECRET:-}" ]] && die "N8N_WEBHOOK_SECRET is not set in .env"
[[ -z "${N8N_ENCRYPTION_KEY:-}" ]] && die "N8N_ENCRYPTION_KEY is not set in .env"

if [[ "$AI_PROVIDER" == "openai" && -z "${OPENAI_API_KEY:-}" ]]; then
  die "OPENAI_API_KEY is not set in .env (required for AI_PROVIDER=openai)"
fi
if [[ "$AI_PROVIDER" == "mistral" && -z "${MISTRAL_API_KEY:-}" ]]; then
  die "MISTRAL_API_KEY is not set in .env (required for AI_PROVIDER=mistral)"
fi

# Patch AI_PROVIDER in .env to match the argument
if [[ "$(grep -E '^AI_PROVIDER=' .env | cut -d= -f2)" != "$AI_PROVIDER" ]]; then
  sed -i.bak "s/^AI_PROVIDER=.*/AI_PROVIDER=${AI_PROVIDER}/" .env && rm -f .env.bak
  warn "AI_PROVIDER updated to ${AI_PROVIDER} in .env"
fi

ok "Environment looks good (AI provider: ${AI_PROVIDER})"

# ─────────────────────────────────────────────────────────────────────────────
# 3. Build and start containers
# ─────────────────────────────────────────────────────────────────────────────
step "Building and starting Docker services"

docker compose up -d --build

ok "Containers started"

# ─────────────────────────────────────────────────────────────────────────────
# 4. Wait for services to be healthy
# ─────────────────────────────────────────────────────────────────────────────
step "Waiting for services to be ready"

wait_healthy() {
  local service="$1"
  local max_wait="${2:-120}"
  local elapsed=0
  printf "  Waiting for %-20s" "${service}…"
  while ! docker compose ps "${service}" 2>/dev/null | grep -q "healthy"; do
    if [[ $elapsed -ge $max_wait ]]; then
      echo " TIMEOUT"
      die "${service} did not become healthy in ${max_wait}s. Run: docker compose logs ${service}"
    fi
    printf "."
    sleep 3
    elapsed=$((elapsed + 3))
  done
  echo " ready"
}

wait_healthy postgres  60
wait_healthy n8n       120
wait_healthy backend   120

ok "All core services are healthy"

# ─────────────────────────────────────────────────────────────────────────────
# 5. Run database migrations
# ─────────────────────────────────────────────────────────────────────────────
step "Running database migrations"

docker compose exec -T backend alembic upgrade head
ok "Database schema is up to date"

# ─────────────────────────────────────────────────────────────────────────────
# 6. n8n setup
# ─────────────────────────────────────────────────────────────────────────────
step "Checking n8n configuration"

N8N_API_KEY="${N8N_API_KEY:-}"

if [[ -z "$N8N_API_KEY" ]]; then
  echo ""
  echo -e "${YELLOW}  n8n needs a one-time manual setup (first run only):${RESET}"
  echo "  ┌──────────────────────────────────────────────────────────────┐"
  echo "  │  1. Open  http://localhost:5678                             │"
  echo "  │  2. Create an admin account                                │"
  echo "  │  3. Go to Settings → API → Create API Key                 │"
  echo "  │  4. Copy the key and paste it below                       │"
  echo "  └──────────────────────────────────────────────────────────────┘"
  echo ""
  read -rp "  Paste your n8n API key (or press Enter to skip for now): " NEW_KEY
  if [[ -n "$NEW_KEY" ]]; then
    sed -i.bak "s|^N8N_API_KEY=.*|N8N_API_KEY=${NEW_KEY}|" .env && rm -f .env.bak
    N8N_API_KEY="$NEW_KEY"
    ok "API key saved to .env"
  else
    warn "Skipped — workflows won't be synced yet. Re-run ./start.sh after adding N8N_API_KEY to .env"
  fi
fi

if [[ -n "$N8N_API_KEY" ]]; then
  step "Syncing n8n workflows"
  if curl -s -o /dev/null -w "%{http_code}" \
      -H "X-N8N-API-KEY: ${N8N_API_KEY}" \
      "http://localhost:5678/api/v1/workflows" | grep -q "^2"; then
    # Restart backend so it picks up the key and runs startup sync
    docker compose restart backend >/dev/null 2>&1
    # Wait for it to come back
    sleep 8
    SYNC_RESULT=$(curl -s -X POST http://localhost:5001/api/admin/sync-workflows)
    CREATED=$(echo "$SYNC_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('created',0))" 2>/dev/null || echo "?")
    ok "Workflows synced (${CREATED} created)"
  else
    warn "n8n API key invalid — workflows not synced. Check N8N_API_KEY in .env"
  fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# 7. Done — print access URLs
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${BOLD}${GREEN}  Knowbase is ready!${RESET}"
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo -e "  ${BOLD}App${RESET}          →  ${CYAN}http://localhost:3000${RESET}"
echo -e "  ${BOLD}API${RESET}          →  ${CYAN}http://localhost:5001${RESET}"
echo -e "  ${BOLD}n8n editor${RESET}   →  ${CYAN}http://localhost:5678${RESET}"
echo -e "  ${BOLD}Email viewer${RESET} →  ${CYAN}http://localhost:8025${RESET}"
echo ""
echo -e "  ${BOLD}AI provider:${RESET} ${AI_PROVIDER}"
echo ""
echo -e "  Useful commands:"
echo -e "  ${CYAN}make logs${RESET}          — tail all logs"
echo -e "  ${CYAN}make logs-backend${RESET}  — backend logs only"
echo -e "  ${CYAN}make down${RESET}          — stop everything"
echo -e "  ${CYAN}make shell-db${RESET}      — open Postgres shell"
echo ""

# Open browser if possible
if command -v open >/dev/null 2>&1; then
  open http://localhost:3000
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open http://localhost:3000
fi
