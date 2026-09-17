import { useEffect, useState } from "react";
import { apiFetch } from "../api/client";
import * as s from "../layout/styles";

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

  async function deleteUser(user: AdminUser): Promise<void> {
    if (
      !window.confirm(
        `Permanently delete "${user.telegram_user_id}"? Their messages, favourites, notes and recommendation history are all erased — this cannot be undone.`
      )
    ) {
      return;
    }
    setError(null);
    try {
      await apiFetch(`/admin/users/${user.id}`, { method: "DELETE" });
      await loadUsers();
    } catch {
      setError("Failed to delete user");
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className={s.pageTitle}>Users</h1>
        <p className={s.pageDescription}>Telegram users who have messaged the bot.</p>
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
                <td colSpan={5} className={s.emptyCell}>
                  Loading users…
                </td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={5} className={s.emptyCell}>
                  No users yet — they will appear once someone messages the bot.
                </td>
              </tr>
            ) : (
              users.map((user) => (
                <tr key={user.id}>
                  <td className="font-semibold">{user.telegram_user_id}</td>
                  <td>{user.message_count}</td>
                  <td className="text-admin-muted">{user.favourites.join(", ") || "—"}</td>
                  <td>
                    <span className={user.blocked ? s.badgeDanger : s.badgeSuccess}>
                      {user.blocked ? "Blocked" : "Active"}
                    </span>
                  </td>
                  <td className="flex gap-2">
                    <button onClick={() => toggleBlock(user)} className={s.btnGhostPrimary}>
                      {user.blocked ? "Unblock" : "Block"}
                    </button>
                    <button onClick={() => deleteUser(user)} className={s.btnDanger}>
                      Delete
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
