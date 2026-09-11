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
  window.history.pushState({}, "", "/panel");
});

describe("App", () => {
  it("shows the public welcome page at / with a link into the admin login", () => {
    window.history.pushState({}, "", "/");
    render(<App />);
    expect(screen.getByRole("heading", { name: /steep the knowledge/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Enter Admin Panel" })).toHaveAttribute("href", "/login");
  });

  it("redirects an unauthenticated visitor to /login, then to /panel/docs after login", async () => {
    server.use(http.get(`${API_BASE}/admin/docs`, () => HttpResponse.json([])));
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
      http.get(`${API_BASE}/admin/users`, () => HttpResponse.json([]))
    );
    render(<App />);
    await userEvent.type(await screen.findByLabelText("Username"), "admin");
    await userEvent.type(screen.getByLabelText("Password"), "admin");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    await waitFor(() => expect(screen.getByText("Documents & Recipes")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("link", { name: "Users" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Users" })).toBeInTheDocument());
  });

  it("redirects to /login when a request returns 401 mid-session", async () => {
    server.use(http.get(`${API_BASE}/admin/docs`, () => HttpResponse.json([])));
    render(<App />);
    await userEvent.type(await screen.findByLabelText("Username"), "admin");
    await userEvent.type(screen.getByLabelText("Password"), "admin");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    await waitFor(() => expect(screen.getByText("Documents & Recipes")).toBeInTheDocument());

    server.use(http.get(`${API_BASE}/admin/users`, () => new HttpResponse(null, { status: 401 })));
    await userEvent.click(screen.getByRole("link", { name: "Users" }));

    await waitFor(() => expect(screen.getByText("Admin Login")).toBeInTheDocument());
  });

  it("opens the test chat from the sidebar", async () => {
    server.use(
      http.get(`${API_BASE}/admin/docs`, () => HttpResponse.json([])),
      http.get(`${API_BASE}/admin/llm-settings`, () =>
        HttpResponse.json({ provider: "openai", chat_model: "gpt-4o-mini" })
      )
    );
    render(<App />);
    await userEvent.type(await screen.findByLabelText("Username"), "admin");
    await userEvent.type(screen.getByLabelText("Password"), "admin");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    await waitFor(() => expect(screen.getByText("Documents & Recipes")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("link", { name: "Chat" }));
    await waitFor(() => expect(screen.getByRole("heading", { name: "Chat" })).toBeInTheDocument());
  });

  it("shows the signed-in username and logs out back to the login page", async () => {
    server.use(http.get(`${API_BASE}/admin/docs`, () => HttpResponse.json([])));
    render(<App />);
    await userEvent.type(await screen.findByLabelText("Username"), "admin");
    await userEvent.type(screen.getByLabelText("Password"), "admin");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    await waitFor(() => expect(screen.getByText("Documents & Recipes")).toBeInTheDocument());

    expect(screen.getByText("admin")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Log out" }));

    await waitFor(() => expect(screen.getByText("Admin Login")).toBeInTheDocument());
  });
});
