"use client";

import { useRef, useState } from "react";
import { api } from "@/lib/api";

interface PdfUploadFormProps {
  onSuccess: () => void;
}

export function PdfUploadForm({ onSuccess }: PdfUploadFormProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null;
    setFile(f);
    setError(null);
    if (f && !title) setTitle(f.name.replace(/\.pdf$/i, ""));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setLoading(true);
    setError(null);

    const res = await api.content.uploadPdf(file, title || undefined);
    if (res.error) {
      setError(res.error.message);
    } else {
      setFile(null);
      setTitle("");
      if (inputRef.current) inputRef.current.value = "";
      onSuccess();
    }
    setLoading(false);
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-xl border border-gray-800 bg-gray-900 p-4 space-y-3"
    >
      <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wide">
        Upload PDF
      </h2>

      <div
        className="border-2 border-dashed border-gray-700 rounded-lg p-4 text-center cursor-pointer hover:border-gray-500 transition-colors"
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          const f = e.dataTransfer.files[0];
          if (f?.type === "application/pdf") {
            setFile(f);
            setError(null);
            if (!title) setTitle(f.name.replace(/\.pdf$/i, ""));
          } else {
            setError("Only PDF files are accepted");
          }
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          className="hidden"
          onChange={handleFileChange}
          aria-label="Choose PDF file"
        />
        {file ? (
          <p className="text-sm text-gray-300">
            📄 <span className="font-medium">{file.name}</span>{" "}
            <span className="text-gray-500">({(file.size / 1024).toFixed(0)} KB)</span>
          </p>
        ) : (
          <p className="text-sm text-gray-500">
            Drop a PDF here or <span className="text-blue-400 underline">browse</span>
          </p>
        )}
      </div>

      {file && (
        <div>
          <label htmlFor="pdf-title" className="block text-xs text-gray-400 mb-1">
            Title <span className="text-gray-600">(optional)</span>
          </label>
          <input
            id="pdf-title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Add a title..."
            className="w-full rounded-lg bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      )}

      {error && (
        <p className="text-xs text-red-400 bg-red-900/20 border border-red-800 rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={!file || loading}
        className="w-full rounded-lg bg-orange-600 hover:bg-orange-500 disabled:bg-gray-700 disabled:text-gray-500 px-4 py-2 text-sm font-medium transition-colors"
        aria-busy={loading}
      >
        {loading ? "Extracting & saving..." : "Upload PDF"}
      </button>
    </form>
  );
}
