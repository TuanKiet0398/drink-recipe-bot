import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, beforeEach } from "vitest";
import { AuthProvider } from "../../src/auth/AuthContext";
import { LoginPage } from "../../src/auth/LoginPage";
import { getStoredCredentials } from "../../src/api/client";
import { API_BASE } from "../mocks/handlers";
import { server } from "../mocks/server";

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
          <Route path="/panel/docs" element={<div>Docs Page</div>} />
          <Route path="/panel/chat" element={<div>Chat Page</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  );
}

describe("LoginPage", () => {
  it("navigates to /panel/docs and stores credentials on successful login", async () => {
    renderLoginPage();
    await userEvent.type(screen.getByLabelText("Username"), "admin");
    await userEvent.type(screen.getByLabelText("Password"), "admin");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));

    await waitFor(() => expect(screen.getByText("Docs Page")).toBeInTheDocument());
    expect(getStoredCredentials()).toEqual({ username: "admin", password: "admin", role: "admin" });
  });

  it("has a back link to the landing page", () => {
    renderLoginPage();
    expect(screen.getByRole("link", { name: /back/i })).toHaveAttribute("href", "/");
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

  describe("registration", () => {
    async function openRegister() {
      renderLoginPage();
      await userEvent.click(screen.getByRole("button", { name: "No account? Create one" }));
    }

    async function fillRegister(username: string, password: string, confirm: string) {
      await userEvent.type(screen.getByLabelText("Username"), username);
      await userEvent.type(screen.getByLabelText("Password"), password);
      await userEvent.type(screen.getByLabelText("Confirm password"), confirm);
      await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    }

    it("switches to register mode and back", async () => {
      await openRegister();
      expect(screen.getByRole("heading", { name: "Create account" })).toBeInTheDocument();
      expect(screen.getByLabelText("Confirm password")).toBeInTheDocument();

      await userEvent.click(screen.getByRole("button", { name: "Have an account? Log in" }));
      expect(screen.getByRole("heading", { name: "Admin Login" })).toBeInTheDocument();
      expect(screen.queryByLabelText("Confirm password")).not.toBeInTheDocument();
    });

    it("rejects mismatched passwords without calling the server", async () => {
      let calls = 0;
      server.use(
        http.post(`${API_BASE}/auth/register`, () => {
          calls += 1;
          return HttpResponse.json({ username: "linh" }, { status: 201 });
        })
      );
      await openRegister();

      await fillRegister("linh", "matcha-lover", "matcha-lovers");

      expect(screen.getByRole("alert")).toHaveTextContent("Passwords do not match");
      expect(calls).toBe(0);
    });

    it("shows when the username is taken", async () => {
      server.use(
        http.post(`${API_BASE}/auth/register`, () =>
          HttpResponse.json({ detail: "Username already taken" }, { status: 409 })
        )
      );
      await openRegister();

      await fillRegister("linh", "matcha-lover", "matcha-lover");

      await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Username already taken"));
      expect(getStoredCredentials()).toBeNull();
    });

    it("explains the rules when the server rejects the input", async () => {
      server.use(http.post(`${API_BASE}/auth/register`, () => HttpResponse.json({ detail: [] }, { status: 422 })));
      await openRegister();

      await fillRegister("linh", "matcha-lover", "matcha-lover");

      await waitFor(() =>
        expect(screen.getByRole("alert")).toHaveTextContent(
          "Username must be 3–32 characters (letters, numbers, _ . -) and password at least 8 characters"
        )
      );
    });

    it("registers, signs in and opens the chat", async () => {
      const bodies: unknown[] = [];
      server.use(
        http.post(`${API_BASE}/auth/register`, async ({ request }) => {
          bodies.push(await request.json());
          return HttpResponse.json({ username: "linh" }, { status: 201 });
        }),
        http.post(`${API_BASE}/admin/login`, () => HttpResponse.json({ status: "ok" }))
      );
      await openRegister();

      await fillRegister("linh", "matcha-lover", "matcha-lover");

      await waitFor(() => expect(screen.getByText("Chat Page")).toBeInTheDocument());
      expect(bodies).toEqual([{ username: "linh", password: "matcha-lover" }]);
      expect(getStoredCredentials()).toEqual({ username: "linh", password: "matcha-lover" });
    });
  });
});
