import { useEffect, useState } from "react";
import { apiFetch } from "../api/client";

interface AccessLogEntry {
  id: number;
  telegram_user_id: string;
  role: string;
  content: string;
  created_at: string;
}

const PAGE_SIZE = 20;

export function AccessLogPage() {
  const [entries, setEntries] = useState<AccessLogEntry[]>([]);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);

  async function load(currentOffset: number): Promise<void> {
    try {
      const data = await apiFetch<AccessLogEntry[]>(
        `/admin/logs/access?limit=${PAGE_SIZE}&offset=${currentOffset}`
      );
      setEntries(data);
    } catch {
      setError("Failed to load access log");
    }
  }

  useEffect(() => {
    load(offset);
  }, [offset]);

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold">Access Log</h1>
      {error && (
        <p role="alert" className="text-red-600">
          {error}
        </p>
      )}
      <table className="w-full text-left border-collapse">
        <thead>
          <tr>
            <th>User</th>
            <th>Role</th>
            <th>Content</th>
            <th>When</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr key={entry.id}>
              <td>{entry.telegram_user_id}</td>
              <td>{entry.role}</td>
              <td>{entry.content}</td>
              <td>{entry.created_at}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex gap-2">
        <button
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
        >
          Previous
        </button>
        <button
          disabled={entries.length < PAGE_SIZE}
          onClick={() => setOffset(offset + PAGE_SIZE)}
        >
          Next
        </button>
      </div>
    </div>
  );
}
