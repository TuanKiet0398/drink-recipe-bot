import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { clearCredentials, getStoredCredentials, login as apiLogin, onUnauthorized } from "../api/client";

interface AuthContextValue {
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(() => getStoredCredentials() !== null);

  useEffect(() => {
    return onUnauthorized(() => setIsAuthenticated(false));
  }, []);

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
