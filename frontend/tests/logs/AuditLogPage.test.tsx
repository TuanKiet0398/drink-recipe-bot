import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, beforeEach } from "vitest";
import { server } from "../mocks/server";
import { API_BASE } from "../mocks/handlers";
import { storeCredentials } from "../../src/api/client";
import { AuditLogPage } from "../../src/logs/AuditLogPage";

beforeEach(() => {
  sessionStorage.clear();
  import.meta.env.VITE_API_BASE_URL = API_BASE;
  storeCredentials("admin", "admin");
});

describe("AuditLogPage", () => {
  it("lists audit log entries for the first page", async () => {
    server.use(
      http.get(`${API_BASE}/admin/logs/audit`, ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get("limit")).toBe("20");
        expect(url.searchParams.get("offset")).toBe("0");
        return HttpResponse.json([
          { id: 1, action: "block_user", target: "42", ip: "1.2.3.4", created_at: "now" },
        ]);
      })
    );
    render(<AuditLogPage />);
    await waitFor(() => expect(screen.getByText("block_user")).toBeInTheDocument());
  });

  it("requests the next page with an incremented offset", async () => {
    server.use(
      http.get(`${API_BASE}/admin/logs/audit`, ({ request }) => {
        const url = new URL(request.url);
        const offset = url.searchParams.get("offset");
        if (offset === "0") {
          return HttpResponse.json(
            Array.from({ length: 20 }, (_, i) => ({
              id: i,
              action: `action-${i}`,
              target: "42",
              ip: "1.2.3.4",
              created_at: "now",
            }))
          );
        }
        return HttpResponse.json([
          { id: 20, action: "page-2", target: "42", ip: "1.2.3.4", created_at: "now" },
        ]);
      })
    );
    render(<AuditLogPage />);
    await waitFor(() => expect(screen.getByText("action-0")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(screen.getByText("page-2")).toBeInTheDocument());
  });

  it("clears error state when a load succeeds after a previous failure", async () => {
    server.use(
      http.get(`${API_BASE}/admin/logs/audit`, () => {
        return new HttpResponse(null, { status: 500 });
      })
    );
    render(<AuditLogPage />);
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Failed to load audit log")).toBeInTheDocument());
    server.use(
      http.get(`${API_BASE}/admin/logs/audit`, () => {
        return HttpResponse.json([
          { id: 1, action: "success", target: "42", ip: "1.2.3.4", created_at: "now" },
        ]);
      })
    );
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(screen.getByText("success")).toBeInTheDocument());
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
  });
});
