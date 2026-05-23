"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { ContentType, CreateContentRequest } from "@/types";

interface ContentSaveFormProps {
  onSuccess: () => void;
}

const CONTENT_TYPES: { value: ContentType; label: string }[] = [
  { value: "link", label: "Link" },
  { value: "youtube", label: "YouTube" },
  { value: "note", label: "Note" },
  { value: "pdf", label: "PDF" },
];

export function ContentSaveForm({ onSuccess }: ContentSaveFormProps) {
  const [type, setType] = useState<ContentType>("link");
  const [rawUrl, setRawUrl] = useState("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const payload: CreateContentRequest = { type };
    if (rawUrl) payload.raw_url = rawUrl;
    if (title) payload.title = title;
    if (body) payload.body = body;

    const res = await api.content.create(payload);

    if (res.error) {
      setError(res.error.message);
    } else {
      setRawUrl("");
      setTitle("");
      setBody("");
      onSuccess();
    }

    setLoading(false);
  }

  const needsUrl = type === "link" || type === "youtube";
  const needsBody = type === "note";

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-xl border border-gray-800 bg-gray-900 p-4 space-y-3"
    >
      <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wide">
        Save Content
      </h2>

      {/* Type selector */}
      <div className="flex gap-2">
        {CONTENT_TYPES.map((t) => (
          <button
            key={t.value}
            type="button"
            onClick={() => setType(t.value)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              type === t.value
                ? "bg-blue-600 text-white"
                : "bg-gray-800 text-gray-400 hover:bg-gray-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* URL field */}
      {needsUrl && (
        <div>
          <label htmlFor="raw_url" className="block text-xs text-gray-400 mb-1">
            URL <span className="text-red-400">*</span>
          </label>
          <input
            id="raw_url"
            type="url"
            value={rawUrl}
            onChange={(e) => setRawUrl(e.target.value)}
            required
            placeholder={type === "youtube" ? "https://youtube.com/watch?v=..." : "https://..."}
            className="w-full rounded-lg bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      )}

      {/* Title */}
      <div>
        <label htmlFor="title" className="block text-xs text-gray-400 mb-1">
          Title <span className="text-gray-600">(optional)</span>
        </label>
        <input
          id="title"
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Add a title..."
          className="w-full rounded-lg bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {/* Body */}
      {(needsBody || type === "pdf") && (
        <div>
          <label htmlFor="body" className="block text-xs text-gray-400 mb-1">
            Content{needsBody && <span className="text-red-400"> *</span>}
          </label>
          <textarea
            id="body"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            required={needsBody}
            rows={4}
            placeholder="Paste your note or content..."
            className="w-full rounded-lg bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
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
        disabled={loading}
        className="w-full rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 px-4 py-2 text-sm font-medium transition-colors"
        aria-busy={loading}
      >
        {loading ? "Saving..." : "Save"}
      </button>
    </form>
  );
}
