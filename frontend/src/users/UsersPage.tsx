import { useEffect, useState } from "react";
import { apiFetch } from "../api/client";

interface AdminUser {
  id: number;
  telegram_user_id: string;
  first_seen: string;
  message_count: number;
  favourites: string[];
  blocked: boolean;
}

export function UsersPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  async function loadUsers(): Promise<void> {
    try {
      const data = await apiFetch<AdminUser[]>("/admin/users");
      setUsers(data);
    } catch {
      setError("Failed to load users");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadUsers();
  }, []);

  async function toggleBlock(user: AdminUser): Promise<void> {
    setError(null);
    try {
      const action = user.blocked ? "unblock" : "block";
      await apiFetch(`/admin/users/${user.id}/${action}`, { method: "POST" });
      await loadUsers();
    } catch {
      setError("Failed to update user");
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Users</h1>
        <p className="text-sm text-muted-foreground">Telegram users who have messaged the bot.</p>
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
              <th>Telegram ID</th>
              <th>Messages</th>
              <th>Favourites</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="py-8 text-center text-sm text-muted-foreground">
                  Loading users…
                </td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-8 text-center text-sm text-muted-foreground">
                  No users yet — they will appear once someone messages the bot.
                </td>
              </tr>
            ) : (
              users.map((user) => (
                <tr key={user.id}>
                  <td className="font-medium text-foreground">{user.telegram_user_id}</td>
                  <td>{user.message_count}</td>
                  <td className="text-muted-foreground">{user.favourites.join(", ") || "—"}</td>
                  <td>
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                        user.blocked ? "bg-red-50 text-red-700" : "bg-primary-light text-primary-dark"
                      }`}
                    >
                      {user.blocked ? "Blocked" : "Active"}
                    </span>
                  </td>
                  <td>
                    <button
                      onClick={() => toggleBlock(user)}
                      className="rounded px-2 py-1 text-sm font-medium text-primary hover:bg-primary-light"
                    >
                      {user.blocked ? "Unblock" : "Block"}
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
