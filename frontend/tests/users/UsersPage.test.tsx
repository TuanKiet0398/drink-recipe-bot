import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, beforeEach } from "vitest";
import { server } from "../mocks/server";
import { API_BASE } from "../mocks/handlers";
import { storeCredentials } from "../../src/api/client";
import { UsersPage } from "../../src/users/UsersPage";

beforeEach(() => {
  sessionStorage.clear();
  import.meta.env.VITE_API_BASE_URL = API_BASE;
  storeCredentials("admin", "admin");
});

const baseUser = {
  id: 1,
  telegram_user_id: "42",
  first_seen: "2026-09-01",
  message_count: 5,
  favourites: ["sencha"],
  blocked: false,
};

describe("UsersPage", () => {
  it("lists users with their status", async () => {
    server.use(http.get(`${API_BASE}/admin/users`, () => HttpResponse.json([baseUser])));
    render(<UsersPage />);
    await waitFor(() => expect(screen.getByText("42")).toBeInTheDocument());
    expect(screen.getByText("sencha")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("blocks an active user and reflects the new status", async () => {
    let blocked = false;
    server.use(
      http.get(`${API_BASE}/admin/users`, () =>
        HttpResponse.json([{ ...baseUser, blocked }])
      ),
      http.post(`${API_BASE}/admin/users/1/block`, () => {
        blocked = true;
        return HttpResponse.json({ id: 1, blocked: true });
      })
    );
    render(<UsersPage />);
    await waitFor(() => expect(screen.getByText("Active")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Block" }));
    await waitFor(() => expect(screen.getByText("Blocked")).toBeInTheDocument());
  });

  it("shows an error message when the user list fails to load", async () => {
    server.use(http.get(`${API_BASE}/admin/users`, () => new HttpResponse(null, { status: 500 })));
    render(<UsersPage />);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Failed to load users"));
  });
});
