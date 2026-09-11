import { useEffect, useState } from "react";
import { apiFetch } from "../api/client";
import * as s from "../layout/styles";

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
    <div className="flex max-w-[640px] flex-col gap-4">
      <div>
        <h1 className={s.pageTitle}>Personality</h1>
        <p className={s.pageDescription}>
          What the bot sounds like when it talks to customers. Changes take effect on the next
          message — no restart needed.
        </p>
      </div>

      {error && (
        <p role="alert" className={s.alertError}>
          {error}
        </p>
      )}

      {saved && <p className={s.alertSuccess}>Saved.</p>}

      <div className={`${s.card} flex flex-col gap-3.5 p-5`}>
        <label className={s.fieldLabel}>
          Bot personality
          <textarea
            aria-label="Bot personality"
            value={content}
            onChange={(e) => {
              setContent(e.target.value);
              setSaved(false);
            }}
            rows={16}
            className={`${s.input} resize-y font-[inherit]`}
          />
        </label>

        <button onClick={save} disabled={saving} className={`${s.btnPrimary} w-fit`}>
          Save
        </button>
      </div>
    </div>
  );
}
