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
