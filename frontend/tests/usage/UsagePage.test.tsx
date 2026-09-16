import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, beforeEach } from "vitest";
import { server } from "../mocks/server";
import { API_BASE } from "../mocks/handlers";
import { storeCredentials } from "../../src/api/client";
import { UsagePage } from "../../src/usage/UsagePage";

beforeEach(() => {
  sessionStorage.clear();
  import.meta.env.VITE_API_BASE_URL = API_BASE;
  storeCredentials("admin", "admin", "admin");
});

const emptySummary = { total_calls: 0, total_tokens: 0, estimated_cost_usd: 0, by_model: [] };

describe("UsagePage", () => {
  it("renders the summary cards from the summary endpoint", async () => {
    server.use(
      http.get(`${API_BASE}/admin/usage/summary`, () =>
        HttpResponse.json({
          total_calls: 42,
          total_tokens: 123456,
          estimated_cost_usd: 1.2345,
          by_model: [{ model: "gpt-4o-mini", calls: 40, total_tokens: 120000, estimated_cost_usd: 1.1 }],
        })
      ),
      http.get(`${API_BASE}/admin/usage`, () => HttpResponse.json([]))
    );
    render(<UsagePage />);

    await waitFor(() => expect(screen.getByText("42")).toBeInTheDocument());
    expect(screen.getByText("123456")).toBeInTheDocument();
    expect(screen.getByText("$1.2345")).toBeInTheDocument();
    expect(screen.getByText("gpt-4o-mini")).toBeInTheDocument();
  });

  it("lists usage entries for the first page", async () => {
    server.use(
      http.get(`${API_BASE}/admin/usage/summary`, () => HttpResponse.json(emptySummary)),
      http.get(`${API_BASE}/admin/usage`, ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get("limit")).toBe("20");
        expect(url.searchParams.get("offset")).toBe("0");
        return HttpResponse.json([
          {
            id: 1,
            user_id: 7,
            call_type: "generate",
            model: "gpt-4o-mini",
            prompt_tokens: 100,
            completion_tokens: 50,
            total_tokens: 150,
            created_at: "now",
          },
        ]);
      })
    );
    render(<UsagePage />);
    await waitFor(() => expect(screen.getByText("generate")).toBeInTheDocument());
    expect(screen.getByText("150")).toBeInTheDocument();
  });

  it("requests the next page with an incremented offset", async () => {
    server.use(
      http.get(`${API_BASE}/admin/usage/summary`, () => HttpResponse.json(emptySummary)),
      http.get(`${API_BASE}/admin/usage`, ({ request }) => {
        const url = new URL(request.url);
        const offset = url.searchParams.get("offset");
        if (offset === "0") {
          return HttpResponse.json(
            Array.from({ length: 20 }, (_, i) => ({
              id: i,
              user_id: 1,
              call_type: "generate",
              model: "gpt-4o-mini",
              prompt_tokens: i,
              completion_tokens: i,
              total_tokens: i * 2,
              created_at: "now",
            }))
          );
        }
        return HttpResponse.json([
          {
            id: 20,
            user_id: 1,
            call_type: "embedding",
            model: "text-embedding-3-small",
            prompt_tokens: 5,
            completion_tokens: null,
            total_tokens: 5,
            created_at: "now",
          },
        ]);
      })
    );
    render(<UsagePage />);
    await waitFor(() => expect(screen.getAllByText("generate").length).toBeGreaterThan(0));
    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(screen.getByText("embedding")).toBeInTheDocument());
  });

  it("shows an error message when the list fails to load", async () => {
    server.use(
      http.get(`${API_BASE}/admin/usage/summary`, () => HttpResponse.json(emptySummary)),
      http.get(`${API_BASE}/admin/usage`, () => new HttpResponse(null, { status: 500 }))
    );
    render(<UsagePage />);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Failed to load usage"));
  });
});
