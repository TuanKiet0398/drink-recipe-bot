import { useEffect, useState } from "react";
import { apiFetch } from "../api/client";

interface LLMSettings {
  provider: string;
  base_url: string | null;
  chat_model: string;
  has_api_key: boolean;
  is_default: boolean;
  updated_at: string | null;
  updated_by: string | null;
}

interface TestResult {
  ok: boolean;
  model?: string;
  latency_ms?: number;
  error?: string;
}

interface FormState {
  provider: string;
  baseUrl: string;
  apiKey: string;
  chatModel: string;
}

const fieldClass =
  "rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none";

const OLLAMA_PLACEHOLDER = "http://host.docker.internal:11434/v1";

export function SettingsPage() {
  const [settings, setSettings] = useState<LLMSettings | null>(null);
  const [form, setForm] = useState<FormState>({ provider: "openai", baseUrl: "", apiKey: "", chatModel: "" });
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  async function load(): Promise<void> {
    try {
      const data = await apiFetch<LLMSettings>("/admin/llm-settings");
      setSettings(data);
      setForm({
        provider: data.provider,
        baseUrl: data.base_url ?? "",
        apiKey: "",
        chatModel: data.chat_model,
      });
      setError(null);
    } catch {
      setError("Failed to load settings");
    }
  }

  useEffect(() => {
    load();
  }, []);

  // Any edit invalidates a previous test result: otherwise a configuration
  // could be saved on the strength of a test of a different configuration.
  function update(patch: Partial<FormState>): void {
    setTestResult(null);
    setSaved(false);
    setForm((current) => ({ ...current, ...patch }));
  }

  function payload() {
    return {
      provider: form.provider,
      chat_model: form.chatModel,
      base_url: form.provider === "ollama" ? form.baseUrl : null,
      api_key: form.apiKey === "" ? null : form.apiKey,
    };
  }

  async function runTest(): Promise<void> {
    setTesting(true);
    try {
      const result = await apiFetch<TestResult>("/admin/llm-settings/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload()),
      });
      setTestResult(result);
      setError(null);
    } catch {
      setError("Failed to reach the server");
    } finally {
      setTesting(false);
    }
  }

  async function save(): Promise<void> {
    setSaving(true);
    try {
      await apiFetch<LLMSettings>("/admin/llm-settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload()),
      });
      setTestResult(null);
      setSaved(true);
      // Re-read so the page shows what the server holds, not what was typed.
      await load();
    } catch {
      setError("Failed to save settings");
    } finally {
      setSaving(false);
    }
  }

  const canSave = testResult?.ok === true && !saving;

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Choose the LLM provider used for the bot&apos;s conversation.
        </p>
      </div>

      {error && (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {settings?.is_default && (
        <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Using the default configuration from environment variables. Saving here overrides it.
        </p>
      )}

      {saved && <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-800">Settings saved.</p>}

      <div className="flex max-w-xl flex-col gap-4 rounded-lg border border-border bg-card p-5 shadow-card">
        <label className="flex flex-col gap-1 text-sm font-medium text-foreground">
          Provider
          <select
            aria-label="Provider"
            value={form.provider}
            onChange={(e) => update({ provider: e.target.value })}
            className={fieldClass}
          >
            <option value="openai">OpenAI</option>
            <option value="ollama">Ollama</option>
          </select>
        </label>

        {form.provider === "ollama" && (
          <label className="flex flex-col gap-1 text-sm font-medium text-foreground">
            Base URL
            <input
              aria-label="Base URL"
              value={form.baseUrl}
              placeholder={OLLAMA_PLACEHOLDER}
              onChange={(e) => update({ baseUrl: e.target.value })}
              className={fieldClass}
            />
          </label>
        )}

        <label className="flex flex-col gap-1 text-sm font-medium text-foreground">
          API key
          <input
            aria-label="API key"
            type="password"
            value={form.apiKey}
            onChange={(e) => update({ apiKey: e.target.value })}
            className={fieldClass}
          />
          {settings?.has_api_key && (
            <span className="text-xs text-muted-foreground">Saved — leave blank to keep the current key.</span>
          )}
        </label>

        <label className="flex flex-col gap-1 text-sm font-medium text-foreground">
          Chat model
          <input
            aria-label="Chat model"
            value={form.chatModel}
            onChange={(e) => update({ chatModel: e.target.value })}
            className={fieldClass}
          />
        </label>

        <div className="flex items-center gap-3">
          <button
            onClick={runTest}
            disabled={testing}
            className="rounded-md border border-border bg-card px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted disabled:opacity-50"
          >
            Test connection
          </button>
          {testResult?.ok === true && (
            <span className="text-sm text-emerald-700">
              OK — {testResult.model}, {testResult.latency_ms}ms
            </span>
          )}
          {testResult?.ok === false && <span className="text-sm text-red-700">{testResult.error}</span>}
        </div>

        <div className="flex flex-col gap-2">
          <button
            onClick={save}
            disabled={!canSave}
            className="w-fit rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-dark disabled:cursor-not-allowed disabled:opacity-50"
          >
            Save
          </button>
          {form.provider === "ollama" && (
            <span className="text-xs text-muted-foreground">
              Ollama has no per-token cost, so the cost chart will read zero.
            </span>
          )}
        </div>
      </div>

      <p className="text-xs text-muted-foreground">
        Embeddings always use OpenAI (text-embedding-3-small). Changing the provider here does not affect the
        knowledge base.
      </p>
    </div>
  );
}
