import { useEffect, useState } from "react";
import { apiFetch } from "../api/client";
import * as s from "../layout/styles";

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
    return s.badgeDanger;
  }
  if (action === "login_failed") {
    return s.badgeWarning;
  }
  return s.badgeSuccess;
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
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className={s.pageTitle}>Audit Log</h1>
          <p className={s.pageDescription}>Admin actions taken in this panel.</p>
        </div>
        <button onClick={clearAll} className={s.btnDanger}>
          Clear all
        </button>
      </div>

      <div className="flex flex-wrap gap-2.5">
        <select
          value={actionFilter}
          onChange={(e) => {
            setOffset(0);
            setActionFilter(e.target.value);
          }}
          className={s.input}
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
          className={`${s.input} min-w-[220px] flex-1`}
        />
      </div>

      {error && (
        <p role="alert" className={s.alertError}>
          {error}
        </p>
      )}
      <div className={`${s.card} overflow-x-auto`}>
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
                <td colSpan={5} className={s.emptyCell}>
                  Loading audit log…
                </td>
              </tr>
            ) : entries.length === 0 ? (
              <tr>
                <td colSpan={5} className={s.emptyCell}>
                  No audit log entries yet.
                </td>
              </tr>
            ) : (
              entries.map((entry) => (
                <tr key={entry.id}>
                  <td>
                    <span className={actionBadgeClass(entry.action)}>{entry.action}</span>
                  </td>
                  <td className="font-semibold">{entry.target}</td>
                  <td className="text-admin-muted">{entry.ip}</td>
                  <td className="text-admin-muted">
                    <div>{entry.created_at}</div>
                    <div className="text-xs">{relativeTime(entry.created_at)}</div>
                  </td>
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
