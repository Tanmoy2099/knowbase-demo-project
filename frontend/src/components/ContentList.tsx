"use client";

import { useEffect } from "react";
import { useContentList } from "@/hooks/useContent";
import { ContentCard } from "./ContentCard";
import type { ContentListParams } from "@/types";

interface ContentListProps {
  filters?: ContentListParams;
  refreshKey?: number;
}

function SkeletonCard() {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900 p-4 animate-pulse">
      <div className="h-4 bg-gray-700 rounded w-2/3 mb-2" />
      <div className="h-3 bg-gray-800 rounded w-1/3 mb-3" />
      <div className="h-3 bg-gray-800 rounded w-full mb-1" />
      <div className="h-3 bg-gray-800 rounded w-5/6" />
    </div>
  );
}

export function ContentList({ filters, refreshKey }: ContentListProps) {
  const { items, meta, loading, error, refetch } = useContentList(filters);

  useEffect(() => {
    if (refreshKey !== undefined) refetch();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey]);

  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((n) => <SkeletonCard key={n} />)}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-800 bg-red-900/10 p-4 text-sm text-red-400">
        Failed to load content: {error}
      </div>
    );
  }

  if (!items.length) {
    return (
      <div className="rounded-xl border border-dashed border-gray-700 p-8 text-center text-gray-500 text-sm">
        No content yet. Save a link, note, or YouTube URL above.
      </div>
    );
  }

  return (
    <div>
      {meta && (
        <p className="text-xs text-gray-500 mb-3">
          {meta.total} item{meta.total !== 1 ? "s" : ""}
        </p>
      )}
      <div className="space-y-3">
        {items.map((item) => (
          <ContentCard key={item.id} item={item} onRefresh={refetch} />
        ))}
      </div>
    </div>
  );
}
