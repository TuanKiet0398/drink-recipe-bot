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
