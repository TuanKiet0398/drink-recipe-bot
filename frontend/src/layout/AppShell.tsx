import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { BrandIcon } from "../components/BrandIcon";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `block rounded-md px-3 py-2 text-sm font-medium transition-colors ${
    isActive ? "bg-primary text-white" : "text-foreground/70 hover:bg-primary-light hover:text-primary-dark"
  }`;

export function AppShell() {
  const { logout } = useAuth();

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-56 shrink-0 flex-col border-r border-border bg-card px-4 py-5 shadow-card">
        <span className="mb-6 flex items-center gap-2 px-3 text-sm font-semibold text-primary-dark">
          <BrandIcon />
          Shop Assistant Admin
        </span>
        <nav className="flex flex-1 flex-col gap-1">
          <NavLink to="/panel/usage" className={linkClass}>
            Usage
          </NavLink>
          <NavLink to="/panel/docs" className={linkClass}>
            Documents
          </NavLink>
          <NavLink to="/panel/users" className={linkClass}>
            Users
          </NavLink>
          <NavLink to="/panel/logs/access" className={linkClass}>
            Access Log
          </NavLink>
          <NavLink to="/panel/logs/audit" className={linkClass}>
            Audit Log
          </NavLink>
          <NavLink to="/panel/channels" className={linkClass}>
            Channels
          </NavLink>
          <NavLink to="/panel/settings" className={linkClass}>
            Settings
          </NavLink>
          <NavLink to="/panel/personality" className={linkClass}>
            Personality
          </NavLink>
        </nav>
        <button
          onClick={logout}
          className="rounded-md px-3 py-2 text-left text-sm font-medium text-foreground/60 hover:bg-muted hover:text-foreground"
        >
          Log out
        </button>
      </aside>
      <main className="flex-1 overflow-y-auto p-6">
        <Outlet />
      </main>
    </div>
  );
}
