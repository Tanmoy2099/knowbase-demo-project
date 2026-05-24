"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { api } from "@/lib/api";
import { useContentItem } from "@/hooks/useContent";
import type { ContentItem, ContentType } from "@/types";

interface ContentCardProps {
  item: ContentItem;
  onRefresh?: () => void;
}

const TYPE_LABELS: Record<ContentType, string> = {
  link: "Link",
  youtube: "YouTube",
  note: "Note",
  pdf: "PDF",
};

const TYPE_COLORS: Record<ContentType, string> = {
  link: "bg-blue-900/40 text-blue-300",
  youtube: "bg-red-900/40 text-red-300",
  note: "bg-green-900/40 text-green-300",
  pdf: "bg-orange-900/40 text-orange-300",
};

function StatusDot({ status }: { status: ContentItem["status"] }) {
  if (status === "enriched") return <span className="inline-block w-2 h-2 rounded-full bg-green-400" aria-label="Enriched" />;
  if (status === "failed") return <span className="inline-block w-2 h-2 rounded-full bg-red-400" aria-label="Failed" />;
  return (
    <span className="inline-flex items-center gap-1 text-xs text-yellow-400">
      <span className="inline-block w-2 h-2 rounded-full bg-yellow-400 animate-pulse" />
      {status === "fetching" ? "Processing..." : "Pending..."}
    </span>
  );
}

function ExternalLinkButton({ url }: { url: string }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      onClick={(e) => e.stopPropagation()}
      className="inline-flex items-center gap-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 border border-gray-700 hover:border-gray-600 px-3 py-1.5 text-xs text-gray-300 hover:text-white transition-all"
    >
      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
      </svg>
      Open in new tab
    </a>
  );
}

export function ContentCard({ item, onRefresh }: ContentCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const { item: detail } = useContentItem(expanded ? item.id : null);

  async function handleDelete(e: React.MouseEvent) {
    e.stopPropagation();
    if (!confirm("Delete this item?")) return;
    setDeleting(true);
    await api.content.delete(item.id);
    onRefresh?.();
  }

  const displayTitle = item.title ?? item.raw_url ?? "Untitled";
  const hasExternalUrl = (item.type === "link" || item.type === "youtube") && item.raw_url;

  return (
    <article
      className="rounded-xl border border-gray-800 bg-gray-900 transition-colors hover:border-gray-700"
      aria-expanded={expanded}
    >
      {/* Header row */}
      <div
        className="flex items-start gap-3 p-4 cursor-pointer"
        onClick={() => setExpanded((v) => !v)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && setExpanded((v) => !v)}
      >
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium shrink-0 ${TYPE_COLORS[item.type]}`}>
          {TYPE_LABELS[item.type]}
        </span>

        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-200 truncate" title={displayTitle}>
            {displayTitle}
          </p>
          {item.raw_url && item.title && (
            <p className="text-xs text-gray-500 truncate">{item.raw_url}</p>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <StatusDot status={item.status} />
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="text-gray-600 hover:text-red-400 text-xs transition-colors"
            aria-label="Delete item"
          >
            &#x2715;
          </button>
        </div>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-gray-800 px-4 pb-4 pt-3 space-y-3">

          {/* External link button */}
          {hasExternalUrl && (
            <ExternalLinkButton url={item.raw_url!} />
          )}

          {/* AI Summary with markdown rendering */}
          {detail?.summary && (
            <div className="bg-gray-800/50 rounded-lg p-4">
              <p className="text-xs text-gray-500 mb-3 font-medium uppercase tracking-wide">AI Summary</p>
              <div className="prose prose-sm prose-invert max-w-none text-gray-300
                [&_strong]:text-gray-100 [&_strong]:font-semibold
                [&_ul]:mt-2 [&_ul]:space-y-1 [&_ul]:pl-0 [&_ul]:list-none
                [&_li]:flex [&_li]:items-start [&_li]:gap-2
                [&_li]:before:content-['•'] [&_li]:before:text-blue-400 [&_li]:before:shrink-0 [&_li]:before:mt-0.5
                [&_p]:leading-relaxed [&_p]:mb-2 last:[&_p]:mb-0
              ">
                <ReactMarkdown>{detail.summary.text}</ReactMarkdown>
              </div>
              {detail.summary.ai_provider && (
                <p className="text-xs text-gray-600 mt-3 pt-3 border-t border-gray-700/50">
                  via {detail.summary.ai_provider} · {detail.summary.model}
                </p>
              )}
            </div>
          )}

          {/* Tags */}
          {detail?.tags && detail.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {detail.tags.map((tag) => (
                <span
                  key={tag.id}
                  className="rounded-full bg-gray-800 text-gray-400 text-xs px-2 py-0.5"
                >
                  #{tag.name}
                </span>
              ))}
            </div>
          )}

          {/* Collections */}
          {detail?.collections && detail.collections.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {detail.collections.map((col) => (
                <span
                  key={col.id}
                  className="rounded-full bg-indigo-900/40 text-indigo-300 text-xs px-2 py-0.5"
                >
                  {col.name}
                </span>
              ))}
            </div>
          )}

          {item.body && (
            <p className="text-sm text-gray-400 whitespace-pre-wrap">{item.body}</p>
          )}

          <p className="text-xs text-gray-600">
            {new Date(item.created_at).toLocaleString()}
          </p>
        </div>
      )}
    </article>
  );
}
