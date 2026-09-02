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
});
