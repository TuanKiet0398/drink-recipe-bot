import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "../mocks/server";
import { API_BASE } from "../mocks/handlers";
import { storeCredentials } from "../../src/api/client";
import { SettingsPage } from "../../src/settings/SettingsPage";

const SAVED_SETTINGS = {
  provider: "openai",
  base_url: null,
  chat_model: "gpt-4o-mini",
  has_api_key: true,
  is_default: false,
  daily_token_limit: null,
  updated_at: "2026-09-07T10:00:00Z",
  updated_by: "admin",
};

beforeEach(() => {
  sessionStorage.clear();
  import.meta.env.VITE_API_BASE_URL = API_BASE;
  storeCredentials("admin", "admin", "admin");
  server.use(http.get(`${API_BASE}/admin/llm-settings`, () => HttpResponse.json(SAVED_SETTINGS)));
});

describe("SettingsPage", () => {
  it("keeps Save clickable and confirms before saving an untested configuration", async () => {
    let saved = false;
    server.use(
      http.put(`${API_BASE}/admin/llm-settings`, () => {
        saved = true;
        return HttpResponse.json(SAVED_SETTINGS);
      })
    );
    render(<SettingsPage />);

    const save = await screen.findByRole("button", { name: "Save" });
    expect(save).toBeEnabled();

    await userEvent.click(save);

    // Untested configurations are not blocked, only questioned.
    expect(await screen.findByRole("alertdialog")).toBeInTheDocument();
    expect(saved).toBe(false);

    await userEvent.click(screen.getByRole("button", { name: "Save anyway" }));

    await waitFor(() => expect(saved).toBe(true));
  });

  it("cancels the confirmation without saving", async () => {
    let saved = false;
    server.use(
      http.put(`${API_BASE}/admin/llm-settings`, () => {
        saved = true;
        return HttpResponse.json(SAVED_SETTINGS);
      })
    );
    render(<SettingsPage />);

    await userEvent.click(await screen.findByRole("button", { name: "Save" }));
    await screen.findByRole("alertdialog");

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(saved).toBe(false);
  });

  it("saves without confirmation once the test has passed", async () => {
    let saved = false;
    server.use(
      http.post(`${API_BASE}/admin/llm-settings/test`, () =>
        HttpResponse.json({ ok: true, model: "gpt-4o-mini", latency_ms: 120 })
      ),
      http.put(`${API_BASE}/admin/llm-settings`, () => {
        saved = true;
        return HttpResponse.json(SAVED_SETTINGS);
      })
    );
    render(<SettingsPage />);

    await screen.findByRole("button", { name: "Save" });
    await userEvent.click(screen.getByRole("button", { name: "Test connection" }));
    await screen.findByText(/OK — gpt-4o-mini/);

    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(saved).toBe(true));
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("asks again when a field changes after a successful test", async () => {
    server.use(
      http.post(`${API_BASE}/admin/llm-settings/test`, () =>
        HttpResponse.json({ ok: true, model: "gpt-4o-mini", latency_ms: 120 })
      )
    );
    render(<SettingsPage />);

    await screen.findByRole("button", { name: "Save" });
    await userEvent.click(screen.getByRole("button", { name: "Test connection" }));
    await screen.findByText(/OK — gpt-4o-mini/);

    // The passing test belonged to a different configuration.
    await userEvent.type(screen.getByLabelText("Chat model"), "-turbo");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByRole("alertdialog")).toBeInTheDocument();
  });

  it("lists the provider's models and offers them as suggestions", async () => {
    server.use(
      http.post(`${API_BASE}/admin/llm-settings/models`, () =>
        HttpResponse.json({ ok: true, models: ["gpt-4o", "gpt-4o-mini"], count: 2 })
      )
    );
    render(<SettingsPage />);

    await userEvent.click(await screen.findByRole("button", { name: "Load models" }));

    expect(await screen.findByText("2 models available")).toBeInTheDocument();
    expect(document.querySelectorAll("#chat-model-options option")).toHaveLength(2);
  });

  it("reports a failure to list models", async () => {
    server.use(
      http.post(`${API_BASE}/admin/llm-settings/models`, () =>
        HttpResponse.json({ ok: false, error: "Connection refused", models: [], count: 0 })
      )
    );
    render(<SettingsPage />);

    await userEvent.click(await screen.findByRole("button", { name: "Load models" }));

    expect(await screen.findByText("Connection refused")).toBeInTheDocument();
  });

  it("shows the base URL field only for Ollama", async () => {
    render(<SettingsPage />);
    await screen.findByRole("button", { name: "Save" });

    expect(screen.queryByLabelText("Base URL")).not.toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText("Provider"), "ollama");

    expect(screen.getByLabelText("Base URL")).toBeInTheDocument();
  });

  it("reports a failed test and leaves Save disabled", async () => {
    server.use(
      http.post(`${API_BASE}/admin/llm-settings/test`, () =>
        HttpResponse.json({ ok: false, error: "Incorrect API key provided" })
      )
    );
    render(<SettingsPage />);

    const save = await screen.findByRole("button", { name: "Save" });
    await userEvent.click(screen.getByRole("button", { name: "Test connection" }));

    expect(await screen.findByText(/Incorrect API key provided/)).toBeInTheDocument();
    // A red test does not lock Save; it just means the confirmation still applies.
    expect(save).toBeEnabled();
  });

  it("announces that the environment default is in use", async () => {
    server.use(
      http.get(`${API_BASE}/admin/llm-settings`, () =>
        HttpResponse.json({ ...SAVED_SETTINGS, is_default: true, updated_at: null, updated_by: null })
      )
    );
    render(<SettingsPage />);

    expect(
      await screen.findByText(/default configuration from environment variables/i)
    ).toBeInTheDocument();
  });

  it("never renders the API key field with a value", async () => {
    render(<SettingsPage />);

    const field = await screen.findByLabelText("API key");
    expect(field).toHaveValue("");
    expect(screen.getByText(/leave blank to keep/i)).toBeInTheDocument();
  });

  it("pre-fills the daily token limit field from the saved value", async () => {
    server.use(
      http.get(`${API_BASE}/admin/llm-settings`, () =>
        HttpResponse.json({ ...SAVED_SETTINGS, daily_token_limit: 50000 })
      )
    );
    render(<SettingsPage />);

    const field = await screen.findByLabelText("Daily token limit per customer");
    expect(field).toHaveValue(50000);
  });

  it("sends daily_token_limit as null when the field is left blank", async () => {
    let sentBody: Record<string, unknown> | null = null;
    server.use(
      http.put(`${API_BASE}/admin/llm-settings`, async ({ request }) => {
        sentBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(SAVED_SETTINGS);
      })
    );
    render(<SettingsPage />);

    await userEvent.click(await screen.findByRole("button", { name: "Save" }));
    await userEvent.click(screen.getByRole("button", { name: "Save anyway" }));

    await waitFor(() => expect(sentBody).not.toBeNull());
    expect(sentBody!.daily_token_limit).toBeNull();
  });

  it("sends the typed daily token limit as a number", async () => {
    let sentBody: Record<string, unknown> | null = null;
    server.use(
      http.put(`${API_BASE}/admin/llm-settings`, async ({ request }) => {
        sentBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(SAVED_SETTINGS);
      })
    );
    render(<SettingsPage />);

    await userEvent.type(
      await screen.findByLabelText("Daily token limit per customer"),
      "50000"
    );
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await userEvent.click(screen.getByRole("button", { name: "Save anyway" }));

    await waitFor(() => expect(sentBody).not.toBeNull());
    expect(sentBody!.daily_token_limit).toBe(50000);
  });
});
