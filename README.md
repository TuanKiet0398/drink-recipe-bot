# Matcha Bot

A drink-recipe (tea, matcha, etc.) consulting chatbot for a shop, served over Telegram, plus an admin dashboard for running and monitoring it.

## Key features

- **RAG chatbot on Telegram**: answers customers via OpenAI, grounding responses on uploaded recipe documents retrieved from a Chroma vector DB — never invents a drink/ingredient outside those documents (`backend/SOUL.md` defines the bot's personality and tone).
- **Multi-channel**: manages several Telegram bot connections at once (`ChannelManager`), each channel with its own bot token, encrypted with AES-GCM (`app/crypto.py`) before being stored.
- **React admin SPA**:
  - Channels: create/edit/delete, test connection (checks the token still works), force-delete a channel that still has users attached (with a type-to-confirm modal).
  - Docs: upload/list/delete the recipe documents that back the bot's knowledge base.
  - Users: list/block/unblock users per channel.
  - Access log & Audit log: access history and admin action history (filter by action, search, danger badges).
  - Usage: token usage tracking (chart by model) for OpenAI calls.
- **Auth**: Basic Auth for the admin dashboard (`ADMIN_USERNAME` / `ADMIN_PASSWORD`).

## Architecture / stack

| Layer | Tech |
|---|---|
| Backend | FastAPI, SQLAlchemy + Alembic, LangGraph (agent graph: fetch_history → retrieve → generate → extract_favourite) |
| Vector DB | ChromaDB |
| LLM | OpenAI API |
| Database | SQLite (default) / PostgreSQL supported via `DATABASE_URL` |
| Frontend | React + TypeScript + Vite, Tailwind CSS, React Router |
| Telegram | Per-channel long-polling (`telegram_poller.py`, `telegram_client.py`) |
| Infra | Docker Compose (backend + frontend), GitHub Actions CI/CD |

### Project layout

```
backend/
  app/
    agent/          # LangGraph nodes: fetch_history, retrieve, generate, extract_favourite
    routers/        # admin_channels, admin_docs, admin_logs, admin_usage, admin_users, health, webhook
    db/              # models + session
    channel_manager.py   # manages the poller for each Telegram channel
    crypto.py             # token/credential encryption (AES-GCM)
    config.py             # settings (env)
  SOUL.md            # bot personality / tone
  migrations/        # Alembic
frontend/
  src/               # React SPA (Channels, Docs, Users, Access Log, Audit Log, Usage pages)
docs/                # design specs & implementation plans
sample-recipes/      # sample recipes for testing ingestion/RAG
docker-compose.yml
```

## Running the project

### Docker Compose (recommended)

Create `backend/.env` (see the environment variables table below), then:

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

See the `docs/` directory — it holds design specs and implementation plans for each major feature (RAG, multi-channel admin, token usage tracking, etc.).
