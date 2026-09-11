import { useEffect, useState } from "react";
import { apiFetch } from "../api/client";
import * as s from "../layout/styles";

interface Document {
  id: number;
  filename: string;
  chunk_count: number;
  uploaded_at: string;
}

export function DocsPage() {
  const [docs, setDocs] = useState<Document[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);

  async function loadDocs(): Promise<void> {
    try {
      const data = await apiFetch<Document[]>("/admin/docs");
      setDocs(data);
    } catch {
      setError("Failed to load documents");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDocs();
  }, []);

  async function handleUpload(file: File): Promise<void> {
    setUploading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      await apiFetch<Document>("/admin/docs", { method: "POST", body: formData });
      await loadDocs();
    } catch {
      setError("Failed to upload document");
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(id: number): Promise<void> {
    setError(null);
    try {
      await apiFetch(`/admin/docs/${id}`, { method: "DELETE" });
      await loadDocs();
    } catch {
      setError("Failed to delete document");
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className={s.pageTitle}>Documents &amp; Recipes</h1>
          <p className={s.pageDescription}>Knowledge base the bot answers from.</p>
        </div>
        <label className={`${s.btnSecondary} flex cursor-pointer items-center gap-2 text-admin-fg shadow-admin-card`}>
          <span>{uploading ? "Uploading…" : "Upload document"}</span>
          <input
            type="file"
            disabled={uploading}
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) handleUpload(file);
              e.target.value = "";
            }}
          />
        </label>
      </div>
      {error && (
        <p role="alert" className={s.alertError}>
          {error}
        </p>
      )}
      <div className={`${s.card} overflow-x-auto`}>
        <table className="w-full">
          <thead>
            <tr>
              <th>Filename</th>
              <th>Chunks</th>
              <th>Uploaded</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={4} className={s.emptyCell}>
                  Loading documents…
                </td>
              </tr>
            ) : docs.length === 0 ? (
              <tr>
                <td colSpan={4} className={s.emptyCell}>
                  No documents yet — upload a .txt or .md file above.
                </td>
              </tr>
            ) : (
              docs.map((doc) => (
                <tr key={doc.id}>
                  <td className="font-semibold">{doc.filename}</td>
                  <td>{doc.chunk_count}</td>
                  <td className="text-admin-muted">{doc.uploaded_at}</td>
                  <td>
                    <button onClick={() => handleDelete(doc.id)} className={s.btnGhostDanger}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
