"use client";

import { useState } from "react";
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

export function ContentCard({ item, onRefresh }: ContentCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [deleting, setDeleting] = useState(false);

  // Only load detail (with summary/tags) when expanded
  const { item: detail } = useContentItem(expanded ? item.id : null);

  async function handleDelete(e: React.MouseEvent) {
    e.stopPropagation();
    if (!confirm("Delete this item?")) return;
    setDeleting(true);
    await api.content.delete(item.id);
    onRefresh?.();
  }

  const displayTitle = item.title ?? item.raw_url ?? "Untitled";

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
          {detail?.summary && (
            <div className="text-sm text-gray-300 bg-gray-800/50 rounded-lg p-3">
              <p className="text-xs text-gray-500 mb-1">AI Summary</p>
              <p>{detail.summary.text}</p>
              {detail.summary.ai_provider && (
                <p className="text-xs text-gray-600 mt-1">
                  via {detail.summary.ai_provider} / {detail.summary.model}
                </p>
              )}
            </div>
          )}

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
