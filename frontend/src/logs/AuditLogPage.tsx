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

export function AuditLogPage() {
  const [entries, setEntries] = useState<AuditLogEntry[]>([]);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function load(currentOffset: number): Promise<void> {
    try {
      const data = await apiFetch<AuditLogEntry[]>(
        `/admin/logs/audit?limit=${PAGE_SIZE}&offset=${currentOffset}`
      );
      setEntries(data);
      setError(null);
    } catch {
      setError("Failed to load audit log");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(offset);
  }, [offset]);

  async function deleteEntry(id: number): Promise<void> {
    try {
      await apiFetch(`/admin/logs/audit/${id}`, { method: "DELETE" });
      await load(offset);
    } catch {
      setError("Failed to delete entry");
    }
  }

  async function clearAll(): Promise<void> {
    if (!confirm("Delete all audit log entries? This cannot be undone.")) return;
    try {
      await apiFetch("/admin/logs/audit", { method: "DELETE" });
      setOffset(0);
      await load(0);
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
                    <span className="inline-flex items-center rounded-full bg-primary-light px-2 py-0.5 text-xs font-medium text-primary-dark">
                      {entry.action}
                    </span>
                  </td>
                  <td className="font-medium text-foreground">{entry.target}</td>
                  <td className="text-muted-foreground">{entry.ip}</td>
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
