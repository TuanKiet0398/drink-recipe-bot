import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-2 rounded ${isActive ? "bg-green-700 text-white" : "text-green-900"}`;

export function AppShell() {
  const { logout } = useAuth();

  return (
    <div>
      <nav className="flex items-center gap-2 border-b px-4 py-2">
        <NavLink to="/docs" className={linkClass}>
          Documents
        </NavLink>
        <NavLink to="/users" className={linkClass}>
          Users
        </NavLink>
        <NavLink to="/logs/access" className={linkClass}>
          Access Log
        </NavLink>
        <NavLink to="/logs/audit" className={linkClass}>
          Audit Log
        </NavLink>
        <button onClick={logout} className="ml-auto text-sm underline">
          Log out
        </button>
      </nav>
      <main className="p-4">
        <Outlet />
      </main>
    </div>
  );
}
