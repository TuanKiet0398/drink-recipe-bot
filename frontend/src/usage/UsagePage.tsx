import { useEffect, useState } from "react";
import { apiFetch } from "../api/client";

interface UsageEntry {
  id: number;
  user_id: number | null;
  call_type: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number | null;
  total_tokens: number;
  created_at: string;
}

interface ModelBreakdown {
  model: string;
  calls: number;
  total_tokens: number;
  estimated_cost_usd: number;
}

interface UsageSummary {
  total_calls: number;
  total_tokens: number;
  estimated_cost_usd: number;
  by_model: ModelBreakdown[];
}

const PAGE_SIZE = 20;

const EMPTY_SUMMARY: UsageSummary = { total_calls: 0, total_tokens: 0, estimated_cost_usd: 0, by_model: [] };

export function UsagePage() {
  const [summary, setSummary] = useState<UsageSummary>(EMPTY_SUMMARY);
  const [entries, setEntries] = useState<UsageEntry[]>([]);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function loadSummary(): Promise<void> {
    try {
      const data = await apiFetch<UsageSummary>("/admin/usage/summary");
      setSummary(data);
    } catch {
      /* summary is supplementary; the list's error banner is the primary signal */
    }
  }

  useEffect(() => {
    loadSummary();
  }, []);

  async function load(currentOffset: number): Promise<void> {
    try {
      const data = await apiFetch<UsageEntry[]>(`/admin/usage?limit=${PAGE_SIZE}&offset=${currentOffset}`);
      setEntries(data);
      setError(null);
    } catch {
      setError("Failed to load usage");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(offset);
  }, [offset]);

  async function deleteEntry(id: number): Promise<void> {
    try {
      await apiFetch(`/admin/usage/${id}`, { method: "DELETE" });
      await load(offset);
      await loadSummary();
    } catch {
      setError("Failed to delete entry");
    }
  }

  async function clearAll(): Promise<void> {
    if (!confirm("Delete all usage records? This cannot be undone.")) return;
    try {
      await apiFetch("/admin/usage", { method: "DELETE" });
      setOffset(0);
      await load(0);
      await loadSummary();
    } catch {
      setError("Failed to clear usage");
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Usage</h1>
          <p className="text-sm text-muted-foreground">OpenAI token usage and estimated cost.</p>
        </div>
        <button
          onClick={clearAll}
          className="rounded-md border border-red-200 px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50"
        >
          Clear all
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-border bg-card p-5 shadow-card">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Total Calls</h2>
          <p className="mt-1 text-2xl font-semibold text-foreground">{summary.total_calls}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-5 shadow-card">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Total Tokens</h2>
          <p className="mt-1 text-2xl font-semibold text-foreground">{summary.total_tokens}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-5 shadow-card">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Est. Cost</h2>
          <p className="mt-1 text-2xl font-semibold text-foreground">${summary.estimated_cost_usd}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-5 shadow-card">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">By Model</h2>
          <ul className="mt-1 flex flex-col gap-1">
            {summary.by_model.length === 0 ? (
              <li className="text-sm text-muted-foreground">No data yet</li>
            ) : (
              summary.by_model.map((m) => (
                <li key={m.model} className="text-sm text-foreground">
                  <span>{m.model}</span>: {m.total_tokens} tok
                </li>
              ))
            )}
          </ul>
        </div>
      </div>

      {error && (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      <div className="overflow-x-auto rounded-lg border border-border bg-card shadow-card">
        <table className="w-full">
          <thead>
            <tr>
              <th>User</th>
              <th>Call Type</th>
              <th>Model</th>
              <th>Prompt</th>
              <th>Completion</th>
              <th>Total</th>
              <th>When</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={8} className="py-8 text-center text-sm text-muted-foreground">
                  Loading usage…
                </td>
              </tr>
            ) : entries.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-8 text-center text-sm text-muted-foreground">
                  No usage recorded yet.
                </td>
              </tr>
            ) : (
              entries.map((entry) => (
                <tr key={entry.id}>
                  <td className="text-muted-foreground">{entry.user_id ?? "—"}</td>
                  <td>
                    <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
                      {entry.call_type}
                    </span>
                  </td>
                  <td className="font-medium text-foreground">{entry.model}</td>
                  <td>{entry.prompt_tokens}</td>
                  <td>{entry.completion_tokens ?? "—"}</td>
                  <td>{entry.total_tokens}</td>
                  <td className="text-muted-foreground">{entry.created_at}</td>
                  <td>
                    <button
                      onClick={() => deleteEntry(entry.id)}
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

      <div className="flex gap-2">
        <button
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          className="rounded-md border border-border bg-card px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
        >
          Previous
        </button>
        <button
          disabled={!error && entries.length < PAGE_SIZE}
          onClick={() => setOffset(offset + PAGE_SIZE)}
          className="rounded-md border border-border bg-card px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </div>
  );
}
