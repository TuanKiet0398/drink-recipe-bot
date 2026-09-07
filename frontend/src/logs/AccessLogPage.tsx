import { useEffect, useState } from "react";
import { apiFetch } from "../api/client";

interface AccessLogEntry {
  id: number;
  telegram_user_id: string;
  role: string;
  content: string;
  created_at: string;
}

interface AdminUser {
  id: number;
  telegram_user_id: string;
}

interface Filters {
  role: string;
  telegramUserId: string;
  fromDate: string;
  toDate: string;
}

const PAGE_SIZE = 20;

const EMPTY_FILTERS: Filters = { role: "", telegramUserId: "", fromDate: "", toDate: "" };

function buildQuery(offset: number, filters: Filters): string {
  const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
  if (filters.role) params.set("role", filters.role);
  if (filters.telegramUserId) params.set("telegram_user_id", filters.telegramUserId);
  if (filters.fromDate) params.set("from_date", filters.fromDate);
  if (filters.toDate) params.set("to_date", filters.toDate);
  return params.toString();
}

const selectClass =
  "rounded-md border border-border bg-card px-2 py-1.5 text-sm text-foreground focus:border-primary focus:outline-none";

export function AccessLogPage() {
  const [entries, setEntries] = useState<AccessLogEntry[]>([]);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [users, setUsers] = useState<AdminUser[]>([]);

  async function load(currentOffset: number, currentFilters: Filters): Promise<void> {
    try {
      const data = await apiFetch<AccessLogEntry[]>(`/admin/logs/access?${buildQuery(currentOffset, currentFilters)}`);
      setEntries(data);
      setError(null);
    } catch {
      setError("Failed to load access log");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load(offset, filters);
  }, [offset, filters]);

  useEffect(() => {
    apiFetch<AdminUser[]>("/admin/users")
      .then(setUsers)
      .catch(() => setUsers([]));
  }, []);

  // Every filter change resets to the first page. Without this, narrowing the
  // filter while on page 3 shows an empty table.
  function updateFilter(patch: Partial<Filters>): void {
    setLoading(true);
    setOffset(0);
    setFilters((current) => ({ ...current, ...patch }));
  }

  const hasActiveFilters = Object.values(filters).some(Boolean);

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Access Log</h1>
        <p className="text-sm text-muted-foreground">Messages exchanged between users and the bot.</p>
      </div>
      {error && (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs font-medium text-muted-foreground">
          Role
          <select
            aria-label="Role"
            value={filters.role}
            onChange={(e) => updateFilter({ role: e.target.value })}
            className={selectClass}
          >
            <option value="">All roles</option>
            <option value="user">User</option>
            <option value="assistant">Assistant</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-muted-foreground">
          Customer
          <select
            aria-label="Customer"
            value={filters.telegramUserId}
            onChange={(e) => updateFilter({ telegramUserId: e.target.value })}
            className={selectClass}
          >
            <option value="">All customers</option>
            {users.map((u) => (
              <option key={u.id} value={u.telegram_user_id}>
                {u.telegram_user_id}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-muted-foreground">
          From
          <input
            aria-label="From"
            type="date"
            value={filters.fromDate}
            onChange={(e) => updateFilter({ fromDate: e.target.value })}
            className={selectClass}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs font-medium text-muted-foreground">
          To
          <input
            aria-label="To"
            type="date"
            value={filters.toDate}
            onChange={(e) => updateFilter({ toDate: e.target.value })}
            className={selectClass}
          />
        </label>
        <button
          onClick={() => updateFilter(EMPTY_FILTERS)}
          className="rounded-md border border-border bg-card px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted"
        >
          Clear filters
        </button>
      </div>
      <div className="overflow-x-auto rounded-lg border border-border bg-card shadow-card">
        <table className="w-full">
          <thead>
            <tr>
              <th>User</th>
              <th>Role</th>
              <th>Content</th>
              <th>When</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={4} className="py-8 text-center text-sm text-muted-foreground">
                  Loading access log…
                </td>
              </tr>
            ) : entries.length === 0 ? (
              <tr>
                <td colSpan={4} className="py-8 text-center text-sm text-muted-foreground">
                  {hasActiveFilters
                    ? "No access log entries match these filters."
                    : "No access log entries yet."}
                </td>
              </tr>
            ) : (
              entries.map((entry) => (
                <tr key={entry.id}>
                  <td className="font-medium text-foreground">{entry.telegram_user_id}</td>
                  <td>
                    <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
                      {entry.role}
                    </span>
                  </td>
                  <td className="max-w-md truncate" title={entry.content}>
                    {entry.content}
                  </td>
                  <td className="text-muted-foreground">{entry.created_at}</td>
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
