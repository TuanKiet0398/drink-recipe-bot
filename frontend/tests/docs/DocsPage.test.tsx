import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, beforeEach } from "vitest";
import { server } from "../mocks/server";
import { API_BASE } from "../mocks/handlers";
import { getStoredCredentials, storeCredentials } from "../../src/api/client";
import { DocsPage } from "../../src/docs/DocsPage";

beforeEach(() => {
  sessionStorage.clear();
  import.meta.env.VITE_API_BASE_URL = API_BASE;
  storeCredentials("admin", "admin", "admin");
});

describe("DocsPage", () => {
  it("lists documents fetched from the backend", async () => {
    server.use(
      http.get(`${API_BASE}/admin/docs`, () =>
        HttpResponse.json([{ id: 1, filename: "brewing.txt", chunk_count: 3, uploaded_at: "2026-09-02" }])
      )
    );
    render(<DocsPage />);
    await waitFor(() => expect(screen.getByText("brewing.txt")).toBeInTheDocument());
  });

  it("uploads a file and reloads the list", async () => {
    let uploaded = false;
    server.use(
      http.get(`${API_BASE}/admin/docs`, () =>
        HttpResponse.json(uploaded ? [{ id: 2, filename: "recipe.txt", chunk_count: 1, uploaded_at: "now" }] : [])
      ),
      http.post(`${API_BASE}/admin/docs`, () => {
        uploaded = true;
        return HttpResponse.json({ id: 2, filename: "recipe.txt", chunk_count: 1 }, { status: 201 });
      })
    );
    render(<DocsPage />);
    await waitFor(() => expect(screen.queryByText("recipe.txt")).not.toBeInTheDocument());

    const file = new File(["matcha steeping steps"], "recipe.txt", { type: "text/plain" });
    const input = screen.getByLabelText("Upload document") as HTMLInputElement;
    await userEvent.upload(input, file);

    await waitFor(() => expect(screen.getByText("recipe.txt")).toBeInTheDocument());
  });

  it("deletes a document and reloads the list", async () => {
    let deleted = false;
    server.use(
      http.get(`${API_BASE}/admin/docs`, () =>
        HttpResponse.json(deleted ? [] : [{ id: 3, filename: "old.txt", chunk_count: 1, uploaded_at: "now" }])
      ),
      http.delete(`${API_BASE}/admin/docs/3`, () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      })
    );
    render(<DocsPage />);
    await waitFor(() => expect(screen.getByText("old.txt")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(screen.queryByText("old.txt")).not.toBeInTheDocument());
  });

  it("shows an error message when the doc list fails to load", async () => {
    server.use(http.get(`${API_BASE}/admin/docs`, () => new HttpResponse(null, { status: 500 })));
    render(<DocsPage />);
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Failed to load documents"));
  });

  it("clears stored credentials when the upload request comes back 401", async () => {
    server.use(
      http.get(`${API_BASE}/admin/docs`, () => HttpResponse.json([])),
      http.post(`${API_BASE}/admin/docs`, () => new HttpResponse(null, { status: 401 }))
    );
    render(<DocsPage />);
    await waitFor(() => expect(getStoredCredentials()).not.toBeNull());

    const file = new File(["matcha steeping steps"], "recipe.txt", { type: "text/plain" });
    const input = screen.getByLabelText("Upload document") as HTMLInputElement;
    await userEvent.upload(input, file);

    await waitFor(() => expect(getStoredCredentials()).toBeNull());
  });
});
