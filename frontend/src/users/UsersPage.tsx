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

  async function loadUsers(): Promise<void> {
    try {
      const data = await apiFetch<AdminUser[]>("/admin/users");
      setUsers(data);
    } catch {
      setError("Failed to load users");
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
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold">Users</h1>
      {error && (
        <p role="alert" className="text-red-600">
          {error}
        </p>
      )}
      <table className="w-full text-left border-collapse">
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
          {users.map((user) => (
            <tr key={user.id}>
              <td>{user.telegram_user_id}</td>
              <td>{user.message_count}</td>
              <td>{user.favourites.join(", ") || "—"}</td>
              <td>{user.blocked ? "Blocked" : "Active"}</td>
              <td>
                <button onClick={() => toggleBlock(user)} className="underline">
                  {user.blocked ? "Unblock" : "Block"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
