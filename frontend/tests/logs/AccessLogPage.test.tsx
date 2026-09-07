import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, beforeEach } from "vitest";
import { server } from "../mocks/server";
import { API_BASE } from "../mocks/handlers";
import { storeCredentials } from "../../src/api/client";
import { AccessLogPage } from "../../src/logs/AccessLogPage";

beforeEach(() => {
  sessionStorage.clear();
  import.meta.env.VITE_API_BASE_URL = API_BASE;
  storeCredentials("admin", "admin");
});

describe("AccessLogPage", () => {
  it("lists access log entries for the first page", async () => {
    server.use(
      http.get(`${API_BASE}/admin/logs/access`, ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get("limit")).toBe("20");
        expect(url.searchParams.get("offset")).toBe("0");
        return HttpResponse.json([
          { id: 1, telegram_user_id: "42", role: "user", content: "hi", created_at: "now" },
        ]);
      })
    );
    render(<AccessLogPage />);
    await waitFor(() => expect(screen.getByText("hi")).toBeInTheDocument());
  });

  it("requests the next page with an incremented offset", async () => {
    server.use(
      http.get(`${API_BASE}/admin/logs/access`, ({ request }) => {
        const url = new URL(request.url);
        const offset = url.searchParams.get("offset");
        if (offset === "0") {
          return HttpResponse.json(
            Array.from({ length: 20 }, (_, i) => ({
              id: i,
              telegram_user_id: "42",
              role: "user",
              content: `msg-${i}`,
              created_at: "now",
            }))
          );
        }
        return HttpResponse.json([{ id: 20, telegram_user_id: "42", role: "user", content: "page-2", created_at: "now" }]);
      })
    );
    render(<AccessLogPage />);
    await waitFor(() => expect(screen.getByText("msg-0")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(screen.getByText("page-2")).toBeInTheDocument());
  });

  it("clears error state when a load succeeds after a previous failure", async () => {
    // First handler: all requests fail
    server.use(
      http.get(`${API_BASE}/admin/logs/access`, () => {
        return new HttpResponse(null, { status: 500 });
      })
    );
    render(<AccessLogPage />);
    // Verify error alert appears after first failed load
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Failed to load access log")).toBeInTheDocument());
    // Override handler to succeed on next request
    server.use(
      http.get(`${API_BASE}/admin/logs/access`, () => {
        return HttpResponse.json([
          { id: 1, telegram_user_id: "42", role: "user", content: "success", created_at: "now" },
        ]);
      })
    );
    // Trigger next page (which should now succeed)
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    // Verify error alert is gone and new data is shown
    await waitFor(() => expect(screen.getByText("success")).toBeInTheDocument());
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
  });
  it("sends no filter params until a filter is chosen", async () => {
    let query: URLSearchParams | null = null;
    server.use(
      http.get(`${API_BASE}/admin/logs/access`, ({ request }) => {
        query = new URL(request.url).searchParams;
        return HttpResponse.json([]);
      })
    );
    render(<AccessLogPage />);

    await waitFor(() => expect(query).not.toBeNull());
    expect(query!.get("role")).toBeNull();
    expect(query!.get("telegram_user_id")).toBeNull();
    expect(query!.get("from_date")).toBeNull();
    expect(query!.get("to_date")).toBeNull();
  });

  it("sends the chosen role and date range", async () => {
    let query: URLSearchParams | null = null;
    server.use(
      http.get(`${API_BASE}/admin/logs/access`, ({ request }) => {
        query = new URL(request.url).searchParams;
        return HttpResponse.json([]);
      })
    );
    render(<AccessLogPage />);
    await waitFor(() => expect(query).not.toBeNull());

    await userEvent.selectOptions(screen.getByLabelText("Role"), "assistant");
    await waitFor(() => expect(query!.get("role")).toBe("assistant"));

    await userEvent.type(screen.getByLabelText("From"), "2026-03-01");
    await waitFor(() => expect(query!.get("from_date")).toBe("2026-03-01"));
  });

  it("populates the customer dropdown from /admin/users", async () => {
    server.use(
      http.get(`${API_BASE}/admin/logs/access`, () => HttpResponse.json([])),
      http.get(`${API_BASE}/admin/users`, () =>
        HttpResponse.json([
          { id: 1, telegram_user_id: "alice" },
          { id: 2, telegram_user_id: "bob" },
        ])
      )
    );
    render(<AccessLogPage />);

    expect(await screen.findByRole("option", { name: "alice" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "bob" })).toBeInTheDocument();
  });

  it("resets to the first page when a filter changes", async () => {
    let query: URLSearchParams | null = null;
    server.use(
      http.get(`${API_BASE}/admin/logs/access`, ({ request }) => {
        query = new URL(request.url).searchParams;
        // A full page, so the Next button stays enabled.
        return HttpResponse.json(
          Array.from({ length: 20 }, (_, i) => ({
            id: i,
            telegram_user_id: "42",
            role: "user",
            content: `msg-${i}`,
            created_at: "now",
          }))
        );
      })
    );
    render(<AccessLogPage />);
    await waitFor(() => expect(screen.getByText("msg-0")).toBeInTheDocument());

    // Page forward, then narrow the filter: offset must go back to 0, or the
    // admin lands on an empty page of a now-shorter result set.
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(query!.get("offset")).toBe("20"));

    await userEvent.selectOptions(screen.getByLabelText("Role"), "user");

    await waitFor(() => expect(query!.get("offset")).toBe("0"));
    expect(query!.get("role")).toBe("user");
  });

  it("clears every filter", async () => {
    let query: URLSearchParams | null = null;
    server.use(
      http.get(`${API_BASE}/admin/logs/access`, ({ request }) => {
        query = new URL(request.url).searchParams;
        return HttpResponse.json([]);
      })
    );
    render(<AccessLogPage />);
    await waitFor(() => expect(query).not.toBeNull());

    await userEvent.selectOptions(screen.getByLabelText("Role"), "user");
    await waitFor(() => expect(query!.get("role")).toBe("user"));

    await userEvent.click(screen.getByRole("button", { name: "Clear filters" }));

    await waitFor(() => expect(query!.get("role")).toBeNull());
  });
});
