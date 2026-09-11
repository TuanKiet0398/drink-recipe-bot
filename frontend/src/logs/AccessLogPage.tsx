import { useEffect, useState } from "react";
import { apiFetch } from "../api/client";
import * as s from "../layout/styles";

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

const filterLabel = "flex flex-col gap-1 text-xs font-semibold text-admin-muted";

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
    <div className="flex flex-col gap-4">
      <div>
        <h1 className={s.pageTitle}>Access Log</h1>
        <p className={s.pageDescription}>Messages exchanged between users and the bot.</p>
      </div>
      {error && (
        <p role="alert" className={s.alertError}>
          {error}
        </p>
      )}
      <div className="flex flex-wrap items-end gap-2.5">
        <label className={filterLabel}>
          Role
          <select
            aria-label="Role"
            value={filters.role}
            onChange={(e) => updateFilter({ role: e.target.value })}
            className={s.input}
          >
            <option value="">All roles</option>
            <option value="user">User</option>
            <option value="assistant">Assistant</option>
          </select>
        </label>
        <label className={filterLabel}>
          Customer
          <select
            aria-label="Customer"
            value={filters.telegramUserId}
            onChange={(e) => updateFilter({ telegramUserId: e.target.value })}
            className={s.input}
          >
            <option value="">All customers</option>
            {users.map((u) => (
              <option key={u.id} value={u.telegram_user_id}>
                {u.telegram_user_id}
              </option>
            ))}
          </select>
        </label>
        <label className={filterLabel}>
          From
          <input
            aria-label="From"
            type="date"
            value={filters.fromDate}
            onChange={(e) => updateFilter({ fromDate: e.target.value })}
            className={s.input}
          />
        </label>
        <label className={filterLabel}>
          To
          <input
            aria-label="To"
            type="date"
            value={filters.toDate}
            onChange={(e) => updateFilter({ toDate: e.target.value })}
            className={s.input}
          />
        </label>
        <button onClick={() => updateFilter(EMPTY_FILTERS)} className={s.btnSecondary}>
          Clear filters
        </button>
      </div>
      <div className={`${s.card} overflow-x-auto`}>
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
                <td colSpan={4} className={s.emptyCell}>
                  Loading access log…
                </td>
              </tr>
            ) : entries.length === 0 ? (
              <tr>
                <td colSpan={4} className={s.emptyCell}>
                  {hasActiveFilters
                    ? "No access log entries match these filters."
                    : "No access log entries yet."}
                </td>
              </tr>
            ) : (
              entries.map((entry) => (
                <tr key={entry.id}>
                  <td className="font-semibold">{entry.telegram_user_id}</td>
                  <td>
                    <span className={s.badgeNeutral}>{entry.role}</span>
                  </td>
                  <td className="max-w-[360px] truncate" title={entry.content}>
                    {entry.content}
                  </td>
                  <td className="text-admin-muted">{entry.created_at}</td>
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
