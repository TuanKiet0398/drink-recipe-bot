import { useEffect, useState } from "react";
import { apiFetch } from "../api/client";

interface AuditLogEntry {
  id: number;
  action: string;
  target: string;
  ip: string;
  created_at: string;
}

const PAGE_SIZE = 20;

function actionBadgeClass(action: string): string {
  if (action.startsWith("delete_") || action.startsWith("clear_")) {
    return "bg-red-50 text-red-700";
  }
  if (action === "login_failed") {
    return "bg-amber-50 text-amber-700";
  }
  return "bg-primary-light text-primary-dark";
}

function relativeTime(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const diffSec = Math.round(diffMs / 1000);
  if (diffSec < 60) return "just now";
  const diffMin = Math.round(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHour = Math.round(diffMin / 60);
  if (diffHour < 24) return `${diffHour}h ago`;
  const diffDay = Math.round(diffHour / 24);
  return `${diffDay}d ago`;
}

export function AuditLogPage() {
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [actions, setActions] = useState<string[]>([]);
  const [actionFilter, setActionFilter] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch<string[]>("/admin/logs/audit/actions")
      .then((data) => setActions(data.sort()))
      .catch(() => {
        /* the filter dropdown is supplementary; the list's error banner is the primary signal */
      });
  }, []);

  async function load(currentOffset: number, action: string, q: string): Promise<void> {
    try {
      const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(currentOffset) });
      if (action) params.set("action", action);
      if (q) params.set("q", q);
      const data = await apiFetch<AuditLogEntry[]>(`/admin/logs/audit?${params}`);
      setEntries(data);
      setError(null);
    } catch {
      setError("Failed to load audit log");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(offset, actionFilter, search);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offset, actionFilter, search]);

  async function deleteEntry(id: number): Promise<void> {
    try {
      await apiFetch(`/admin/logs/audit/${id}`, { method: "DELETE" });
      await load(offset, actionFilter, search);
    } catch {
      setError("Failed to delete entry");
    }
  }

  async function clearAll(): Promise<void> {
    if (!confirm("Delete all audit log entries? This cannot be undone.")) return;
    try {
      await apiFetch("/admin/logs/audit", { method: "DELETE" });
      setOffset(0);
      await load(0, actionFilter, search);
    } catch {
      setError("Failed to clear audit log");
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-foreground">Audit Log</h1>
          <p className="text-sm text-muted-foreground">Admin actions taken in this panel.</p>
        </div>
        <button
          onClick={clearAll}
          className="rounded-md border border-red-200 px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50"
        >
          Clear all
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        <select
          value={actionFilter}
          onChange={(e) => {
            setOffset(0);
            setActionFilter(e.target.value);
          }}
          className="rounded-md border border-border bg-card px-3 py-1.5 text-sm text-foreground"
        >
          <option value="">All actions</option>
          {actions.map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
        <input
          value={search}
          onChange={(e) => {
            setOffset(0);
            setSearch(e.target.value);
          }}
          placeholder="Search target or IP…"
          className="min-w-[220px] flex-1 rounded-md border border-border bg-card px-3 py-1.5 text-sm text-foreground"
        />
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
              <th>Action</th>
              <th>Target</th>
              <th>IP</th>
              <th>When</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="py-8 text-center text-sm text-muted-foreground">
                  Loading audit log…
                </td>
              </tr>
            ) : entries.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-8 text-center text-sm text-muted-foreground">
                  No audit log entries yet.
                </td>
              </tr>
            ) : (
              entries.map((entry) => (
                <tr key={entry.id}>
                  <td>
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${actionBadgeClass(entry.action)}`}
                    >
                      {entry.action}
                    </span>
                  </td>
                  <td className="font-medium text-foreground">{entry.target}</td>
                  <td className="text-muted-foreground">{entry.ip}</td>
                  <td className="text-muted-foreground">
                    <div>{entry.created_at}</div>
                    <div className="text-xs">{relativeTime(entry.created_at)}</div>
                  </td>
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
