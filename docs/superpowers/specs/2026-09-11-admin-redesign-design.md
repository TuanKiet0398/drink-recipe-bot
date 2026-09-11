# Admin Panel Redesign + Test Chat — Design

## Context

`references/Matcha Admin Redesign.dc.html` is a mockup of a restyled admin panel. It
changes the look of every page under `/panel` and adds one new tab, **Chat**, where an
admin can talk to the bot directly without a real Telegram user.

The mockup's own review notes list the intent:

- Contrast fixed throughout — secondary text, badges and nav labels are solid colors
  reaching WCAG AA instead of opacity tints like `text-foreground/70`.
- Sidebar grouped into Main / Bot / Monitoring / System, with a profile chip at the top.
- A Chat tab to test the bot's replies.
- Visible keyboard focus rings on every button, link and input.

Scope decisions made during brainstorming:

1. **The public landing page (`/`) and the login page (`/login`) do not change**, visually
   or behaviourally.
2. **Every existing feature is kept.** The mockup omits several (pagination, per-row
   Delete on Usage and Audit Log, Prompt/Completion columns, the channel Type column,
   Activate/Deactivate, the force-delete dialog, Load models, Ollama Base URL, the "To"
   date filter). These stay; only their styling changes.
3. **Usage's donut chart is replaced by the mockup's horizontal bar list.**
4. **Chat is built in this spec**, as a stateless endpoint (see §3).
5. The mockup's "Show UI review" button is a design note, not a feature — it is not built.

## 1. Visual system

### Separate token namespace

The landing page, login page, `BrandIcon` and `MatchaIllustration` use the existing
Tailwind tokens (`primary`, `primary-dark`, `primary-light`, `surface`, `card`, `border`,
`muted`, `muted-foreground`, `foreground`, `gold`). Changing those values would restyle
the pages that must not change, so **existing token values stay untouched**.

A new `admin` color group is added to `frontend/tailwind.config.js`:

| Token | Value | Use |
|---|---|---|
| `admin-primary` | `#3E6B37` | Primary buttons, active nav, user chat bubble |
| `admin-primary-dark` | `#2C4F27` | Primary hover, brand text, badge text |
| `admin-primary-light` | `#E4EEDD` | Nav hover, success badge, bot avatar |
| `admin-bg` | `#F5F7F1` | Page background, secondary hover, bot bubble |
| `admin-border` | `#DCE3D4` | Card, input and table-header borders |
| `admin-divider` | `#ECEFE6` | Table row dividers, sidebar separators |
| `admin-fg` | `#1C2A1F` | Primary text |
| `admin-fg-2` | `#33422F` | Secondary button text, neutral badge text |
| `admin-muted` | `#55604D` | Descriptions, table headers, muted cells |
| `admin-label` | `#7C8874` | Nav group labels, chat meta |
| `admin-danger` | `#B91C1C` | Destructive text |
| `admin-danger-light` | `#FEF2F2` | Destructive hover, blocked/inactive badge |
| `admin-danger-border` | `#F3C6C6` | "Clear all" border |

Plus `boxShadow.admin-card: 0 1px 2px rgba(28,42,31,0.06)`.

The warning badge (`login_failed`) uses `#FFFBEB` / `#92400E` — Tailwind's `amber-50` /
`amber-800`, so no token is needed.

### Global styles (`frontend/src/index.css`)

The base `th`, `td` and `tbody tr` rules are used only inside the panel (landing and login
have no tables), so they switch to the mockup's values:

- `th`: `px-3.5 py-2.5`, 11px, bold, uppercase, `tracking-wide`, `text-admin-muted`,
  bottom border `admin-border`.
- `td`: `px-3.5 py-2.5`, 13.5px, bottom border `admin-divider`.
- `tbody tr:hover`: `admin-primary-light` at 50%.

The global focus-visible rule (`ring-2 ring-primary ring-offset-2`) is **not changed**, since
landing and login use it. It already gives every button and link a visible ring. Form
fields in the panel additionally get the mockup's soft ring through the `input` constant
(`focus:border-admin-primary focus:ring-[3px] focus:ring-admin-primary/20
focus:outline-none`), and `select`/`textarea` are added to the global rule's selector list
so they are covered too.

`body` keeps `bg-surface`; `AppShell` paints `bg-admin-bg` over it.

### Shared class strings (`frontend/src/layout/styles.ts`)

Button, input and card class strings repeat across nine pages. They live as plain string
constants in one file, following the existing `fieldClass` pattern — no component library:

- `card` — `rounded-xl border border-admin-border bg-white shadow-admin-card`
- `pageTitle`, `pageDescription`
- `btnPrimary`, `btnSecondary`, `btnDanger` (outlined "Clear all"), `btnGhost`,
  `btnGhostPrimary`, `btnGhostDanger` (row actions)
- `input` (also used for `select` and `textarea`)
- `badgeNeutral`, `badgeSuccess`, `badgeDanger`, `badgeWarning`
- `alertError`, `alertSuccess`, `alertWarning` (the existing banners)

Pages compose these with layout classes as needed.

## 2. Shell and routing

### `AppShell.tsx`

- Sidebar 232px wide, white, right border `admin-border`, padding `20px 14px`.
- Brand block: `BrandIcon` (its SVG is identical to the mockup's cup icon) in
  `text-admin-primary-dark`, with "Shop Assistant" / "Admin panel", separated by an
  `admin-divider` rule.
- Profile chip: circular avatar with the username's first letter uppercased, the username,
  and "Signed in".
- Nav groups, each with a small uppercase label in `admin-label`:
  - **Main** — Chat, Usage
  - **Bot** — Documents, Personality, Channels
  - **Monitoring** — Users, Access Log, Audit Log
  - **System** — Settings
- Items stay `NavLink`s (tests query `getByRole("link", { name: "Users" })`). Active:
  `bg-admin-primary text-white`; inactive: `text-admin-fg-2`, hover `admin-primary-light`.
- "Log out" at the bottom with a top divider, calling `logout` as today.
- `main`: `flex-1 overflow-y-auto`, padding `26px 32px`, content capped at 1180px.

### `AuthContext.tsx`

Adds `username: string | null` to the context value, read from `getStoredCredentials()` on
init and set on `login`, cleared on `logout`. No API call. `LoginPage` is not modified — it
already calls `login(username, password)`.

### `App.tsx`

Adds `<Route path="chat" element={<ChatPage />} />`. The `/panel` index redirect stays on
`usage`, and the post-login redirect (owned by `LoginPage`) is unchanged.

## 3. Test Chat

### Backend: `backend/app/routers/admin_chat.py`

Registered in `app/main.py` next to the other admin routers.

`POST /admin/chat`, protected by `require_admin`.

Request:

```json
{
  "message": "Cách pha matcha đá?",
  "history": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ]
}
```

- `message`: `str`, stripped length ≥ 1, length ≤ 4000.
- `history`: list of `{role: Literal["user", "assistant"], content: str}`, default `[]`.
- The server uses only the **last 10** history entries, matching `fetch_history`'s
  `limit=10`, so a client cannot grow the prompt without bound.

Behaviour:

1. Build `AgentState(user_id=None, chat_id="admin-chat", incoming_text=message,
   history=history[-10:])`.
2. In one `asyncio.to_thread` call, run `retrieve(state, db, chroma_client, chat_client,
   embedding_client, chat_model)` then `generate(state, db, chat_client, chat_model)`,
   using `get_chroma_client()`, `get_chat_client(db)`, `get_embedding_client()` and
   `get_chat_model(db)` — the same clients the Telegram path uses. The graph
   (`run_agent`) is not used because its entry node is `fetch_history`, which loads
   per-customer memory from the database.
3. Return `200 {"reply": state.reply, "model": chat_model}`.

Response on failure: if `retrieve`/`generate` raises (e.g. the LLM provider is down or the
key is wrong), return `502 {"detail": "<str(exception)>"}`. The Telegram path's
`FALLBACK_REPLY` is deliberately not used — an admin testing the bot needs the real error.
`retrieve` already swallows knowledge-base errors and continues with no context; that
behaviour is unchanged.

Explicitly **not** done:

- No `User`, `Channel` or `Message` rows are created.
- No background extractors (favourite, summary, customer notes, recommendation).
- No daily token limit check (there is no customer).
- No audit log entry — test messages are not configuration changes and would flood the log.

Token usage **is** still recorded by the existing `log_token_usage` calls inside
`retrieve`/`generate`, with `user_id=None` — it is real spend. It shows as "—" in the Usage
table's User column, as it does today for null users.

### `AgentState` change

`backend/app/agent/state.py`: `user_id: int` becomes `user_id: int | None`. The only code
that queries by `state.user_id` is `fetch_history` and the extractors, none of which run on
the chat path. `log_token_usage` already accepts `None`.

### Frontend: `frontend/src/chat/ChatPage.tsx`

Layout follows the mockup: header, a model bar, a scrolling message panel, and an input
form, in a column of height `calc(100vh - 120px)`.

- **Model bar.** On mount, `GET /admin/llm-settings` (existing endpoint). On success, show a
  badge "● {chat_model}" and "via OpenAI" / "via Ollama". On failure, hide the badge; the
  page still works. A "Reset conversation" button sits on the right.
- **State.** `messages: {role: "user" | "assistant", content: string}[]`, `input`,
  `sending`, `error`. Starts empty with a hint: "Send a message to test the bot's replies."
- **Send** (form submit, so Enter works):
  1. Ignore if `input.trim()` is empty or `sending` is true.
  2. Append the user message, clear the input, set `sending`, clear `error`.
  3. `POST /admin/chat` with `message` and `history` = the messages *before* this one.
  4. On success, append `{role: "assistant", content: reply}` and remember `model` for the
     bubble meta.
  5. On failure, show a `role="alert"` banner with the server's `detail` (parsed the same
     way `ChannelsPage.readableError` does), falling back to "Failed to get a reply". The
     user message stays in the list; nothing is retried automatically.
  6. Clear `sending`.
- **While sending**: a bot-side bubble "Đang trả lời…" is shown and Send is disabled
  (`bg` `#9FB396`, `cursor-not-allowed`).
- **Reset conversation** clears `messages` and `error`.
- **Bubbles.** User: right-aligned, `admin-primary` background, white text, radius
  `14px 14px 4px 14px`, avatar with the username initial; meta "Admin (test)". Bot:
  left-aligned, `admin-bg` background with `admin-border` border, radius
  `14px 14px 14px 4px`, `BrandIcon` avatar; meta "Bot · {model}". Max width 70%,
  `whitespace-pre-wrap`.
- **Scroll.** After each message change, set the panel's `scrollTop = scrollHeight`.

`readableError` moves from `ChannelsPage.tsx` to `frontend/src/api/client.ts` so both pages
use one copy.

## 4. Existing pages

Each page keeps its current data flow, state, handlers, visible text, labels and
`aria-*` attributes. Only class names change, to the `admin-*` tokens and `styles.ts`
constants. Common rules:

- Header: `h1` 20px bold `admin-fg`; description 13.5px `admin-muted`, 4px below.
- Page column gap 16px.
- Cards and table wrappers use `card`; tables sit in `overflow-x-auto`.
- Loading and empty rows keep their current text, styled `admin-muted`.
- Pagination buttons use `btnSecondary`.

Page-specific notes:

- **Usage** — Stat cards: 11px uppercase label, 24px bold value, `grid` with
  `repeat(auto-fit, minmax(160px, 1fr))`. Values keep their current raw formatting
  (`123456`, `$1.2345`) — the mockup's `1,284` / `$18.42` formatting is not adopted because
  the existing `UsagePage` tests assert the raw values. **"Tokens by Model"** becomes a list of rows inside `UsagePage`: a
  10px color dot, the model name (min-width 180px, truncated), an 8px track
  (`#F1EFE7`) with a fill at the model's share, and "512.3K · 58%" right-aligned. Rows are
  sorted by tokens descending and keep the existing fixed categorical palette. The empty
  state stays "No usage recorded yet." `UsageByModelChart.tsx` is deleted. The table keeps
  Prompt, Completion and the Delete column.
- **Documents** — Upload label styled as `btnSecondary` with a card shadow; the Delete
  action uses `btnGhostDanger`.
- **Personality** — Card capped at 640px; textarea uses `input`.
- **Channels** — "+ Add Channel" uses `btnPrimary`; the form is a `card`; row actions use
  ghost buttons (Test neutral, Edit and Activate/Deactivate primary, Delete danger); status
  badges `badgeSuccess` / `badgeDanger`. The Type column and force-delete dialog stay,
  restyled.
- **Users** — Status badges `badgeSuccess` ("Active") / `badgeDanger` ("Blocked");
  Block/Unblock uses `btnGhostPrimary`.
- **Access Log** — Filters keep their labels (Role, Customer, From, To); controls use
  `input`; role badge `badgeNeutral`.
- **Audit Log** — `actionBadgeClass` returns `badgeDanger` / `badgeWarning` /
  `badgeSuccess`; filters and "Clear all" restyled; relative time stays.
- **Settings** — Card capped at 560px; fields use `input`; the default-config, saved,
  error and confirm-save banners use the `alert*` constants; the test result keeps its
  text ("OK — model, Nms").

## 5. Testing

### Backend — `backend/tests/test_admin_chat.py`

- Without auth: 401.
- Empty/whitespace `message`, a `message` over 4000 characters, or an invalid history
  `role`: 422.
- Happy path with `retrieve` and `generate` monkeypatched in `app.routers.admin_chat`:
  200 with `reply` and `model`, and no `User` or `Message` rows exist afterwards.
- With 15 history entries, the state passed to `generate` holds only the last 10.
- When `generate` raises: 502 with the exception message in `detail`.

`test_agent_nodes.py`, `test_agent_graph.py` and `test_webhook.py` must keep passing after
the `AgentState.user_id` change.

### Frontend

- New `frontend/tests/chat/ChatPage.test.tsx`:
  - The model badge shows the model from `/admin/llm-settings`.
  - Sending shows the user message, then the reply; the request body carries the prior
    messages as `history`.
  - Send is disabled while a request is pending.
  - A 502 response shows the `detail` in a `role="alert"` banner.
  - Reset clears the conversation.
- `frontend/tests/App.test.tsx`: add navigating to Chat via its sidebar link, and logging out
  via "Log out". The welcome and login tests are not edited.
- `frontend/tests/usage/UsagePage.test.tsx` has no donut-specific assertions, so it stays
  unmodified like the rest.
- Every existing test must pass **without modification**. A test that has to change
  means a restyle altered a label or behaviour, which is a bug.

### Verification

`npm test`, `npm run build` (includes `tsc`), backend `pytest`. Then run the app and
screenshot each panel tab against the mockup, and the landing and login pages against their
current appearance.

## 6. Implementation order

Each step is one commit.

1. Backend: `AgentState.user_id` optional; `POST /admin/chat` with tests.
2. Frontend foundation: `admin-*` tokens, `index.css`, `layout/styles.ts`,
   `AuthContext.username`, new `AppShell`, `/panel/chat` route, `readableError` moved to
   `api/client.ts`.
3. `ChatPage` with tests.
4. Usage: bar list, delete `UsageByModelChart`.
5. Restyle Documents, Personality, Channels.
6. Restyle Users, Access Log, Audit Log, Settings.
7. Full verification and screenshots.
