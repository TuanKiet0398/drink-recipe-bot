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
  updated_at: "2026-09-07T10:00:00Z",
  updated_by: "admin",
};

beforeEach(() => {
  sessionStorage.clear();
  import.meta.env.VITE_API_BASE_URL = API_BASE;
  storeCredentials("admin", "admin");
  server.use(http.get(`${API_BASE}/admin/llm-settings`, () => HttpResponse.json(SAVED_SETTINGS)));
});

describe("SettingsPage", () => {
  it("keeps Save disabled until a test succeeds", async () => {
    server.use(
      http.post(`${API_BASE}/admin/llm-settings/test`, () =>
        HttpResponse.json({ ok: true, model: "gpt-4o-mini", latency_ms: 120 })
      )
    );
    render(<SettingsPage />);

    const save = await screen.findByRole("button", { name: "Save" });
    expect(save).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: "Test connection" }));

    await waitFor(() => expect(save).toBeEnabled());
  });

  it("disables Save again when a field changes after a successful test", async () => {
    server.use(
      http.post(`${API_BASE}/admin/llm-settings/test`, () =>
        HttpResponse.json({ ok: true, model: "gpt-4o-mini", latency_ms: 120 })
      )
    );
    render(<SettingsPage />);

    const save = await screen.findByRole("button", { name: "Save" });
    await userEvent.click(screen.getByRole("button", { name: "Test connection" }));
    await waitFor(() => expect(save).toBeEnabled());

    // A configuration must never be saved on the strength of a test of a
    // different configuration.
    await userEvent.type(screen.getByLabelText("Chat model"), "-turbo");

    expect(save).toBeDisabled();
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
    expect(save).toBeDisabled();
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
});
