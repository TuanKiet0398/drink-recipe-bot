import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
    isActive ? "bg-primary text-white" : "text-foreground/70 hover:bg-primary-light hover:text-primary-dark"
  }`;

export function AppShell() {
  const { logout } = useAuth();

  return (
    <div className="min-h-screen">
      <nav className="flex items-center gap-1 border-b border-border bg-card px-6 py-3 shadow-card">
        <span className="mr-4 flex items-center gap-2 text-sm font-semibold text-primary-dark">
          <span aria-hidden="true">🍵</span>
          Matcha Admin
        </span>
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
        <button
          onClick={logout}
          className="ml-auto rounded-md px-3 py-1.5 text-sm font-medium text-foreground/60 hover:bg-muted hover:text-foreground"
        >
          Log out
        </button>
      </nav>
      <main className="mx-auto max-w-6xl p-6">
        <Outlet />
      </main>
    </div>
  );
}
