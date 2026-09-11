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

/** The server's `detail` string from a failed request, else `fallback`. */
export function readableError(err: unknown, fallback: string): string {
  if (err instanceof ApiError && err.message) {
    try {
      const parsed = JSON.parse(err.message);
      if (typeof parsed.detail === "string") return parsed.detail;
    } catch {
      return err.message;
    }
  }
  return fallback;
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

type UnauthorizedListener = () => void;

const unauthorizedListeners = new Set<UnauthorizedListener>();

/**
 * Register a callback invoked whenever apiFetch clears stored credentials
 * because a request came back 401. Returns an unsubscribe function.
 */
export function onUnauthorized(listener: UnauthorizedListener): () => void {
  unauthorizedListeners.add(listener);
  return () => {
    unauthorizedListeners.delete(listener);
  };
}

function notifyUnauthorized(): void {
  unauthorizedListeners.forEach((listener) => listener());
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

/** Creates a web account. Does not sign in — call `login` afterwards. */
export async function register(username: string, password: string): Promise<void> {
  const response = await fetch(`${apiBase()}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!response.ok) {
    throw new ApiError((await response.text()) || response.statusText, response.status);
  }
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
    notifyUnauthorized();
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
