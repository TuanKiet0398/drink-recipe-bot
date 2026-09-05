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
  window.history.pushState({}, "", "/");
});

describe("App", () => {
  it("redirects an unauthenticated visitor to /login, then to /docs after login", async () => {
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
});
