import { useEffect, useState } from "react";
import { apiFetch, ApiError, readableError } from "../api/client";
import * as s from "../layout/styles";

interface Channel {
  id: number;
  key: string;
  display_name: string;
  channel_type: string;
  is_active: boolean;
  created_at: string;
}

const CHANNEL_TYPES: { value: string; label: string; enabled: boolean }[] = [
  { value: "telegram", label: "Telegram", enabled: true },
  { value: "zalo", label: "Zalo (coming soon)", enabled: false },
];

const EMPTY_FORM = { key: "", display_name: "", channel_type: "telegram", bot_token: "" };

type TestResult = { ok: true; username: string } | { ok: false; message: string };

function TestResultLine({ result }: { result: TestResult }) {
  return (
    <p className={`mt-1 text-xs ${result.ok ? "text-admin-primary-dark" : "text-admin-danger"}`}>
      {result.ok ? `✓ Connected as @${result.username}` : `✗ ${result.message}`}
    </p>
  );
}

export function ChannelsPage() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [formTest, setFormTest] = useState<TestResult | null>(null);
  const [formTesting, setFormTesting] = useState(false);
  const [rowTest, setRowTest] = useState<Record<number, TestResult>>({});
  const [rowTesting, setRowTesting] = useState<Record<number, boolean>>({});
  const [forceDeleteTarget, setForceDeleteTarget] = useState<{ channel: Channel; message: string } | null>(null);
  const [forceDeleteInput, setForceDeleteInput] = useState("");
  const [forceDeleting, setForceDeleting] = useState(false);

  async function loadChannels(): Promise<void> {
    try {
      const data = await apiFetch<Channel[]>("/admin/channels");
      setChannels(data);
      setError(null);
    } catch {
      setError("Failed to load channels");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadChannels();
  }, []);

  function openCreateForm(): void {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setFormTest(null);
    setShowForm(true);
  }

  function openEditForm(channel: Channel): void {
    setEditingId(channel.id);
    setForm({ key: channel.key, display_name: channel.display_name, channel_type: channel.channel_type, bot_token: "" });
    setFormTest(null);
    setShowForm(true);
  }

  async function toggleActive(channel: Channel): Promise<void> {
    try {
      await apiFetch(`/admin/channels/${channel.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: !channel.is_active }),
      });
      await loadChannels();
    } catch {
      setError("Failed to update channel");
    }
  }

  async function deleteChannel(channel: Channel): Promise<void> {
    try {
      await apiFetch(`/admin/channels/${channel.id}`, { method: "DELETE" });
      setError(null);
      await loadChannels();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(null);
        setForceDeleteInput("");
        setForceDeleteTarget({ channel, message: readableError(err, "This channel still has users attached.") });
        return;
      }
      setError(readableError(err, "Failed to delete channel"));
    }
  }

  async function confirmForceDelete(): Promise<void> {
    if (!forceDeleteTarget) return;
    setForceDeleting(true);
    try {
      await apiFetch(`/admin/channels/${forceDeleteTarget.channel.id}?force=true`, { method: "DELETE" });
      setError(null);
      setForceDeleteTarget(null);
      await loadChannels();
    } catch (err) {
      setError(readableError(err, "Failed to delete channel"));
      setForceDeleteTarget(null);
    } finally {
      setForceDeleting(false);
    }
  }

  async function submitForm(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      if (editingId === null) {
        await apiFetch("/admin/channels", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(form),
        });
      } else {
        const payload: Record<string, unknown> = { display_name: form.display_name };
        if (form.bot_token) payload.bot_token = form.bot_token;
        await apiFetch(`/admin/channels/${editingId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      }
      setForm(EMPTY_FORM);
      setShowForm(false);
      setEditingId(null);
      await loadChannels();
    } catch {
      setError(editingId === null ? "Failed to create channel" : "Failed to update channel");
    } finally {
      setSubmitting(false);
    }
  }

  async function testFormConnection(): Promise<void> {
    setFormTesting(true);
    setFormTest(null);
    try {
      if (form.bot_token) {
        const result = await apiFetch<{ ok: true; username: string }>("/admin/channels/test", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ channel_type: form.channel_type, bot_token: form.bot_token }),
        });
        setFormTest(result);
      } else if (editingId !== null) {
        const result = await apiFetch<{ ok: true; username: string }>(`/admin/channels/${editingId}/test`, {
          method: "POST",
        });
        setFormTest(result);
      } else {
        setFormTest({ ok: false, message: "Enter a bot token first" });
      }
    } catch (err) {
      setFormTest({ ok: false, message: readableError(err, "Connection failed") });
    } finally {
      setFormTesting(false);
    }
  }

  async function testRowConnection(channel: Channel): Promise<void> {
    setRowTesting((prev) => ({ ...prev, [channel.id]: true }));
    setRowTest((prev) => ({ ...prev, [channel.id]: undefined as unknown as TestResult }));
    try {
      const result = await apiFetch<{ ok: true; username: string }>(`/admin/channels/${channel.id}/test`, {
        method: "POST",
      });
      setRowTest((prev) => ({ ...prev, [channel.id]: result }));
    } catch (err) {
      setRowTest((prev) => ({ ...prev, [channel.id]: { ok: false, message: readableError(err, "Connection failed") } }));
    } finally {
      setRowTesting((prev) => ({ ...prev, [channel.id]: false }));
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className={s.pageTitle}>Channels</h1>
          <p className={s.pageDescription}>Chat platform connections (Telegram, and more soon).</p>
        </div>
        <button onClick={() => (showForm ? setShowForm(false) : openCreateForm())} className={s.btnPrimary}>
          + Add Channel
        </button>
      </div>

      {error && (
        <p role="alert" className={s.alertError}>
          {error}
        </p>
      )}

      {showForm && (
        <form onSubmit={submitForm} className={`${s.card} flex flex-col gap-3 p-[18px]`}>
          <h2 className="text-sm font-bold text-admin-fg">{editingId === null ? "New Channel" : "Edit Channel"}</h2>
          <label className={s.fieldLabel}>
            Key
            <input
              required
              disabled={editingId !== null}
              value={form.key}
              onChange={(e) => setForm({ ...form, key: e.target.value })}
              placeholder="my-telegram-bot"
              className={s.input}
            />
          </label>
          <label className={s.fieldLabel}>
            Display Name
            <input
              required
              value={form.display_name}
              onChange={(e) => setForm({ ...form, display_name: e.target.value })}
              placeholder="Sales Bot"
              className={s.input}
            />
          </label>
          <label className={s.fieldLabel}>
            Channel Type
            <select
              value={form.channel_type}
              disabled={editingId !== null}
              onChange={(e) => setForm({ ...form, channel_type: e.target.value })}
              className={s.input}
            >
              {CHANNEL_TYPES.map((t) => (
                <option key={t.value} value={t.value} disabled={!t.enabled}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
          <div className={s.fieldLabel}>
            <label htmlFor="channel-bot-token">Bot Token</label>
            <div className="flex gap-2">
              <input
                id="channel-bot-token"
                required={editingId === null}
                type="password"
                value={form.bot_token}
                onChange={(e) => setForm({ ...form, bot_token: e.target.value })}
                placeholder={editingId === null ? "123456:ABC-DEF..." : "Leave blank to keep current token"}
                className={`${s.input} w-full`}
              />
              <button type="button" onClick={testFormConnection} disabled={formTesting} className={`${s.btnSecondary} shrink-0`}>
                {formTesting ? "Testing…" : "Test"}
              </button>
            </div>
            {formTest && <TestResultLine result={formTest} />}
          </div>
          <div className="flex gap-2">
            <button type="submit" disabled={submitting} className={s.btnPrimary}>
              {editingId === null ? "Create" : "Save"}
            </button>
            <button type="button" onClick={() => setShowForm(false)} className={s.btnSecondary}>
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className={`${s.card} overflow-x-auto`}>
        <table className="w-full">
          <thead>
            <tr>
              <th>Key</th>
              <th>Display Name</th>
              <th>Type</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className={s.emptyCell}>
                  Loading channels…
                </td>
              </tr>
            ) : channels.length === 0 ? (
              <tr>
                <td colSpan={5} className={s.emptyCell}>
                  No channels yet — add one to connect a bot.
                </td>
              </tr>
            ) : (
              channels.map((channel) => (
                <tr key={channel.id}>
                  <td className="font-semibold">{channel.key}</td>
                  <td>{channel.display_name}</td>
                  <td className="text-admin-muted">{channel.channel_type}</td>
                  <td>
                    <span className={channel.is_active ? s.badgeSuccess : s.badgeDanger}>
                      {channel.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td>
                    <div className="flex flex-wrap gap-1.5">
                      <button
                        onClick={() => testRowConnection(channel)}
                        disabled={rowTesting[channel.id]}
                        className={s.btnGhost}
                      >
                        {rowTesting[channel.id] ? "Testing…" : "Test"}
                      </button>
                      <button onClick={() => openEditForm(channel)} className={s.btnGhostPrimary}>
                        Edit
                      </button>
                      <button onClick={() => toggleActive(channel)} className={s.btnGhostPrimary}>
                        {channel.is_active ? "Deactivate" : "Activate"}
                      </button>
                      <button onClick={() => deleteChannel(channel)} className={s.btnGhostDanger}>
                        Delete
                      </button>
                    </div>
                    {rowTest[channel.id] && <TestResultLine result={rowTest[channel.id]} />}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {forceDeleteTarget && (
        <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/40 p-4">
          <div className={`${s.card} w-full max-w-md p-5`}>
            <h2 className="text-sm font-bold text-admin-danger">Delete "{forceDeleteTarget.channel.key}"?</h2>
            <p className="mt-2 text-[13.5px] text-admin-muted">{forceDeleteTarget.message}</p>
            <p className="mt-2 text-[13.5px] text-admin-muted">
              This permanently erases those users' chat history. Type the channel's key,{" "}
              <span className="font-semibold text-admin-fg">{forceDeleteTarget.channel.key}</span>, to confirm.
            </p>
            <input
              autoFocus
              value={forceDeleteInput}
              onChange={(e) => setForceDeleteInput(e.target.value)}
              placeholder={forceDeleteTarget.channel.key}
              className={`${s.input} mt-3 w-full`}
            />
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" onClick={() => setForceDeleteTarget(null)} className={s.btnSecondary}>
                Cancel
              </button>
              <button
                type="button"
                disabled={forceDeleteInput !== forceDeleteTarget.channel.key || forceDeleting}
                onClick={confirmForceDelete}
                className="rounded-lg bg-admin-danger px-3.5 py-2 text-[13px] font-semibold text-white hover:bg-red-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {forceDeleting ? "Deleting…" : "Delete permanently"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
