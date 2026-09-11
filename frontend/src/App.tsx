import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
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
            <Route index element={<Navigate to="/panel/usage" replace />} />
            <Route path="chat" element={<ChatPage />} />
            <Route path="docs" element={<DocsPage />} />
            <Route path="users" element={<UsersPage />} />
            <Route path="logs/access" element={<AccessLogPage />} />
            <Route path="logs/audit" element={<AuditLogPage />} />
            <Route path="usage" element={<UsagePage />} />
            <Route path="channels" element={<ChannelsPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="personality" element={<PersonalityPage />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
