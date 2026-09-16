import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { LoginPage } from "./auth/LoginPage";
import { RequireAuth } from "./auth/RequireAuth";
import { AppShell } from "./layout/AppShell";
import { ChatPage } from "./chat/ChatPage";
import { DocsPage } from "./docs/DocsPage";
import { UsersPage } from "./users/UsersPage";
import { AccessLogPage } from "./logs/AccessLogPage";
import { AuditLogPage } from "./logs/AuditLogPage";
import { UsagePage } from "./usage/UsagePage";
import { WelcomePage } from "./welcome/WelcomePage";
import { ChannelsPage } from "./channels/ChannelsPage";
import { SettingsPage } from "./settings/SettingsPage";
import { PersonalityPage } from "./personality/PersonalityPage";

/** `/panel` lands admins on Usage (their overview) and customers on Chat (their only tab). */
function PanelIndex() {
  const { isAdmin } = useAuth();
  return <Navigate to={isAdmin ? "/panel/usage" : "/panel/chat"} replace />;
}

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
            <Route index element={<PanelIndex />} />
            <Route path="chat" element={<ChatPage />} />
            <Route
              path="docs"
              element={
                <RequireAuth adminOnly>
                  <DocsPage />
                </RequireAuth>
              }
            />
            <Route
              path="users"
              element={
                <RequireAuth adminOnly>
                  <UsersPage />
                </RequireAuth>
              }
            />
            <Route
              path="logs/access"
              element={
                <RequireAuth adminOnly>
                  <AccessLogPage />
                </RequireAuth>
              }
            />
            <Route
              path="logs/audit"
              element={
                <RequireAuth adminOnly>
                  <AuditLogPage />
                </RequireAuth>
              }
            />
            <Route
              path="usage"
              element={
                <RequireAuth adminOnly>
                  <UsagePage />
                </RequireAuth>
              }
            />
            <Route
              path="channels"
              element={
                <RequireAuth adminOnly>
                  <ChannelsPage />
                </RequireAuth>
              }
            />
            <Route
              path="settings"
              element={
                <RequireAuth adminOnly>
                  <SettingsPage />
                </RequireAuth>
              }
            />
            <Route
              path="personality"
              element={
                <RequireAuth adminOnly>
                  <PersonalityPage />
                </RequireAuth>
              }
            />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
