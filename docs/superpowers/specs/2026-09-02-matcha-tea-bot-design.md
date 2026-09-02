# Premium Matcha & Tea Ceremony Consulting Bot — Design

Date: 2026-09-02

## Requirement (source)

From project requirements table (GenAI & AI Agents row):

> Premium Matcha & Tea Ceremony Consulting Bot — An Agent integrated via Zalo API
> (using AWS Bedrock or open-source LLMs) to answer questions about Matcha origins,
> brewing methods, and recommend products. Set up an automated pipeline to deploy
> the bot code whenever there are updates.

## Decisions vs. original requirement

The following deviations from the literal requirement text were agreed with the
requester during brainstorming, and this design builds on them:

- **Channel: Telegram, not Zalo.** No Zalo Official Account is provisioned yet
  (OA registration/business verification required). Telegram was chosen for v1
  to avoid blocking on that setup. A future Zalo adapter can be added later
  without changing the agent core, since the webhook handler is a thin layer
  in front of the LangGraph agent.
- **LLM: OpenAI API, not AWS Bedrock.** Requester has an OpenAI API key and
  prefers it over Bedrock.
- **RAG framework: LangGraph** (with Pydantic for structured state/tool I/O),
  not a bare Bedrock/LangChain setup.
- **CI/CD: GitHub Actions**, not Jenkins.
- **Vector store: Qdrant Cloud** (managed), not a local FAISS/Chroma index.
- **Scope addition: admin web app** for uploading/managing the product and
  brewing-knowledge documents that get embedded into Qdrant (not in the
  original one-line requirement, but necessary — someone has to get docs in).
- **Scope addition: persistent memory.** The agent stores chat history and
  infers/remembers each user's favourite drinks in Postgres, and uses that
  to personalize replies and recommendations.

## Architecture

```
Telegram user
    │ (message)
    ▼
Telegram Bot API ──webhook──▶ FastAPI backend (/webhook/telegram)
                                   │
                                   ▼
                           LangGraph agent graph
                     ┌─────────────┼──────────────┐
                     ▼             ▼              ▼
              fetch_history   retrieve (RAG)  (after generate)
              (Postgres)      (Qdrant Cloud)   extract_favourite
                     │             │           (Postgres write)
                     └──────┬──────┘
                             ▼
                       generate (OpenAI)
                             │
                             ▼
                    reply sent back via Telegram Bot API

Admin (browser) ──HTTPS──▶ nginx ──▶ React admin SPA (static)
                                   ──▶ FastAPI backend /admin/* (basic auth)
                                          │
                                          ▼
                                 ingest: chunk + embed doc
                                          │
                                          ▼
                                     Qdrant Cloud
```

Deployment: single VPS running Docker Compose with four containers —
`backend`, `frontend`, `postgres`, `nginx`. Qdrant Cloud and the OpenAI API
are external managed dependencies (no containers on the VPS for these).

## Components

### `backend/` (FastAPI, Python)

- `POST /webhook/telegram` — receives Telegram updates, invokes the agent
  graph for the given chat, sends the reply via the Telegram Bot API.
  Returns HTTP 200 immediately regardless of internal outcome (Telegram
  retries aggressively on non-200 / slow responses; errors are handled
  internally and surfaced to the user as a fallback message instead).
- `GET /health` — liveness check used by the CI smoke test and can be used
  for uptime monitoring.
- `agent/` — LangGraph graph, Pydantic models for state/tool schemas:
  - `fetch_history` node — loads recent conversation turns for this
    Telegram user from Postgres.
  - `retrieve` node — queries Qdrant Cloud for relevant matcha/tea
    knowledge and product chunks.
  - `generate` node — calls OpenAI with history + retrieved context,
    produces the reply.
  - `extract_favourite` node — runs after generate; a lightweight
    classification step that checks whether the user expressed a drink
    preference in this turn, and if so upserts it into the `favourites`
    table. Does not block the reply — the reply is sent first, extraction
    happens as a fire-and-forget follow-up.
- `admin/` routes (HTTP Basic Auth, credentials from env vars):
  - `POST /admin/docs` — upload a document (PDF/markdown/txt), chunk it,
    embed it, upsert into Qdrant, record metadata in Postgres (`documents`
    table) so the admin UI can list/delete by name.
  - `GET /admin/docs` — list uploaded documents with metadata.
  - `DELETE /admin/docs/{id}` — remove a document's vectors from Qdrant and
    its metadata row.
- `db/` — SQLAlchemy models and Alembic migrations for Postgres:
  - `users` (Telegram user id, first seen, etc.)
  - `messages` (user id, role, content, timestamp) — chat history
  - `favourites` (user id, drink name, confidence/source, timestamp)
  - `documents` (id, filename, chunk count, uploaded_at) — admin doc metadata

### `frontend/` (React admin SPA)

- Built with the ui-ux-pro-max skill for styling/components.
- Login screen (submits Basic Auth credentials, stored in memory /
  sessionStorage for the session).
- Document manager: upload form (drag-and-drop or file picker), list of
  uploaded docs with delete action, upload status/errors surfaced inline.
- No end-user-facing chat UI in this app — chat happens entirely in
  Telegram. This SPA is admin-only.

### `infra/`

- `backend/Dockerfile`, `frontend/Dockerfile`
- `docker-compose.yml` (VPS): `backend`, `frontend`, `postgres`, `nginx`
- `nginx/` config: routes `/` → frontend static, `/api/*` → backend,
  `/webhook/telegram` → backend
- `.github/workflows/deploy.yml`:
  1. On push to `main`: run backend tests (pytest) and frontend tests.
  2. Build `backend` and `frontend` images, push to GHCR tagged with commit SHA.
  3. SSH to the VPS, update `docker-compose.yml` image tags (or `.env`),
     `docker compose pull && docker compose up -d`.
  4. Hit `/health` after rollout; fail the workflow (and optionally alert)
     if it doesn't come back healthy within a short timeout.
  - Secrets (OpenAI key, Telegram bot token, Qdrant URL/key, Postgres
    creds, admin basic-auth creds, SSH deploy key) stored as GitHub Actions
    encrypted secrets, injected as env vars at deploy time — never
    committed to the repo.

## Data flow (chat turn)

1. Telegram sends webhook POST to backend on new message.
2. Backend loads/creates the `users` row, stores the incoming message in
   `messages`.
3. Agent graph runs: fetch recent history → retrieve Qdrant context →
   generate reply via OpenAI (system prompt includes user's known
   favourites, retrieved knowledge/product chunks, recent history).
4. Reply stored in `messages`, sent to user via Telegram Bot API.
5. `extract_favourite` runs, updates `favourites` if a new preference was
   expressed.

## Error handling

- Telegram webhook: always ACK 200 fast; internal failures logged and the
  user gets a friendly fallback reply ("having trouble right now, try
  again in a bit") rather than silence or a Telegram error retry storm.
- OpenAI / Qdrant calls: one retry with backoff on transient failure, then
  fall back to the friendly error reply; failure logged with enough
  context (user id, turn) to debug.
- Admin doc upload: validate file type/size before processing; embedding
  failures reported back to the SPA as a visible error, not a silent drop.
- CI/CD: deploy workflow fails (and does not mark the deploy successful)
  if the post-deploy `/health` check doesn't pass — no silent broken
  deploys.

## Testing

- Backend: pytest — agent nodes unit-tested with mocked OpenAI/Qdrant/DB;
  webhook endpoint integration-tested with a fake Telegram payload;
  admin endpoints tested for upload/list/delete happy path + basic-auth
  rejection.
- Frontend: component tests for login, upload, list, delete flows.
- CI: build the backend image, run `/health` smoke test, before allowing
  deploy to proceed.

## Out of scope (for this design)

- Zalo OA integration (deferred until an OA is provisioned; webhook layer
  is kept thin enough to add a Zalo adapter later without touching the
  agent core).
- Authoring the actual matcha/tea knowledge content — requester will
  supply source docs via the admin app.
- Multi-language support, analytics dashboards, or A/B testing of prompts.
