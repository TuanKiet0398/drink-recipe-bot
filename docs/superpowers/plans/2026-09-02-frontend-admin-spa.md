# Frontend Admin SPA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the React admin SPA — login, document/recipe manager, user list with block/unblock, access log viewer, audit log viewer — as a standalone client of the backend service's `/admin/*` API. No end-user chat UI (chat is Telegram-only).

**Architecture:** Vite + React + TypeScript SPA (`frontend/`). A small `api/client.ts` wraps `fetch` with HTTP Basic Auth (credentials held in `sessionStorage`, never in a cookie or the URL). `react-router-dom` drives four protected routes (Docs, Users, Access Log, Audit Log) behind a login gate; an `AuthContext` tracks whether valid credentials are stored. Tests use Vitest + React Testing Library + MSW (Mock Service Worker) to mock the backend HTTP API — no real backend needed to run the suite.

**Tech Stack:** React 18, TypeScript, Vite, react-router-dom, Vitest, @testing-library/react, @testing-library/user-event, MSW, Tailwind CSS (utility styling only — no design-system work in this plan; see Task 9's note for a follow-up polish pass).

**Spec:** docs/superpowers/specs/2026-09-02-matcha-tea-bot-design.md

## Global Constraints

- Auth: HTTP Basic Auth against the backend's single shared admin credential. Login screen submits username/password; on success, credentials are held in `sessionStorage` for the browser session (spec: "stored in memory / sessionStorage for the session") — never persisted to `localStorage` or a cookie.
- No end-user-facing chat UI in this app — it is admin-only. Chat happens entirely in Telegram (out of scope).
- Recipes are uploaded through the exact same document upload form as any other doc — no separate "recipe" UI path.
- Backend API base URL is configurable via `VITE_API_BASE_URL` (empty string default — same-origin, matches the production nginx setup where the SPA and API share an origin).
- Four admin views: Documents (upload/list/delete), Users (list/block/unblock), Access Log (paginated), Audit Log (paginated) — all behind login.

## Backend API this plan consumes (already built and reviewed — see the backend service plan)

- `POST /admin/login` — Basic Auth; 200 `{"status": "ok"}` on success, 401 on bad credentials.
- `GET /admin/docs` — 200, array of `{id, filename, chunk_count, uploaded_at}`.
- `POST /admin/docs` — multipart `file` field; 201 `{id, filename, chunk_count}`; 400 for a rejected extension (only `.txt`/`.md` accepted); 413 for an oversized file.
- `DELETE /admin/docs/{id}` — 204; 404 if the id doesn't exist.
- `GET /admin/users` — 200, array of `{id, telegram_user_id, first_seen, message_count, favourites, blocked}`.
- `POST /admin/users/{id}/block` / `POST /admin/users/{id}/unblock` — 200 `{id, blocked}`; 404 if the id doesn't exist.
- `GET /admin/logs/access?limit=&offset=` — 200, array of `{id, telegram_user_id, role, content, created_at}`.
- `GET /admin/logs/audit?limit=&offset=` — 200, array of `{id, action, target, ip, created_at}`.
- All `/admin/*` routes are Basic Auth protected and return 401 with no body on bad/missing credentials.

---

## File Structure

```
frontend/
  package.json
  tsconfig.json
  vite.config.ts
  index.html
  postcss.config.js
  tailwind.config.js
  src/
    main.tsx                    # ReactDOM root, wraps App in AuthProvider + BrowserRouter
    App.tsx                     # Route table
    index.css                   # Tailwind directives
    api/
      client.ts                 # apiFetch, ApiError, login, credential storage helpers
    auth/
      AuthContext.tsx            # AuthProvider, useAuth
      LoginPage.tsx
      RequireAuth.tsx
    layout/
      AppShell.tsx                # Nav tabs + logout + <Outlet/>
    docs/
      DocsPage.tsx
    users/
      UsersPage.tsx
    logs/
      AccessLogPage.tsx
      AuditLogPage.tsx
  tests/
    setup.ts                     # jest-dom matchers, MSW server lifecycle
    mocks/
      server.ts                   # MSW server instance
      handlers.ts                  # Default MSW request handlers
    api/client.test.ts
    auth/LoginPage.test.tsx
    auth/RequireAuth.test.tsx
    docs/DocsPage.test.tsx
    users/UsersPage.test.tsx
    logs/AccessLogPage.test.tsx
    logs/AuditLogPage.test.tsx
    App.test.tsx
```

**Interfaces produced by this plan** (nothing downstream consumes these — this is the last plan in the sequence — but listed for clarity):

- The built SPA is a static asset bundle (`frontend/dist/` after `npm run build`) that the infra plan's nginx config serves at `/` and proxies `/admin/*` + `/webhook/telegram` to the backend.

---

### Task 1: Project scaffold (Vite + React + TS + Tailwind) + smoke test

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/postcss.config.js`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/index.css`
- Create: `frontend/tests/setup.ts`
- Test: `frontend/tests/App.test.tsx`

**Interfaces:**
- Produces: `frontend/src/App.tsx` exporting `function App(): JSX.Element` — a placeholder root component this task verifies renders; later tasks replace its contents with the real route table.

- [ ] **Step 1: Write `package.json`**

```json
{
  "name": "matcha-bot-admin",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.2"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.5.0",
    "@testing-library/react": "^16.0.1",
    "@testing-library/user-event": "^14.5.2",
    "@types/react": "^18.3.5",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "autoprefixer": "^10.4.20",
    "jsdom": "^25.0.0",
    "msw": "^2.4.9",
    "postcss": "^8.4.45",
    "tailwindcss": "^3.4.10",
    "typescript": "^5.5.4",
    "vite": "^5.4.5",
    "vitest": "^2.1.1"
  }
}
```

- [ ] **Step 2: Write `tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src", "tests"]
}
```

- [ ] **Step 3: Write `vite.config.ts`**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    globals: true,
  },
});
```

- [ ] **Step 4: Write `index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Matcha Bot Admin</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Write `postcss.config.js` and `tailwind.config.js`**

```javascript
// postcss.config.js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

```javascript
// tailwind.config.js
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
};
```

- [ ] **Step 6: Write `src/index.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 7: Write `src/App.tsx`** (placeholder — Task 8 replaces this with the real route table)

```tsx
export function App() {
  return <div>Matcha Bot Admin</div>;
}
```

- [ ] **Step 8: Write `src/main.tsx`**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 9: Write `tests/setup.ts`** (MSW server wiring added in Task 2; keep minimal here)

```typescript
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 10: Write failing test `tests/App.test.tsx`**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "../src/App";

describe("App", () => {
  it("renders the admin app root", () => {
    render(<App />);
    expect(screen.getByText("Matcha Bot Admin")).toBeInTheDocument();
  });
});
```

- [ ] **Step 11: Install deps and run test**

Run (from `frontend/`):
```bash
npm install
npm test
```
Expected: PASS (1 test)

- [ ] **Step 12: Commit**

```bash
git add frontend/package.json frontend/tsconfig.json frontend/vite.config.ts frontend/index.html frontend/postcss.config.js frontend/tailwind.config.js frontend/src frontend/tests
git commit -m "feat(frontend): scaffold Vite/React/TS admin app"
```

---

### Task 2: API client (fetch wrapper, Basic Auth, credential storage)

**Files:**
- Create: `frontend/src/api/client.ts`
- Create: `frontend/tests/mocks/server.ts`
- Create: `frontend/tests/mocks/handlers.ts`
- Modify: `frontend/tests/setup.ts`
- Test: `frontend/tests/api/client.test.ts`

**Interfaces:**
- Produces: `ApiError extends Error` (fields: `status: number`), `login(username: string, password: string): Promise<void>`, `apiFetch<T>(path: string, options?: RequestInit): Promise<T>`, `getStoredCredentials(): {username: string; password: string} | null`, `storeCredentials(username: string, password: string): void`, `clearCredentials(): void`, `authHeader(): string`

- [ ] **Step 1: Write `tests/mocks/handlers.ts`** (default handlers; individual tests override per-case with `server.use(...)`)

```typescript
import { http, HttpResponse } from "msw";

export const API_BASE = "http://localhost:3000";

export const handlers = [
  http.post(`${API_BASE}/admin/login`, ({ request }) => {
    const auth = request.headers.get("Authorization");
    if (auth === `Basic ${btoa("admin:admin")}`) {
      return HttpResponse.json({ status: "ok" });
    }
    return new HttpResponse(null, { status: 401 });
  }),
];
```

- [ ] **Step 2: Write `tests/mocks/server.ts`**

```typescript
import { setupServer } from "msw/node";
import { handlers } from "./handlers";

export const server = setupServer(...handlers);
```

- [ ] **Step 3: Update `tests/setup.ts`**

```typescript
import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./mocks/server";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

- [ ] **Step 4: Write failing test `tests/api/client.test.ts`**

```typescript
import { describe, expect, it, beforeEach } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../mocks/server";
import { API_BASE } from "../mocks/handlers";
import {
  ApiError,
  apiFetch,
  authHeader,
  clearCredentials,
  getStoredCredentials,
  login,
  storeCredentials,
} from "../../src/api/client";

beforeEach(() => {
  sessionStorage.clear();
  import.meta.env.VITE_API_BASE_URL = API_BASE;
});

describe("credential storage", () => {
  it("stores and retrieves credentials from sessionStorage", () => {
    expect(getStoredCredentials()).toBeNull();
    storeCredentials("admin", "secret");
    expect(getStoredCredentials()).toEqual({ username: "admin", password: "secret" });
    clearCredentials();
    expect(getStoredCredentials()).toBeNull();
  });

  it("builds a Basic auth header from stored credentials", () => {
    storeCredentials("admin", "secret");
    expect(authHeader()).toBe(`Basic ${btoa("admin:secret")}`);
  });

  it("throws if no credentials are stored", () => {
    expect(() => authHeader()).toThrow();
  });
});

describe("login", () => {
  it("stores credentials on success", async () => {
    await login("admin", "admin");
    expect(getStoredCredentials()).toEqual({ username: "admin", password: "admin" });
  });

  it("throws ApiError and does not store credentials on failure", async () => {
    await expect(login("admin", "wrong")).rejects.toBeInstanceOf(ApiError);
    expect(getStoredCredentials()).toBeNull();
  });
});

describe("apiFetch", () => {
  it("attaches the Basic auth header and parses JSON", async () => {
    server.use(
      http.get(`${API_BASE}/admin/docs`, ({ request }) => {
        if (request.headers.get("Authorization") !== `Basic ${btoa("admin:admin")}`) {
          return new HttpResponse(null, { status: 401 });
        }
        return HttpResponse.json([{ id: 1, filename: "a.txt" }]);
      })
    );
    storeCredentials("admin", "admin");
    const result = await apiFetch<{ id: number; filename: string }[]>("/admin/docs");
    expect(result).toEqual([{ id: 1, filename: "a.txt" }]);
  });

  it("clears credentials and throws ApiError on 401", async () => {
    server.use(http.get(`${API_BASE}/admin/docs`, () => new HttpResponse(null, { status: 401 })));
    storeCredentials("admin", "admin");
    await expect(apiFetch("/admin/docs")).rejects.toBeInstanceOf(ApiError);
    expect(getStoredCredentials()).toBeNull();
  });

  it("returns undefined for a 204 No Content response", async () => {
    server.use(http.delete(`${API_BASE}/admin/docs/1`, () => new HttpResponse(null, { status: 204 })));
    storeCredentials("admin", "admin");
    const result = await apiFetch("/admin/docs/1", { method: "DELETE" });
    expect(result).toBeUndefined();
  });
});
```

- [ ] **Step 5: Run test to verify it fails**

Run: `npm test -- tests/api/client.test.ts`
Expected: FAIL with `Cannot find module '../../src/api/client'`

- [ ] **Step 6: Write `src/api/client.ts`**

```typescript
const CREDENTIALS_KEY = "admin_credentials";

export interface Credentials {
  username: string;
  password: string;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function apiBase(): string {
  return import.meta.env.VITE_API_BASE_URL ?? "";
}

export function getStoredCredentials(): Credentials | null {
  const raw = sessionStorage.getItem(CREDENTIALS_KEY);
  if (!raw) return null;
  return JSON.parse(raw) as Credentials;
}

export function storeCredentials(username: string, password: string): void {
  sessionStorage.setItem(CREDENTIALS_KEY, JSON.stringify({ username, password }));
}

export function clearCredentials(): void {
  sessionStorage.removeItem(CREDENTIALS_KEY);
}

export function authHeader(): string {
  const creds = getStoredCredentials();
  if (!creds) {
    throw new Error("Not authenticated");
  }
  return `Basic ${btoa(`${creds.username}:${creds.password}`)}`;
}

export async function login(username: string, password: string): Promise<void> {
  const response = await fetch(`${apiBase()}/admin/login`, {
    method: "POST",
    headers: { Authorization: `Basic ${btoa(`${username}:${password}`)}` },
  });
  if (!response.ok) {
    throw new ApiError("Invalid credentials", response.status);
  }
  storeCredentials(username, password);
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`, {
    ...options,
    headers: {
      ...options.headers,
      Authorization: authHeader(),
    },
  });

  if (response.status === 401) {
    clearCredentials();
    throw new ApiError("Unauthorized", 401);
  }
  if (!response.ok) {
    const text = await response.text();
    throw new ApiError(text || response.statusText, response.status);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
```

- [ ] **Step 7: Run test to verify it passes**

Run: `npm test -- tests/api/client.test.ts`
Expected: PASS (8 tests)

- [ ] **Step 8: Commit**

```bash
git add frontend/src/api frontend/tests/mocks frontend/tests/setup.ts frontend/tests/api
git commit -m "feat(frontend): add API client with Basic Auth and credential storage"
```

---

### Task 3: AuthContext + LoginPage

**Files:**
- Create: `frontend/src/auth/AuthContext.tsx`
- Create: `frontend/src/auth/LoginPage.tsx`
- Modify: `frontend/tests/mocks/handlers.ts` (no change needed — Task 2's login handler is reused)
- Test: `frontend/tests/auth/LoginPage.test.tsx`

**Interfaces:**
- Consumes: `login`, `ApiError` from `src/api/client.ts` (Task 2)
- Produces: `AuthProvider({children}): JSX.Element`, `useAuth(): {isAuthenticated: boolean; login: (u: string, p: string) => Promise<void>; logout: () => void}`, `LoginPage(): JSX.Element` (calls `useAuth().login`, navigates to `/docs` on success via `react-router-dom`'s `useNavigate`)

- [ ] **Step 1: Write `src/auth/AuthContext.tsx`**

```tsx
import { createContext, useContext, useState, type ReactNode } from "react";
import { clearCredentials, getStoredCredentials, login as apiLogin } from "../api/client";

interface AuthContextValue {
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(() => getStoredCredentials() !== null);

  async function login(username: string, password: string): Promise<void> {
    await apiLogin(username, password);
    setIsAuthenticated(true);
  }

  function logout(): void {
    clearCredentials();
    setIsAuthenticated(false);
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated, login, logout }}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
```

- [ ] **Step 2: Write `src/auth/LoginPage.tsx`**

```tsx
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent): Promise<void> {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(username, password);
      navigate("/docs");
    } catch {
      setError("Invalid username or password");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-sm mx-auto mt-16 flex flex-col gap-4">
      <h1 className="text-xl font-semibold">Admin Login</h1>
      <label className="flex flex-col gap-1">
        Username
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="border rounded px-2 py-1"
        />
      </label>
      <label className="flex flex-col gap-1">
        Password
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="border rounded px-2 py-1"
        />
      </label>
      {error && (
        <p role="alert" className="text-red-600">
          {error}
        </p>
      )}
      <button type="submit" disabled={submitting} className="bg-green-700 text-white rounded px-3 py-2">
        Log in
      </button>
    </form>
  );
}
```

- [ ] **Step 3: Write failing test `tests/auth/LoginPage.test.tsx`**

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, beforeEach } from "vitest";
import { AuthProvider } from "../../src/auth/AuthContext";
import { LoginPage } from "../../src/auth/LoginPage";
import { getStoredCredentials } from "../../src/api/client";
import { API_BASE } from "../mocks/handlers";

beforeEach(() => {
  sessionStorage.clear();
  import.meta.env.VITE_API_BASE_URL = API_BASE;
});

function renderLoginPage() {
  return render(
    <MemoryRouter initialEntries={["/login"]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/docs" element={<div>Docs Page</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  );
}

describe("LoginPage", () => {
  it("navigates to /docs and stores credentials on successful login", async () => {
    renderLoginPage();
    await userEvent.type(screen.getByLabelText("Username"), "admin");
    await userEvent.type(screen.getByLabelText("Password"), "admin");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));

    await waitFor(() => expect(screen.getByText("Docs Page")).toBeInTheDocument());
    expect(getStoredCredentials()).toEqual({ username: "admin", password: "admin" });
  });

  it("shows an error and does not navigate on bad credentials", async () => {
    renderLoginPage();
    await userEvent.type(screen.getByLabelText("Username"), "admin");
    await userEvent.type(screen.getByLabelText("Password"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Invalid username or password"));
    expect(screen.queryByText("Docs Page")).not.toBeInTheDocument();
    expect(getStoredCredentials()).toBeNull();
  });
});
```

- [ ] **Step 4: Run test to verify it fails**

Run: `npm test -- tests/auth/LoginPage.test.tsx`
Expected: FAIL with `Cannot find module '../../src/auth/AuthContext'`

- [ ] **Step 5: Run test to verify it passes**

Run: `npm test -- tests/auth/LoginPage.test.tsx`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/auth/AuthContext.tsx frontend/src/auth/LoginPage.tsx frontend/tests/auth/LoginPage.test.tsx
git commit -m "feat(frontend): add AuthContext and LoginPage"
```

---

### Task 4: RequireAuth route guard + AppShell

**Files:**
- Create: `frontend/src/auth/RequireAuth.tsx`
- Create: `frontend/src/layout/AppShell.tsx`
- Test: `frontend/tests/auth/RequireAuth.test.tsx`

**Interfaces:**
- Consumes: `useAuth` (Task 3)
- Produces: `RequireAuth({children}: {children: JSX.Element}): JSX.Element` (redirects to `/login` via `Navigate` if not authenticated), `AppShell(): JSX.Element` (nav tabs for Docs/Users/Access Log/Audit Log + logout button + `<Outlet/>` for the matched child route)

- [ ] **Step 1: Write `src/auth/RequireAuth.tsx`**

```tsx
import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

export function RequireAuth({ children }: { children: JSX.Element }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return children;
}
```

- [ ] **Step 2: Write `src/layout/AppShell.tsx`**

```tsx
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
```

- [ ] **Step 3: Write failing test `tests/auth/RequireAuth.test.tsx`**

```tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, beforeEach } from "vitest";
import { AuthProvider } from "../../src/auth/AuthContext";
import { RequireAuth } from "../../src/auth/RequireAuth";
import { storeCredentials } from "../../src/api/client";

beforeEach(() => {
  sessionStorage.clear();
});

function renderProtected(initialPath: string) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<div>Login Page</div>} />
          <Route
            path="/docs"
            element={
              <RequireAuth>
                <div>Protected Docs</div>
              </RequireAuth>
            }
          />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  );
}

describe("RequireAuth", () => {
  it("redirects to /login when not authenticated", () => {
    renderProtected("/docs");
    expect(screen.getByText("Login Page")).toBeInTheDocument();
    expect(screen.queryByText("Protected Docs")).not.toBeInTheDocument();
  });

  it("renders the protected content when authenticated", () => {
    storeCredentials("admin", "admin");
    renderProtected("/docs");
    expect(screen.getByText("Protected Docs")).toBeInTheDocument();
  });
});
```

- [ ] **Step 4: Run test to verify it fails**

Run: `npm test -- tests/auth/RequireAuth.test.tsx`
Expected: FAIL with `Cannot find module '../../src/auth/RequireAuth'`

- [ ] **Step 5: Run test to verify it passes**

Run: `npm test -- tests/auth/RequireAuth.test.tsx`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/auth/RequireAuth.tsx frontend/src/layout/AppShell.tsx frontend/tests/auth/RequireAuth.test.tsx
git commit -m "feat(frontend): add RequireAuth guard and AppShell layout"
```

---

### Task 5: DocsPage (upload/list/delete)

**Files:**
- Create: `frontend/src/docs/DocsPage.tsx`
- Test: `frontend/tests/docs/DocsPage.test.tsx`

**Interfaces:**
- Consumes: `apiFetch`, `authHeader`, `ApiError` from `src/api/client.ts` (Task 2)
- Produces: `DocsPage(): JSX.Element`

- [ ] **Step 1: Write `src/docs/DocsPage.tsx`**

```tsx
import { useEffect, useState } from "react";
import { apiFetch, authHeader } from "../api/client";

interface Document {
  id: number;
  filename: string;
  chunk_count: number;
  uploaded_at: string;
}

function apiBase(): string {
  return import.meta.env.VITE_API_BASE_URL ?? "";
}

export function DocsPage() {
  const [docs, setDocs] = useState<Document[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  async function loadDocs(): Promise<void> {
    try {
      const data = await apiFetch<Document[]>("/admin/docs");
      setDocs(data);
    } catch {
      setError("Failed to load documents");
    }
  }

  useEffect(() => {
    loadDocs();
  }, []);

  async function handleUpload(file: File): Promise<void> {
    setUploading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const response = await fetch(`${apiBase()}/admin/docs`, {
        method: "POST",
        headers: { Authorization: authHeader() },
        body: formData,
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || "Upload failed");
      }
      await loadDocs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(id: number): Promise<void> {
    setError(null);
    try {
      await apiFetch(`/admin/docs/${id}`, { method: "DELETE" });
      await loadDocs();
    } catch {
      setError("Failed to delete document");
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold">Documents &amp; Recipes</h1>
      <label className="flex items-center gap-2">
        <span>Upload document</span>
        <input
          type="file"
          disabled={uploading}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleUpload(file);
            e.target.value = "";
          }}
        />
      </label>
      {error && (
        <p role="alert" className="text-red-600">
          {error}
        </p>
      )}
      <table className="w-full text-left border-collapse">
        <thead>
          <tr>
            <th>Filename</th>
            <th>Chunks</th>
            <th>Uploaded</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {docs.map((doc) => (
            <tr key={doc.id}>
              <td>{doc.filename}</td>
              <td>{doc.chunk_count}</td>
              <td>{doc.uploaded_at}</td>
              <td>
                <button onClick={() => handleDelete(doc.id)} className="text-red-600 underline">
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: Write failing test `tests/docs/DocsPage.test.tsx`**

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, beforeEach } from "vitest";
import { server } from "../mocks/server";
import { API_BASE } from "../mocks/handlers";
import { storeCredentials } from "../../src/api/client";
import { DocsPage } from "../../src/docs/DocsPage";

beforeEach(() => {
  sessionStorage.clear();
  import.meta.env.VITE_API_BASE_URL = API_BASE;
  storeCredentials("admin", "admin");
});

describe("DocsPage", () => {
  it("lists documents fetched from the backend", async () => {
    server.use(
      http.get(`${API_BASE}/admin/docs`, () =>
        HttpResponse.json([{ id: 1, filename: "brewing.txt", chunk_count: 3, uploaded_at: "2026-09-02" }])
      )
    );
    render(<DocsPage />);
    await waitFor(() => expect(screen.getByText("brewing.txt")).toBeInTheDocument());
  });

  it("uploads a file and reloads the list", async () => {
    let uploaded = false;
    server.use(
      http.get(`${API_BASE}/admin/docs`, () =>
        HttpResponse.json(uploaded ? [{ id: 2, filename: "recipe.txt", chunk_count: 1, uploaded_at: "now" }] : [])
      ),
      http.post(`${API_BASE}/admin/docs`, () => {
        uploaded = true;
        return HttpResponse.json({ id: 2, filename: "recipe.txt", chunk_count: 1 }, { status: 201 });
      })
    );
    render(<DocsPage />);
    await waitFor(() => expect(screen.queryByText("recipe.txt")).not.toBeInTheDocument());

    const file = new File(["matcha steeping steps"], "recipe.txt", { type: "text/plain" });
    const input = screen.getByLabelText("Upload document") as HTMLInputElement;
    await userEvent.upload(input, file);

    await waitFor(() => expect(screen.getByText("recipe.txt")).toBeInTheDocument());
  });

  it("deletes a document and reloads the list", async () => {
    let deleted = false;
    server.use(
      http.get(`${API_BASE}/admin/docs`, () =>
        HttpResponse.json(deleted ? [] : [{ id: 3, filename: "old.txt", chunk_count: 1, uploaded_at: "now" }])
      ),
      http.delete(`${API_BASE}/admin/docs/3`, () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      })
    );
    render(<DocsPage />);
    await waitFor(() => expect(screen.getByText("old.txt")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(screen.queryByText("old.txt")).not.toBeInTheDocument());
  });

  it("shows an error message when the doc list fails to load", async () => {
    server.use(http.get(`${API_BASE}/admin/docs`, () => new HttpResponse(null, { status: 500 })));
    render(<DocsPage />);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Failed to load documents"));
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `npm test -- tests/docs/DocsPage.test.tsx`
Expected: FAIL with `Cannot find module '../../src/docs/DocsPage'`

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- tests/docs/DocsPage.test.tsx`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/docs/DocsPage.tsx frontend/tests/docs/DocsPage.test.tsx
git commit -m "feat(frontend): add DocsPage with upload/list/delete"
```

---

### Task 6: UsersPage (list/block/unblock)

**Files:**
- Create: `frontend/src/users/UsersPage.tsx`
- Test: `frontend/tests/users/UsersPage.test.tsx`

**Interfaces:**
- Consumes: `apiFetch` from `src/api/client.ts` (Task 2)
- Produces: `UsersPage(): JSX.Element`

- [ ] **Step 1: Write `src/users/UsersPage.tsx`**

```tsx
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
```

- [ ] **Step 2: Write failing test `tests/users/UsersPage.test.tsx`**

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, beforeEach } from "vitest";
import { server } from "../mocks/server";
import { API_BASE } from "../mocks/handlers";
import { storeCredentials } from "../../src/api/client";
import { UsersPage } from "../../src/users/UsersPage";

beforeEach(() => {
  sessionStorage.clear();
  import.meta.env.VITE_API_BASE_URL = API_BASE;
  storeCredentials("admin", "admin");
});

const baseUser = {
  id: 1,
  telegram_user_id: "42",
  first_seen: "2026-09-01",
  message_count: 5,
  favourites: ["sencha"],
  blocked: false,
};

describe("UsersPage", () => {
  it("lists users with their status", async () => {
    server.use(http.get(`${API_BASE}/admin/users`, () => HttpResponse.json([baseUser])));
    render(<UsersPage />);
    await waitFor(() => expect(screen.getByText("42")).toBeInTheDocument());
    expect(screen.getByText("sencha")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("blocks an active user and reflects the new status", async () => {
    let blocked = false;
    server.use(
      http.get(`${API_BASE}/admin/users`, () =>
        HttpResponse.json([{ ...baseUser, blocked }])
      ),
      http.post(`${API_BASE}/admin/users/1/block`, () => {
        blocked = true;
        return HttpResponse.json({ id: 1, blocked: true });
      })
    );
    render(<UsersPage />);
    await waitFor(() => expect(screen.getByText("Active")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Block" }));
    await waitFor(() => expect(screen.getByText("Blocked")).toBeInTheDocument());
  });

  it("shows an error message when the user list fails to load", async () => {
    server.use(http.get(`${API_BASE}/admin/users`, () => new HttpResponse(null, { status: 500 })));
    render(<UsersPage />);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Failed to load users"));
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `npm test -- tests/users/UsersPage.test.tsx`
Expected: FAIL with `Cannot find module '../../src/users/UsersPage'`

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- tests/users/UsersPage.test.tsx`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/users/UsersPage.tsx frontend/tests/users/UsersPage.test.tsx
git commit -m "feat(frontend): add UsersPage with list/block/unblock"
```

---

### Task 7: AccessLogPage (paginated)

**Files:**
- Create: `frontend/src/logs/AccessLogPage.tsx`
- Test: `frontend/tests/logs/AccessLogPage.test.tsx`

**Interfaces:**
- Consumes: `apiFetch` from `src/api/client.ts` (Task 2)
- Produces: `AccessLogPage(): JSX.Element`

- [ ] **Step 1: Write `src/logs/AccessLogPage.tsx`**

```tsx
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
```

- [ ] **Step 2: Write failing test `tests/logs/AccessLogPage.test.tsx`**

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, beforeEach } from "vitest";
import { server } from "../mocks/server";
import { API_BASE } from "../mocks/handlers";
import { storeCredentials } from "../../src/api/client";
import { AccessLogPage } from "../../src/logs/AccessLogPage";

beforeEach(() => {
  sessionStorage.clear();
  import.meta.env.VITE_API_BASE_URL = API_BASE;
  storeCredentials("admin", "admin");
});

describe("AccessLogPage", () => {
  it("lists access log entries for the first page", async () => {
    server.use(
      http.get(`${API_BASE}/admin/logs/access`, ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get("limit")).toBe("20");
        expect(url.searchParams.get("offset")).toBe("0");
        return HttpResponse.json([
          { id: 1, telegram_user_id: "42", role: "user", content: "hi", created_at: "now" },
        ]);
      })
    );
    render(<AccessLogPage />);
    await waitFor(() => expect(screen.getByText("hi")).toBeInTheDocument());
  });

  it("requests the next page with an incremented offset", async () => {
    server.use(
      http.get(`${API_BASE}/admin/logs/access`, ({ request }) => {
        const url = new URL(request.url);
        const offset = url.searchParams.get("offset");
        if (offset === "0") {
          return HttpResponse.json(
            Array.from({ length: 20 }, (_, i) => ({
              id: i,
              telegram_user_id: "42",
              role: "user",
              content: `msg-${i}`,
              created_at: "now",
            }))
          );
        }
        return HttpResponse.json([{ id: 20, telegram_user_id: "42", role: "user", content: "page-2", created_at: "now" }]);
      })
    );
    render(<AccessLogPage />);
    await waitFor(() => expect(screen.getByText("msg-0")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(screen.getByText("page-2")).toBeInTheDocument());
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `npm test -- tests/logs/AccessLogPage.test.tsx`
Expected: FAIL with `Cannot find module '../../src/logs/AccessLogPage'`

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test -- tests/logs/AccessLogPage.test.tsx`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/logs/AccessLogPage.tsx frontend/tests/logs/AccessLogPage.test.tsx
git commit -m "feat(frontend): add paginated AccessLogPage"
```

---

### Task 8: AuditLogPage (paginated) + route table wiring

**Files:**
- Create: `frontend/src/logs/AuditLogPage.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `frontend/tests/logs/AuditLogPage.test.tsx`
- Test: `frontend/tests/App.test.tsx` (replace Task 1's placeholder test)

**Interfaces:**
- Consumes: `apiFetch` (Task 2), `AuthProvider` (Task 3), `RequireAuth` (Task 4), `AppShell` (Task 4), `LoginPage` (Task 3), `DocsPage` (Task 5), `UsersPage` (Task 6), `AccessLogPage` (Task 7)
- Produces: `AuditLogPage(): JSX.Element`; `App(): JSX.Element` now the real route table

- [ ] **Step 1: Write `src/logs/AuditLogPage.tsx`** (mirrors `AccessLogPage`'s pagination shape, different fields)

```tsx
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
        <button disabled={entries.length < PAGE_SIZE} onClick={() => setOffset(offset + PAGE_SIZE)}>
          Next
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Write failing test `tests/logs/AuditLogPage.test.tsx`**

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it, beforeEach } from "vitest";
import { server } from "../mocks/server";
import { API_BASE } from "../mocks/handlers";
import { storeCredentials } from "../../src/api/client";
import { AuditLogPage } from "../../src/logs/AuditLogPage";

beforeEach(() => {
  sessionStorage.clear();
  import.meta.env.VITE_API_BASE_URL = API_BASE;
  storeCredentials("admin", "admin");
});

describe("AuditLogPage", () => {
  it("lists audit log entries", async () => {
    server.use(
      http.get(`${API_BASE}/admin/logs/audit`, () =>
        HttpResponse.json([{ id: 1, action: "block_user", target: "42", ip: "1.2.3.4", created_at: "now" }])
      )
    );
    render(<AuditLogPage />);
    await waitFor(() => expect(screen.getByText("block_user")).toBeInTheDocument());
  });
});
```

- [ ] **Step 3: Rewrite `src/App.tsx`** with the real route table

```tsx
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { LoginPage } from "./auth/LoginPage";
import { RequireAuth } from "./auth/RequireAuth";
import { AppShell } from "./layout/AppShell";
import { DocsPage } from "./docs/DocsPage";
import { UsersPage } from "./users/UsersPage";
import { AccessLogPage } from "./logs/AccessLogPage";
import { AuditLogPage } from "./logs/AuditLogPage";

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <RequireAuth>
                <AppShell />
              </RequireAuth>
            }
          >
            <Route index element={<Navigate to="/docs" replace />} />
            <Route path="docs" element={<DocsPage />} />
            <Route path="users" element={<UsersPage />} />
            <Route path="logs/access" element={<AccessLogPage />} />
            <Route path="logs/audit" element={<AuditLogPage />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
```

- [ ] **Step 4: Rewrite `tests/App.test.tsx`** — replace Task 1's placeholder smoke test with a real integration test exercising login → nav → a page

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, beforeEach } from "vitest";
import { server } from "./mocks/server";
import { API_BASE } from "./mocks/handlers";
import { App } from "../src/App";

beforeEach(() => {
  sessionStorage.clear();
  import.meta.env.VITE_API_BASE_URL = API_BASE;
  window.history.pushState({}, "", "/");
});

describe("App", () => {
  it("redirects an unauthenticated visitor to /login, then to /docs after login", async () => {
    server.use(
      http.get(`${API_BASE}/admin/docs`, () => HttpResponse.json([])),
    );
    render(<App />);
    expect(await screen.findByText("Admin Login")).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("Username"), "admin");
    await userEvent.type(screen.getByLabelText("Password"), "admin");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));

    await waitFor(() => expect(screen.getByText("Documents & Recipes")).toBeInTheDocument());
  });

  it("navigates between admin tabs once authenticated", async () => {
    server.use(
      http.get(`${API_BASE}/admin/docs`, () => HttpResponse.json([])),
      http.get(`${API_BASE}/admin/users`, () => HttpResponse.json([])),
    );
    render(<App />);
    await userEvent.type(await screen.findByLabelText("Username"), "admin");
    await userEvent.type(screen.getByLabelText("Password"), "admin");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    await waitFor(() => expect(screen.getByText("Documents & Recipes")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("link", { name: "Users" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Users" })).toBeInTheDocument());
  });
});
```

- [ ] **Step 5: Run all frontend tests to verify everything passes**

Run: `npm test`
Expected: PASS (all tests across all files — App, LoginPage, RequireAuth, DocsPage, UsersPage, AccessLogPage, AuditLogPage, client)

- [ ] **Step 6: Commit**

```bash
git add frontend/src/logs/AuditLogPage.tsx frontend/src/App.tsx frontend/tests/logs/AuditLogPage.test.tsx frontend/tests/App.test.tsx
git commit -m "feat(frontend): add AuditLogPage and wire the full route table"
```

---

### Task 9: Production build check

**Files:**
- None created — this task verifies the existing code builds cleanly for production, which the infra plan's Docker build will depend on.

**Interfaces:**
- Consumes: everything above

- [ ] **Step 1: Run a type-check + production build**

Run (from `frontend/`):
```bash
npm run build
```
Expected: Succeeds, producing `frontend/dist/index.html` and bundled assets. If `tsc -b` reports type errors, fix them in the relevant task's file (not by loosening `tsconfig.json`'s `strict` setting) before proceeding.

- [ ] **Step 2: Manually smoke-test the dev server against a real backend** (not automated — do this once, by hand, before calling the plan done)

Run (from `frontend/`, with the backend service running per the backend plan's own instructions and `VITE_API_BASE_URL` pointed at it, e.g. `http://localhost:8000`):
```bash
npm run dev
```
Open the printed local URL, log in with the backend's configured admin credentials, and confirm: the Documents tab lists/uploads/deletes a `.txt` file against the real backend, the Users tab lists at least the placeholder state, and both log tabs load without error. This is a manual check — there is no automated step for it, since it requires a live backend process.

- [ ] **Step 3: Commit** (only if Step 1 required fixes; otherwise this task has nothing to commit)

```bash
git status --short frontend/
# If clean, nothing to commit — this task's purpose was verification.
# If Step 1 required fixes, commit them:
git add frontend/
git commit -m "fix(frontend): resolve production build/type errors"
```

---

## Self-Review Notes

- Spec coverage: login (Task 3), document/recipe upload+list+delete via the single generic doc form (Task 5), users list+block/unblock (Task 6), access log (Task 7), audit log (Task 8), route protection so nothing is reachable without login (Task 4), no chat UI anywhere in this plan (never built) — all covered.
- Type consistency checked: `apiFetch<T>` used consistently with matching response shapes across Tasks 5-8; `useAuth()`'s returned shape matches between `AuthContext` (Task 3) and its consumers (`LoginPage`, `RequireAuth`, `AppShell`).
- Out of scope for this plan (left to the infra plan or a future iteration): nginx serving `frontend/dist/`, Dockerfile for the frontend, and the design-polish pass the spec mentions ("Built with the ui-ux-pro-max skill for styling/components") — this plan uses plain Tailwind utility classes to keep the TDD loop tight; a follow-up pass through the ui-ux-pro-max/frontend-design skill can restyle these same components without touching their behavior or tests.
