import { useEffect, useState } from "react";
import { apiFetch } from "../api/client";

interface SoulResponse {
  content: string;
}

export function PersonalityPage() {
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    async function load(): Promise<void> {
      try {
        const data = await apiFetch<SoulResponse>("/admin/soul");
        setContent(data.content);
        setError(null);
      } catch {
        setError("Failed to load personality");
      }
    }
    load();
  }, []);

  async function save(): Promise<void> {
    setSaving(true);
    try {
      await apiFetch<SoulResponse>("/admin/soul", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });
      setSaved(true);
      setError(null);
    } catch {
      setError("Failed to save personality");
      setSaved(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-xl font-semibold text-foreground">Personality</h1>
        <p className="text-sm text-muted-foreground">
          What the bot sounds like when it talks to customers. Changes take effect on the next
          message — no restart needed.
        </p>
      </div>

      {error && (
        <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {saved && <p className="rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-800">Saved.</p>}

      <div className="flex max-w-2xl flex-col gap-4 rounded-lg border border-border bg-card p-5 shadow-card">
        <label className="flex flex-col gap-1 text-sm font-medium text-foreground">
          Bot personality
          <textarea
            aria-label="Bot personality"
            value={content}
            onChange={(e) => {
              setContent(e.target.value);
              setSaved(false);
            }}
            rows={16}
            className="rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground focus:border-primary focus:outline-none"
          />
        </label>

        <button
          onClick={save}
          disabled={saving}
          className="w-fit rounded-md bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary-dark disabled:cursor-not-allowed disabled:opacity-50"
        >
          Save
        </button>
      </div>
    </div>
  );
}
