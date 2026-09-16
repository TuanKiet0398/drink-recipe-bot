import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { BrandIcon } from "../components/BrandIcon";

const ADMIN_NAV_GROUPS = [
  {
    label: "Main",
    links: [
      { to: "/panel/chat", name: "Chat" },
      { to: "/panel/usage", name: "Usage" },
    ],
  },
  {
    label: "Bot",
    links: [
      { to: "/panel/docs", name: "Documents" },
      { to: "/panel/personality", name: "Personality" },
      { to: "/panel/channels", name: "Channels" },
    ],
  },
  {
    label: "Monitoring",
    links: [
      { to: "/panel/users", name: "Users" },
      { to: "/panel/logs/access", name: "Access Log" },
      { to: "/panel/logs/audit", name: "Audit Log" },
    ],
  },
  {
    label: "System",
    links: [{ to: "/panel/settings", name: "Settings" }],
  },
];

const CUSTOMER_NAV_GROUPS = [
  {
    label: "Main",
    links: [{ to: "/panel/chat", name: "Chat" }],
  },
];

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `block rounded-lg px-2.5 py-2 text-[13px] font-semibold transition-colors ${
    isActive
      ? "bg-admin-primary text-white"
      : "text-admin-fg-2 hover:bg-admin-primary-light hover:text-admin-primary-dark"
  }`;

export function AppShell() {
  const { logout, username, isAdmin } = useAuth();
  const navGroups = isAdmin ? ADMIN_NAV_GROUPS : CUSTOMER_NAV_GROUPS;

  return (
    <div className="flex min-h-screen bg-admin-bg text-admin-fg">
      <aside className="flex w-[232px] shrink-0 flex-col border-r border-admin-border bg-white px-3.5 py-5">
        <div className="mb-3.5 flex items-center gap-2 border-b border-admin-divider px-2 pb-[18px]">
          <BrandIcon className="h-5 w-5 text-admin-primary-dark" />
          <div className="flex flex-col leading-tight">
            <span className="text-[13px] font-bold text-admin-primary-dark">Shop Assistant</span>
            <span className="text-[11px] text-admin-muted">{isAdmin ? "Admin panel" : "Chat"}</span>
          </div>
        </div>

        <div className="mb-4 flex items-center gap-2 rounded-lg bg-admin-bg p-2">
          <span
            aria-hidden="true"
            className="flex h-[26px] w-[26px] items-center justify-center rounded-full bg-admin-primary text-[11px] font-bold text-white"
          >
            {(username ?? "?").charAt(0).toUpperCase()}
          </span>
          <div className="flex flex-col leading-tight">
            <span className="text-xs font-semibold text-admin-fg">{username}</span>
            <span className="text-[11px] text-admin-muted">Signed in</span>
          </div>
        </div>

        <nav className="flex flex-1 flex-col gap-4 overflow-y-auto">
          {navGroups.map((group) => (
            <div key={group.label} className="flex flex-col gap-0.5">
              <span className="mb-1 px-2.5 text-[10.5px] font-bold uppercase tracking-[0.06em] text-admin-label">
                {group.label}
              </span>
              {group.links.map((link) => (
                <NavLink key={link.to} to={link.to} className={linkClass}>
                  {link.name}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <button
          onClick={logout}
          className="mt-3.5 border-t border-admin-divider px-2.5 py-2 text-left text-[13px] font-medium text-admin-muted hover:bg-admin-bg hover:text-admin-fg"
        >
          Log out
        </button>
      </aside>
      <main className="flex-1 overflow-y-auto px-8 py-[26px]">
        <div className="max-w-[1180px]">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
