# Matcha Bot

A drink-recipe (tea, matcha, etc.) consulting chatbot for a shop, served over Telegram, plus an admin dashboard for running and monitoring it.

## Key features

- **RAG chatbot on Telegram**: a LangGraph agent (`fetch_history → retrieve → generate`, `app/agent/graph.py`) answers customers via OpenAI, grounding responses on uploaded recipe documents retrieved from a Chroma vector DB — never invents a drink/ingredient outside those documents (`backend/SOUL.md` defines the bot's personality and tone). Replies stream token-by-token as progressive edits to a "thinking..." placeholder message (`app/routers/webhook.py`), and a favourite-drink is inferred and saved in the background after each reply (`extract_favourite`).
- **Multi-channel, poll-based**: `ChannelManager` reconciles one long-polling task per active Telegram channel (`app/channel_manager.py`, `app/telegram_poller.py`) — no inbound HTTP webhook is exposed. Each channel's bot token is encrypted with AES-GCM (`app/crypto.py`) before being stored.
- **React admin SPA**:
  - Channels: create/edit/delete, test connection (checks the token still works), force-delete a channel that still has users attached (with a type-to-confirm modal).
  - Docs: upload/list/delete the recipe documents that back the bot's knowledge base.
  - Users: list/block/unblock users per channel.
  - Access log & Audit log: access history and admin action history (filter by action, search, danger badges).
  - Usage: token usage tracking (chart by model) for OpenAI calls.
- **Switchable LLM provider**: a Settings page selects OpenAI or any OpenAI-compatible endpoint (Ollama) and the chat model, stored encrypted in the database and effective without a restart (`app/llm_settings.py`, `app/routers/admin_llm_settings.py`). Embeddings stay on OpenAI's `text-embedding-3-small`, because the Chroma index depends on it.
- **Auth**: Basic Auth for the admin dashboard (`ADMIN_USERNAME` / `ADMIN_PASSWORD`).

## Architecture / stack

System diagram: [`docs/architecture-diagram.html`](docs/architecture-diagram.html) (animated, open in browser) / [`docs/architecture-diagram.svg`](docs/architecture-diagram.svg) (static image).

![Matcha Bot architecture](docs/architecture-diagram.svg)

| Layer | Tech |
|---|---|
| Backend | FastAPI, SQLAlchemy + Alembic, LangGraph (agent graph: fetch_history → retrieve → generate → extract_favourite) |
| Vector DB | ChromaDB |
| LLM | OpenAI API |
| Database | SQLite (default) / PostgreSQL supported via `DATABASE_URL` |
| Frontend | React + TypeScript + Vite, Tailwind CSS, React Router |
| Telegram | Per-channel long-polling (`telegram_poller.py`, `telegram_client.py`) |
| Infra | Docker Compose (backend + frontend), Terraform (single EC2), GitHub Actions CI/CD |
| Monitoring | Prometheus, Grafana, node_exporter, cadvisor |

### Project layout

```
backend/
  app/
    agent/                 # LangGraph nodes: fetch_history, retrieve, generate, extract_favourite
    routers/                # HTTP routers: admin_channels, admin_docs, admin_logs, admin_usage, admin_users, health
    routers/webhook.py       # NOT an HTTP route — message-processing pipeline called by telegram_poller.py
    routers/admin_llm_settings.py  # GET/PUT /admin/llm-settings, POST /admin/llm-settings/test
    routers/metrics.py       # GET /metrics — Prometheus scrape endpoint (no auth, not exposed by nginx)
    db/                      # SQLAlchemy models (Channel, User, Message, Favourite, Document, AdminAuditLog, TokenUsage) + session
    channel_manager.py    # spawns/reconciles one long-poll task per active Telegram channel
    telegram_poller.py    # per-channel long-poll loop (get_updates)
    telegram_client.py    # Telegram Bot API HTTP calls
    ingestion.py           # chunk + embed uploaded docs into Chroma
    crypto.py              # token/credential encryption (AES-GCM)
    retry.py                # single-retry wrapper used around LLM/embedding calls
    token_usage.py         # persists per-call token counts
    llm_settings.py        # active chat provider/model: DB-backed, env fallback, encrypted key
    metrics.py             # Prometheus collectors: tokens, cost, node latency, Telegram traffic
    config.py               # settings (env)
  SOUL.md            # bot personality / tone
  migrations/        # Alembic
frontend/
  src/               # React SPA: api, auth, channels, docs, users, logs, usage, welcome, layout
infra/               # Terraform: EC2, security group, Elastic IP, SSM secrets (see infra/README.md)
monitoring/          # Prometheus scrape config + alert rules, provisioned Grafana dashboard
docs/                # architecture diagram + design specs/plans (see below)
sample-recipes/      # sample recipes for testing ingestion/RAG
docker-compose.yml       # local development (builds from source)
docker-compose.prod.yml  # production stack on EC2 (GHCR images + monitoring)
```

## Deployment

The production stack runs on a single EC2 instance provisioned by Terraform.
See [`infra/README.md`](infra/README.md) for bootstrap, rollback, and routine
operations. Deploys are manual: run the `Deploy` workflow from the Actions tab.

The backend exports Prometheus metrics at `/metrics` — token counts, estimated
cost per model, per-node agent latency, retrieved chunk counts, and Telegram
traffic — scraped alongside host and container metrics and rendered by a
provisioned Grafana dashboard on port 3000. The endpoint is unauthenticated but
not published outside the Docker network.

## Running the project

### Docker Compose (recommended)

Copy `backend/.env.example` to `backend/.env` and fill in real values (see the environment variables table below), then:

```bash
docker compose up --build
```

- Backend: http://localhost:8000
- Admin frontend: http://localhost:80

### Running manually

**Backend**
```bash
cd backend
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

**Frontend**
```bash
cd frontend
npm install
npm run dev
```

## Admin API

All routes below require HTTP Basic Auth (`app/auth.py`, `require_admin`), except `/health` and `/admin/login`.

| Method | Path | Purpose |
|---|---|---|
| POST | `/admin/login` | Validate admin credentials (frontend login) |
| GET/POST | `/admin/channels` | List / create a Telegram channel |
| POST | `/admin/channels/test` | Test a bot token before saving |
| GET/PUT | `/admin/llm-settings` | Read / update the active LLM provider and chat model |
| POST | `/admin/llm-settings/test` | Test a provider configuration before saving |
| PATCH | `/admin/channels/{id}` | Update a channel |
| POST | `/admin/channels/{id}/test` | Test a saved channel's token |
| DELETE | `/admin/channels/{id}` | Delete a channel (`?force=true` if it still has users) |
| GET/POST | `/admin/docs` | List / upload a knowledge-base document (chunked + embedded into Chroma) |
| DELETE | `/admin/docs/{id}` | Delete a document and its chunks |
| GET | `/admin/users` | List users (message count, favourites) |
| POST | `/admin/users/{id}/block` \| `/unblock` | Block / unblock a user |
| GET | `/admin/logs/access` | Paginated chat message log |
| GET | `/admin/logs/audit` | Paginated admin action log (filter by action / search) |
| GET | `/admin/logs/audit/actions` | Distinct audit action names |
| DELETE | `/admin/logs/audit/{id}` \| `/admin/logs/audit` | Delete one / clear all audit entries |
| GET | `/admin/usage` \| `/admin/usage/summary` | Token usage rows / per-model cost totals |
| DELETE | `/admin/usage/{id}` \| `/admin/usage` | Delete one / clear all usage rows |
| GET | `/health` | Liveness check (no auth) |

**Data model** (`app/db/models.py`): `Channel` → `User` → `Message` / `Favourite`, plus standalone `Document`, `AdminAuditLog`, `TokenUsage`.

**Frontend routes** (`frontend/src/App.tsx`): `/` (public landing), `/login`, and `/panel/*` (auth-gated): `usage` (default), `docs`, `users`, `logs/access`, `logs/audit`, `channels`.

## CI/CD

GitHub Actions (`.github/workflows/deploy.yml`) runs on every push to `main`:

1. **test** — installs backend deps, runs `pytest` (with dummy `OPENAI_API_KEY`/`ENCRYPTION_KEY`), then installs frontend deps and runs `npm run build` (typecheck + build).
2. **build-and-push** (needs `test` to pass) — builds the `backend` and `frontend` Docker images and pushes both to GHCR (`ghcr.io/<repo>-backend`, `ghcr.io/<repo>-frontend`), tagged `latest` and the commit SHA.

## Environment variables (backend/.env)

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | API key for retrieve/generate calls to OpenAI |
| `CHROMA_PERSIST_DIR` | Directory where the vector DB is persisted |
| `ENCRYPTION_KEY` | Key used to encrypt each channel's bot token |
| `DATABASE_URL` | DB connection string (defaults to SQLite) |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | Admin dashboard login credentials |

Never commit a real `.env` file — it's already blocked by `.gitignore` at both the root and per-package level.

## Tests

```bash
# backend
cd backend && pytest

# frontend
cd frontend && npm run test
```

## Design docs

`docs/architecture-diagram.{html,svg}` — the system diagram above. Local implementation plans/specs (`docs/superpowers/`) are kept on disk for reference but are gitignored, not part of the repo history.
