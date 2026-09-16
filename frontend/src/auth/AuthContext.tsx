import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import {
  clearCredentials,
  getStoredCredentials,
  login as apiLogin,
  onUnauthorized,
  register as apiRegister,
} from "../api/client";

interface AuthContextValue {
  isAuthenticated: boolean;
  isAdmin: boolean;
  username: string | null;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [username, setUsername] = useState<string | null>(() => getStoredCredentials()?.username ?? null);
  const [role, setRole] = useState<string | null>(() => getStoredCredentials()?.role ?? null);

  useEffect(() => {
    return onUnauthorized(() => {
      setUsername(null);
      setRole(null);
    });
  }, []);

  async function login(name: string, password: string): Promise<void> {
    const signedInRole = await apiLogin(name, password);
    setUsername(name);
    setRole(signedInRole);
  }

  async function register(name: string, password: string): Promise<void> {
    await apiRegister(name, password);
    await login(name, password);
  }

  function logout(): void {
    clearCredentials();
    setUsername(null);
    setRole(null);
  }

  return (
    <AuthContext.Provider
      value={{ isAuthenticated: username !== null, isAdmin: role === "admin", username, login, register, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
