import { useEffect, useState } from "react";
import { apiFetch } from "../api/client";
import * as s from "../layout/styles";

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

// Validated categorical palette (dataviz skill reference), fixed order —
// never cycled or reassigned when the model list changes.
const MODEL_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"];

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function TokensByModel({ byModel }: { byModel: ModelBreakdown[] }) {
  const total = byModel.reduce((sum, m) => sum + m.total_tokens, 0);
  const sorted = [...byModel].sort((a, b) => b.total_tokens - a.total_tokens);

  return (
    <div className={`${s.card} p-[18px]`}>
      <h2 className={`${s.sectionLabel} mb-3`}>Tokens by Model</h2>
      {sorted.length === 0 ? (
        <p className="text-[13.5px] text-admin-muted">No usage recorded yet.</p>
      ) : (
        <ul className="flex flex-col gap-2.5">
          {sorted.map((m, i) => {
            const pct = total > 0 ? Math.round((m.total_tokens / total) * 100) : 0;
            const color = MODEL_COLORS[i % MODEL_COLORS.length];
            return (
              <li
                key={m.model}
                className="flex items-center gap-2.5"
                title={`${m.calls} calls · $${m.estimated_cost_usd.toFixed(4)}`}
              >
                <span aria-hidden="true" className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: color }} />
                <span className="w-[180px] shrink-0 truncate text-[13.5px] font-semibold text-admin-fg">{m.model}</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-[#F1EFE7]">
                  <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
                </div>
                <span className="w-[120px] shrink-0 text-right text-[12.5px] tabular-nums text-admin-muted">
                  {formatTokens(m.total_tokens)} · {pct}%
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

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

  const stats = [
    { label: "Total Calls", value: summary.total_calls },
    { label: "Total Tokens", value: summary.total_tokens },
    { label: "Est. Cost", value: `$${summary.estimated_cost_usd}` },
  ];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className={s.pageTitle}>Usage</h1>
          <p className={s.pageDescription}>OpenAI token usage and estimated cost.</p>
        </div>
        <button onClick={clearAll} className={s.btnDanger}>
          Clear all
        </button>
      </div>

      <div className="grid grid-cols-[repeat(auto-fit,minmax(160px,1fr))] gap-3.5">
        {stats.map((stat) => (
          <div key={stat.label} className={`${s.card} px-[18px] py-4`}>
            <h2 className={s.sectionLabel}>{stat.label}</h2>
            <p className="mt-1.5 text-2xl font-bold text-admin-fg">{stat.value}</p>
          </div>
        ))}
      </div>

      <TokensByModel byModel={summary.by_model} />

      {error && (
        <p role="alert" className={s.alertError}>
          {error}
        </p>
      )}

      <div className={`${s.card} overflow-x-auto`}>
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
                <td colSpan={8} className={s.emptyCell}>
                  Loading usage…
                </td>
              </tr>
            ) : entries.length === 0 ? (
              <tr>
                <td colSpan={8} className={s.emptyCell}>
                  No usage recorded yet.
                </td>
              </tr>
            ) : (
              entries.map((entry) => (
                <tr key={entry.id}>
                  <td className="text-admin-muted">{entry.user_id ?? "—"}</td>
                  <td>
                    <span className={s.badgeNeutral}>{entry.call_type}</span>
                  </td>
                  <td className="font-semibold">{entry.model}</td>
                  <td>{entry.prompt_tokens}</td>
                  <td>{entry.completion_tokens ?? "—"}</td>
                  <td>{entry.total_tokens}</td>
                  <td className="text-admin-muted">{entry.created_at}</td>
                  <td>
                    <button onClick={() => deleteEntry(entry.id)} className={s.btnGhostDanger}>
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
          className={s.btnSecondary}
        >
          Previous
        </button>
        <button
          disabled={!error && entries.length < PAGE_SIZE}
          onClick={() => setOffset(offset + PAGE_SIZE)}
          className={s.btnSecondary}
        >
          Next
        </button>
      </div>
    </div>
  );
}
