# Matcha Bot — Full Coverage Test Plan

Manual + scriptable test plan across every feature currently in the codebase.
Use two throwaway accounts (`tester-a` / `tester-b`) registered via the login
page's "Create one" link for the multi-user cases — don't reuse the real
`admin` account for isolation tests.

Endpoints referenced come straight from `backend/app/routers/*.py` — nothing
here is speculative.

## 1. Auth & accounts

- [ ] `POST /auth/register` with a 2-char username → 422.
- [ ] Register with password < 8 chars → 422.
- [ ] Register with a username already taken → 409 `Username already taken`.
- [ ] Register with username == `ADMIN_USERNAME` → 409.
- [ ] Register with valid username/password → 201, `account.register` audit entry written.
- [ ] Log in with the new account → redirects to `/panel/chat`.
- [ ] Log in with wrong password → 401, `login_failed` audit entry.
- [ ] `.env` admin (`ADMIN_USERNAME`/`ADMIN_PASSWORD`) still logs in exactly as before accounts existed.
- [ ] Frontend: mismatched Password/Confirm on register form → client-side error, no request sent.

## 2. Chat — single user memory

Login as `tester-a`, open the Chat tab, send each line below **in order**,
one at a time, and check the note after `→`.

1. `chào shop` → bot trả lời bình thường (đây là tin đầu tiên của account này — `get_web_user` vừa tạo `User` mới, không lỗi).
2. `mình thích uống matcha latte đá` → bot ghi nhận (không cần bot phản hồi gì đặc biệt ngay, chỉ cần không lỗi).
3. `mình thích uống gì nhỉ, quên mất rồi` → bot phải nhắc lại "matcha latte đá" (favourite được nhớ qua `fetch_history`).
4. `mình bị dị ứng sữa, tư vấn đồ không sữa được không` → bot tư vấn đồ không sữa; gửi thêm 1 câu bất kỳ nữa rồi hỏi lại `mình dị ứng gì nhỉ` → bot phải nhắc đúng "dị ứng sữa" (test `CustomerNote`).
5. Gửi thêm khoảng 20 tin qua lại bất kỳ (chat linh tinh về đồ uống cho đủ số lượng) → sau đó hỏi `tóm tắt lại là mình đã nói gì với shop từ đầu` → bot trả lời dựa trên tóm tắt, không bị "quên" đoạn đầu (test rolling summary).
6. `gợi ý cho mình 1 món` rồi vài tin sau `gợi ý lại món khác đi` → bot không lặp lại y hệt món cũ (test `RecommendationHistory`).
7. Bấm nút **Reset conversation** trên UI → lịch sử chat biến mất trên màn hình; hỏi lại `mình thích uống gì` → bot **vẫn phải nhớ** "matcha latte đá" (favourite sống sót qua reset, chỉ mất `Message`/`ConversationSummary`).
8. Gõ 1 tin dài quá 4000 ký tự (copy-paste 1 đoạn văn dài) → gửi → phải báo lỗi (422), không gửi được.
9. Gõ khoảng trắng rồi bấm gửi → nút gửi phải không hoạt động / báo lỗi, không tạo tin nhắn rỗng.
10. (Cần admin tắt mạng hoặc key sai tạm thời) gửi 1 tin bất kỳ → thấy banner lỗi đỏ trên UI (502), tin nhắn của mình vẫn hiện trong Access Log dù bot không trả lời được.
11. Vào Users page, Block account `tester-a`, quay lại Chat gửi tin bất kỳ → banner báo "Your account is blocked" (403), không tốn token gọi LLM.

## 3. Multi-user isolation

Cần 2 account: `tester-a` và `tester-b`.

1. Login `tester-a`, gửi `mình thích trà sữa matcha` → logout, login `tester-b`, mở tab Chat → lịch sử phải trống trơn, không thấy gì của A.
2. Với `tester-b`, gõ `mình thích uống gì nhỉ` → bot **không được** nhắc tới "trà sữa matcha" của A (đó không phải sở thích của B).
3. Login lại `tester-a`, gõ `mình dị ứng đậu phộng nha` → login `tester-b`, gõ `mình có dị ứng gì không nhỉ` → bot của B không được biết chuyện dị ứng đậu phộng của A.
4. Cho `tester-a` chat đủ dài để có rolling summary (xem mục 2.5) → tạo account `tester-c` mới, hỏi ngay `tóm tắt cuộc trò chuyện của mình đi` → bot phải nói kiểu chưa có gì để tóm tắt, không lẫn summary của A.
5. `tester-a` bấm Reset conversation → login `tester-b`, kiểm tra lịch sử/sở thích của B vẫn còn nguyên, không bị ảnh hưởng.
6. Vào Settings đặt `daily_token_limit` thấp (ví dụ 500), chat bằng `tester-a` tới khi bot trả lời câu giới hạn cố định (không phải LLM thật) → login `tester-b`, chat bình thường → B vẫn được trả lời thật, không bị dính giới hạn của A.
7. Login bằng tài khoản `admin`/`admin` (không phải account tự đăng ký), chat vài câu → không lẫn lịch sử với `tester-a`/`tester-b`.

## 4. Channels

`admin_channels.py` — Telegram-type channels only (`web` channel is internal/hidden).

- [ ] Create a channel with a valid bot token → 201, token never appears in the response, `encrypted_credentials` in DB decrypts to the token.
- [ ] Create with `channel_type: "zalo"` → 400 unsupported.
- [ ] List channels → never includes `encrypted_credentials`/`bot_token`, excludes the `web` channel.
- [ ] `POST /admin/channels/test` with a bad token → 400 with Telegram's error message.
- [ ] `POST /admin/channels/{id}/test` on a real channel → uses the stored token, not one from the request.
- [ ] Update `is_active` → toggles, `channel_manager.sync` re-invoked.
- [ ] Rotate `bot_token` via PATCH → new token encrypted and stored, old one gone.
- [ ] Delete a channel (no `force`) → 204, **soft delete**: `deleted_at` set, `is_active=False`, its users and all their memory tables stay intact.
- [ ] List channels after a soft delete → the deleted one no longer appears.
- [ ] PATCH a soft-deleted channel → 404.
- [ ] Re-add a channel with the **same bot token** as a soft-deleted one → revives the same row (same `id`), new key/display name applied, `is_active=True` again, old users' memory immediately usable again.
- [ ] Re-add with a **different** token → creates a brand-new channel row, no collision.
- [ ] Delete with `?force=true` on a channel with users → 204, channel row **and** its users **and** every memory table (`Message`, `Favourite`, `TokenUsage`, `CustomerNote`, `ConversationSummary`, `RecommendationHistory`) erased — irreversible path.
- [ ] Frontend: click "Delete" → native confirm dialog explaining data is kept, row disappears from the list on accept.
- [ ] Frontend: click "Delete permanently" → modal requires typing the exact channel key before the button enables.

## 5. Telegram path (real customers, not the panel)

- [ ] Send a Telegram message to a configured bot → `process_telegram_message` creates/updates the `User`, runs the same agent graph, replies via Telegram.
- [ ] Same customer messages again later → history/favourites/notes/summary from the web-chat memory tables are recalled (memory is shared infrastructure, not web-only).
- [ ] Bot is slow to reply → `_keepalive_typing` sends "typing…" action so Telegram doesn't look stuck.
- [ ] Background extraction after a Telegram reply → `spawn_background_extractions` fires the same four extractors (favourite, summary, notes, recommendation) as the web path.

## 6. Documents / RAG ingestion

`admin_docs.py`.

- [ ] Upload a short document → 201, appears in `GET /admin/docs`.
- [ ] Upload a long document (long-document ingestion feature) → `split_into_pieces`/`chunk_document` pre-split it, multiple chunks land in Chroma instead of one oversized embedding call.
- [ ] Delete a document → 204, its chunks no longer surface in `retrieve()` results.
- [ ] Ask the bot something the doc answers → reply uses the retrieved chunk (check `retrieved_chunks`/reply content).
- [ ] Ask something no doc covers → `retrieve()` tolerates zero hits, bot still replies without KB context.

## 7. Personality (soul)

`admin_soul.py`.

- [ ] `GET /admin/soul` → returns current `SOUL.md` content.
- [ ] `PUT /admin/soul` with new text, then chat → next reply's tone/persona reflects the edit **without a backend restart** (`_load_soul` reads fresh each call).

## 8. Settings — LLM provider & limits

`admin_llm_settings.py`.

- [ ] `GET /admin/llm-settings` → returns current provider/model/base_url, no raw secrets.
- [ ] `POST /admin/llm-settings/test` with valid creds → "OK — model, Nms" style result, doesn't disturb the live client.
- [ ] `POST /admin/llm-settings/models` → lists available models for the configured provider.
- [ ] `PUT /admin/llm-settings` switching OpenAI → Ollama (or back) → next chat message uses the new provider (check the `model` field in the response), no restart needed.
- [ ] Set `daily_token_limit`, exhaust it, chat again → `DAILY_LIMIT_REPLY` returned, no LLM call, no token spend.
- [ ] Frontend: type a non-numeric value into the daily limit field → no `NaN` sent/saved (regression check for the `9d4e860` fix).

## 9. Retention (30-day purge)

`app/retention.py`.

- [ ] Back-date a user's `last_active_at` past 30 days, run `purge_inactive_messages` → their `Message` rows are deleted.
- [ ] A user active within 30 days → untouched by the same purge run.
- [ ] `run_retention_loop` running under `app/main.py`'s lifespan → fires on its own schedule without manual invocation (check logs over the scan interval).

## 10. Users, Access Log, Audit Log, Usage

- [ ] `GET /admin/users` → lists customers across channels, active/blocked status.
- [ ] Block then unblock a user → status flips both ways, blocked user's chat gets 403 (see section 2).
- [ ] `GET /admin/logs/access` filtered by role/customer/date → filters actually narrow the result set.
- [ ] `GET /admin/logs/audit` after a handful of admin actions → every mutating admin action (create/update/delete channel, register, login_failed, soul edit, settings save) shows up.
- [ ] Delete one audit entry, then clear all → both delete paths work without crashing.
- [ ] `GET /admin/usage` and `/admin/usage/summary` after some chats → token counts match what was actually spent.
- [ ] Delete a usage entry / clear all usage → 204, rows gone.

## 11. Performance / latency

Covered already this session — regression-guard it going forward.

- [ ] Send a chat message, wait >5s, send another → second message should NOT re-pay a full TLS handshake (see `_KEEPALIVE_EXPIRY_SECONDS` in `app/agent/clients.py`); time both, second should be markedly faster than the first cold call.
- [ ] Very first message after a fresh backend boot → expected to be slow (cold TLS/DNS), not a bug, just note the baseline.
- [ ] Switch LLM provider in Settings, then chat → `invalidate_chat_client()` must actually drop the cached client, confirm the new provider's latency profile applies and not a stale connection.

## 12. Cross-cutting edge cases

- [ ] Two browser tabs, same account, send messages from both roughly simultaneously → no crash, both messages land, history stays consistent (SQLite locking).
- [ ] LLM provider key invalid/revoked mid-session → chat returns 502 with the real error (not swallowed), Telegram path falls back to `FALLBACK_REPLY` instead of crashing.
- [ ] Chroma DB unreachable/corrupted → `retrieve()` degrades to no-context reply, doesn't 500 the whole turn.
- [ ] Extremely long conversation (well past summary threshold) in one session → no unbounded prompt growth, rolling summary keeps prompt size roughly flat.

---

**How to knock this out fast:** sections 1–3 are the highest-value/newest
code (this week's work) — do those first, manually through the UI, two
browser profiles for A/B. Section 4 already has automated coverage in
`backend/tests/test_admin_channels.py` (19 cases) — just rerun `pytest`.
Sections 5–10 are mostly pre-existing and lower-risk — spot-check rather
than exhaustively redo unless something regressed. Section 11 needs a
stopwatch, not a test framework.
