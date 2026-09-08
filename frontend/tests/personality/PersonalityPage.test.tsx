import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "../mocks/server";
import { API_BASE } from "../mocks/handlers";
import { storeCredentials } from "../../src/api/client";
import { PersonalityPage } from "../../src/personality/PersonalityPage";

beforeEach(() => {
  sessionStorage.clear();
  import.meta.env.VITE_API_BASE_URL = API_BASE;
  storeCredentials("admin", "admin");
  server.use(
    http.get(`${API_BASE}/admin/soul`, () => HttpResponse.json({ content: "Friendly and knowledgeable." }))
  );
});

describe("PersonalityPage", () => {
  it("loads and displays the current personality text", async () => {
    render(<PersonalityPage />);

    const field = await screen.findByLabelText("Bot personality");
    expect(field).toHaveValue("Friendly and knowledgeable.");
  });

  it("saves the edited text", async () => {
    let sentBody: Record<string, unknown> | null = null;
    server.use(
      http.put(`${API_BASE}/admin/soul`, async ({ request }) => {
        sentBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ content: sentBody.content });
      })
    );
    render(<PersonalityPage />);

    const field = await screen.findByLabelText("Bot personality");
    await userEvent.clear(field);
    await userEvent.type(field, "Warmer and more playful.");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(sentBody).not.toBeNull());
    expect(sentBody!.content).toBe("Warmer and more playful.");
    expect(await screen.findByText(/saved/i)).toBeInTheDocument();
  });

  it("reports a failure to save", async () => {
    server.use(http.put(`${API_BASE}/admin/soul`, () => HttpResponse.json({}, { status: 500 })));
    render(<PersonalityPage />);

    await screen.findByLabelText("Bot personality");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText(/failed to save/i)).toBeInTheDocument();
  });
});
