"use client";

import { useState, useMemo } from "react";
import { api } from "@/lib/api";
import type { ContentType, CreateContentRequest } from "@/types";

interface ContentSaveFormProps {
  onSuccess: () => void;
}

const TYPE_META: Record<ContentType, { label: string; icon: string; color: string }> = {
  youtube: { label: "YouTube", icon: "▶", color: "text-red-400 bg-red-900/30 border-red-800/50" },
  link:    { label: "Link",    icon: "🔗", color: "text-blue-400 bg-blue-900/30 border-blue-800/50" },
  note:    { label: "Note",    icon: "📝", color: "text-green-400 bg-green-900/30 border-green-800/50" },
  pdf:     { label: "PDF",     icon: "📄", color: "text-orange-400 bg-orange-900/30 border-orange-800/50" },
};

function detectType(input: string): ContentType {
  const s = input.trim();
  if (!s) return "note";
  if (/(?:youtube\.com\/(?:watch|shorts|embed|live|playlist)|youtu\.be\/)/i.test(s)) return "youtube";
  if (/^https?:\/\//i.test(s)) return "link";
  return "note";
}

export function ContentSaveForm({ onSuccess }: ContentSaveFormProps) {
  const [input, setInput] = useState("");
  const [title, setTitle] = useState("");
  const [extraContext, setExtraContext] = useState("");
  const [userInstructions, setUserInstructions] = useState("");
  const [showMore, setShowMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const detectedType = useMemo(() => detectType(input), [input]);
  const meta = TYPE_META[detectedType];
  const isUrl = detectedType === "link" || detectedType === "youtube";

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    const trimmed = input.trim();
    if (!trimmed) {
      setError("Please enter a URL or note text.");
      return;
    }

    setLoading(true);

    const payload: CreateContentRequest = { type: detectedType };
    if (isUrl) payload.raw_url = trimmed;
    else payload.body = trimmed;
    if (title) payload.title = title;
    if (extraContext) payload.extra_context = extraContext;
    if (userInstructions) payload.user_instructions = userInstructions;

    const res = await api.content.create(payload);

    if (res.error) {
      setError(res.error.message);
    } else {
      setInput("");
      setTitle("");
      setExtraContext("");
      setUserInstructions("");
      setShowMore(false);
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
        Save Content
      </h2>

      {/* Single smart input */}
      <div>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          rows={isUrl ? 1 : 3}
          placeholder="Paste a YouTube or website URL, or type a note…"
          className="w-full rounded-lg bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none transition-all"
        />
        {/* Detected-type badge */}
        {input.trim() && (
          <div className="mt-1.5 flex items-center gap-1.5">
            <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border ${meta.color}`}>
              <span>{meta.icon}</span>
              <span>{meta.label}</span>
            </span>
            <span className="text-xs text-gray-600">detected automatically</span>
          </div>
        )}
      </div>

      {/* More options toggle */}
      <button
        type="button"
        onClick={() => setShowMore((v) => !v)}
        className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300 transition-colors"
      >
        <span className={`transition-transform ${showMore ? "rotate-90" : ""}`}>▶</span>
        {showMore ? "Fewer options" : "More options"}
        <span className="text-gray-600 ml-1">(title, context, instructions)</span>
      </button>

      {showMore && (
        <div className="space-y-3 pt-1">
          {/* Title */}
          <div>
            <label htmlFor="title" className="block text-xs text-gray-400 mb-1">
              Title <span className="text-gray-600">(optional — AI will generate one if blank)</span>
            </label>
            <input
              id="title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Override the AI-generated title…"
              className="w-full rounded-lg bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Extra context */}
          <div>
            <label htmlFor="extra_context" className="block text-xs text-gray-400 mb-1">
              Additional context <span className="text-gray-600">(optional)</span>
            </label>
            <textarea
              id="extra_context"
              value={extraContext}
              onChange={(e) => setExtraContext(e.target.value)}
              rows={2}
              placeholder="Any extra information the AI should know about this content…"
              className="w-full rounded-lg bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
            />
          </div>

          {/* User instructions */}
          <div>
            <label htmlFor="user_instructions" className="block text-xs text-gray-400 mb-1">
              AI instructions <span className="text-gray-600">(optional)</span>
            </label>
            <textarea
              id="user_instructions"
              value={userInstructions}
              onChange={(e) => setUserInstructions(e.target.value)}
              rows={2}
              placeholder="What should the AI focus on? e.g. 'Explain for a beginner' or 'Focus on security'"
              className="w-full rounded-lg bg-gray-800 border border-gray-700 px-3 py-2 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
            />
          </div>
        </div>
      )}

      {error && (
        <p className="text-xs text-red-400 bg-red-900/20 border border-red-800 rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={loading || !input.trim()}
        className="w-full rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 px-4 py-2 text-sm font-medium transition-colors"
        aria-busy={loading}
      >
        {loading ? "Saving…" : "Save"}
      </button>
    </form>
  );
}
