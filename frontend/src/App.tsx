import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { LoginPage } from "./auth/LoginPage";
import { RequireAuth } from "./auth/RequireAuth";
import { AppShell } from "./layout/AppShell";
import { DocsPage } from "./docs/DocsPage";
import { UsersPage } from "./users/UsersPage";
import { AccessLogPage } from "./logs/AccessLogPage";
import { AuditLogPage } from "./logs/AuditLogPage";
import { WelcomePage } from "./welcome/WelcomePage";

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<WelcomePage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/panel"
            element={
              <RequireAuth>
                <AppShell />
              </RequireAuth>
            }
          >
            <Route index element={<Navigate to="/panel/docs" replace />} />
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
