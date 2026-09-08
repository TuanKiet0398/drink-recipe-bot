import { useEffect, useState } from "react";
import { apiFetch } from "../api/client";

interface LLMSettings {
  provider: string;
  base_url: string | null;
  chat_model: string;
  has_api_key: boolean;
  is_default: boolean;
  daily_token_limit: number | null;
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
  dailyTokenLimit: string;
}

const fieldClass =
  "rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none";

const OLLAMA_PLACEHOLDER = "http://host.docker.internal:11434/v1";

export function SettingsPage() {
  const [settings, setSettings] = useState<LLMSettings | null>(null);
  const [form, setForm] = useState<FormState>({
    provider: "openai",
    baseUrl: "",
    apiKey: "",
    chatModel: "",
    dailyTokenLimit: "",
  });
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [models, setModels] = useState<string[] | null>(null);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [loadingModels, setLoadingModels] = useState(false);
  const [confirming, setConfirming] = useState(false);

  async function load(): Promise<void> {
    try {
      const data = await apiFetch<LLMSettings>("/admin/llm-settings");
      setSettings(data);
      setForm({
        provider: data.provider,
        baseUrl: data.base_url ?? "",
        apiKey: "",
        chatModel: data.chat_model,
        dailyTokenLimit: data.daily_token_limit === null ? "" : String(data.daily_token_limit),
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
    setConfirming(false);
    // Changing the provider, URL or key invalidates the model list too: it
    // came from whatever server was configured a moment ago.
    if (patch.chatModel === undefined) {
      setModels(null);
      setModelsError(null);
    }
    setForm((current) => ({ ...current, ...patch }));
  }

  function payload() {
    return {
      provider: form.provider,
      chat_model: form.chatModel,
      base_url: form.provider === "ollama" ? form.baseUrl : null,
      api_key: form.apiKey === "" ? null : form.apiKey,
      daily_token_limit:
        form.dailyTokenLimit === "" || Number.isNaN(Number(form.dailyTokenLimit))
          ? null
          : Number(form.dailyTokenLimit),
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

  async function loadModels(): Promise<void> {
    setLoadingModels(true);
    try {
      const result = await apiFetch<{ ok: boolean; models: string[]; count: number; error?: string }>(
        "/admin/llm-settings/models",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload()),
        }
      );
      if (result.ok) {
        setModels(result.models);
        setModelsError(null);
      } else {
        setModels(null);
        setModelsError(result.error ?? "Failed to list models");
      }
    } catch {
      setModels(null);
      setModelsError("Failed to reach the server");
    } finally {
      setLoadingModels(false);
    }
  }

  async function save(): Promise<void> {
    setSaving(true);
    try {
      setConfirming(false);
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

  const tested = testResult?.ok === true;

  // Save is never disabled — an admin may know the configuration is right.
  // Saving untested asks for confirmation first, because a wrong provider
  // makes the bot fail for real customers.
  function onSaveClick(): void {
    if (tested) {
      save();
    } else {
      setConfirming(true);
    }
  }

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
          {/* An input with a datalist, not a select: the list may fail to load,
              or hold a model the provider does not advertise, and typing must
              still work. */}
          <input
            aria-label="Chat model"
            list="chat-model-options"
            value={form.chatModel}
            onChange={(e) => update({ chatModel: e.target.value })}
            className={fieldClass}
          />
          <datalist id="chat-model-options">
            {(models ?? []).map((name) => (
              <option key={name} value={name} />
            ))}
          </datalist>
          <span className="flex items-center gap-2">
            <button
              type="button"
              onClick={loadModels}
              disabled={loadingModels}
              className="rounded-md border border-border bg-card px-2 py-1 text-xs font-medium text-foreground hover:bg-muted disabled:opacity-50"
            >
              {loadingModels ? "Loading…" : "Load models"}
            </button>
            {models !== null && (
              <span className="text-xs text-muted-foreground">
                {models.length} {models.length === 1 ? "model" : "models"} available
              </span>
            )}
            {modelsError && <span className="text-xs text-red-700">{modelsError}</span>}
          </span>
        </label>

        <label className="flex flex-col gap-1 text-sm font-medium text-foreground">
          Daily token limit per customer
          <input
            aria-label="Daily token limit per customer"
            type="number"
            min={1}
            value={form.dailyTokenLimit}
            onChange={(e) => update({ dailyTokenLimit: e.target.value })}
            className={fieldClass}
          />
          <span className="text-xs text-muted-foreground">
            Leave blank for no limit. A customer who reaches this gets a polite reply instead of a
            new reply from the bot until the next day.
          </span>
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
            onClick={onSaveClick}
            disabled={saving}
            className="w-fit rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-dark disabled:cursor-not-allowed disabled:opacity-50"
          >
            Save
          </button>
          {confirming && (
            <div
              role="alertdialog"
              aria-label="Confirm saving without testing"
              className="flex flex-col gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900"
            >
              <span>
                Connection not tested. Saving a broken configuration makes the bot fail for real
                customers. Save anyway?
              </span>
              <span className="flex gap-2">
                <button
                  type="button"
                  onClick={save}
                  className="rounded-md bg-amber-600 px-3 py-1 text-xs font-medium text-white hover:bg-amber-700"
                >
                  Save anyway
                </button>
                <button
                  type="button"
                  onClick={() => setConfirming(false)}
                  className="rounded-md border border-amber-300 bg-white px-3 py-1 text-xs font-medium text-amber-900 hover:bg-amber-100"
                >
                  Cancel
                </button>
              </span>
            </div>
          )}
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
