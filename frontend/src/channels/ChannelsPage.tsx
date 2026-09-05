import { useEffect, useState } from "react";
import { apiFetch } from "../api/client";

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

export function ChannelsPage() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);

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
      await loadChannels();
    } catch {
      setError("Failed to delete channel");
    }
  }

  async function createChannel(e: React.FormEvent): Promise<void> {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await apiFetch("/admin/channels", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      setForm(EMPTY_FORM);
      setShowForm(false);
      await loadChannels();
    } catch {
      setError("Failed to create channel");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Channels</h1>
          <p className="text-sm text-muted-foreground">Chat platform connections (Telegram, and more soon).</p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-dark"
        >
          + Add Channel
        </button>
      </div>

      {error && (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {showForm && (
        <form onSubmit={createChannel} className="flex flex-col gap-3 rounded-lg border border-border bg-card p-5 shadow-card">
          <div>
            <label className="block text-sm font-medium text-foreground">Key</label>
            <input
              required
              value={form.key}
              onChange={(e) => setForm({ ...form, key: e.target.value })}
              placeholder="my-telegram-bot"
              className="mt-1 w-full rounded-md border border-border px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground">Display Name</label>
            <input
              required
              value={form.display_name}
              onChange={(e) => setForm({ ...form, display_name: e.target.value })}
              placeholder="Sales Bot"
              className="mt-1 w-full rounded-md border border-border px-3 py-1.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground">Channel Type</label>
            <select
              value={form.channel_type}
              onChange={(e) => setForm({ ...form, channel_type: e.target.value })}
              className="mt-1 w-full rounded-md border border-border px-3 py-1.5 text-sm"
            >
              {CHANNEL_TYPES.map((t) => (
                <option key={t.value} value={t.value} disabled={!t.enabled}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-foreground">Bot Token</label>
            <input
              required
              type="password"
              value={form.bot_token}
              onChange={(e) => setForm({ ...form, bot_token: e.target.value })}
              placeholder="123456:ABC-DEF..."
              className="mt-1 w-full rounded-md border border-border px-3 py-1.5 text-sm"
            />
          </div>
          <div className="flex gap-2">
            <button
              type="submit"
              disabled={submitting}
              className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-dark disabled:opacity-50"
            >
              Create
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="rounded-md border border-border px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      <div className="overflow-x-auto rounded-lg border border-border bg-card shadow-card">
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
                <td colSpan={5} className="py-8 text-center text-sm text-muted-foreground">
                  Loading channels…
                </td>
              </tr>
            ) : channels.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-8 text-center text-sm text-muted-foreground">
                  No channels yet — add one to connect a bot.
                </td>
              </tr>
            ) : (
              channels.map((channel) => (
                <tr key={channel.id}>
                  <td className="font-medium text-foreground">{channel.key}</td>
                  <td>{channel.display_name}</td>
                  <td className="text-muted-foreground">{channel.channel_type}</td>
                  <td>
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                        channel.is_active ? "bg-primary-light text-primary-dark" : "bg-red-50 text-red-700"
                      }`}
                    >
                      {channel.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="flex gap-2">
                    <button
                      onClick={() => toggleActive(channel)}
                      className="rounded px-2 py-1 text-sm font-medium text-primary hover:bg-primary-light"
                    >
                      {channel.is_active ? "Deactivate" : "Activate"}
                    </button>
                    <button
                      onClick={() => deleteChannel(channel)}
                      className="rounded px-2 py-1 text-sm font-medium text-red-700 hover:bg-red-50"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
