import { useEffect, useState } from "react";
import { apiFetch } from "../api/client";

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

  async function loadDocs(): Promise<void> {
    try {
      const data = await apiFetch<Document[]>("/admin/docs");
      setDocs(data);
    } catch {
      setError("Failed to load documents");
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
      <h1 className="text-xl font-semibold">Documents &amp; Recipes</h1>
      <label className="flex items-center gap-2">
        <span>Upload document</span>
        <input
          type="file"
          disabled={uploading}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleUpload(file);
            e.target.value = "";
          }}
        />
      </label>
      {error && (
        <p role="alert" className="text-red-600">
          {error}
        </p>
      )}
      <table className="w-full text-left border-collapse">
        <thead>
          <tr>
            <th>Filename</th>
            <th>Chunks</th>
            <th>Uploaded</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {docs.map((doc) => (
            <tr key={doc.id}>
              <td>{doc.filename}</td>
              <td>{doc.chunk_count}</td>
              <td>{doc.uploaded_at}</td>
              <td>
                <button onClick={() => handleDelete(doc.id)} className="text-red-600 underline">
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
