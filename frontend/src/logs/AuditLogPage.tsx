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

  async function load(currentOffset: number): Promise<void> {
    try {
      const data = await apiFetch<AuditLogEntry[]>(
        `/admin/logs/audit?limit=${PAGE_SIZE}&offset=${currentOffset}`
      );
      setEntries(data);
      setError(null);
    } catch {
      setError("Failed to load audit log");
    }
  }

  useEffect(() => {
    load(offset);
  }, [offset]);

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold">Audit Log</h1>
      {error && (
        <p role="alert" className="text-red-600">
          {error}
        </p>
      )}
      <table className="w-full text-left border-collapse">
        <thead>
          <tr>
            <th>Action</th>
            <th>Target</th>
            <th>IP</th>
            <th>When</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr key={entry.id}>
              <td>{entry.action}</td>
              <td>{entry.target}</td>
              <td>{entry.ip}</td>
              <td>{entry.created_at}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex gap-2">
        <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
          Previous
        </button>
        <button
          disabled={!error && entries.length < PAGE_SIZE}
          onClick={() => setOffset(offset + PAGE_SIZE)}
        >
          Next
        </button>
      </div>
    </div>
  );
}
