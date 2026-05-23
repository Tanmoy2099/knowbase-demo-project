"use client";

import { useState } from "react";
import { ContentSaveForm } from "@/components/ContentSaveForm";
import { ContentList } from "@/components/ContentList";
import { CollectionsSidebar } from "@/components/CollectionsSidebar";
import { TagFilter } from "@/components/TagFilter";
import type { ContentListParams } from "@/types";

export default function HomePage() {
  const [filters, setFilters] = useState<ContentListParams>({});
  const [refreshKey, setRefreshKey] = useState(0);

  function handleSaveSuccess() {
    setRefreshKey((k) => k + 1);
  }

  function handleCollectionSelect(slug: string | undefined) {
    setFilters((f) => ({ ...f, collection: slug, page: 1 }));
  }

  function handleTagSelect(slug: string | undefined) {
    setFilters((f) => ({ ...f, tag: slug, page: 1 }));
  }

  return (
    <div className="flex gap-6">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 space-y-6">
        <CollectionsSidebar
          selectedSlug={filters.collection}
          onSelect={handleCollectionSelect}
        />
        <TagFilter
          selectedSlug={filters.tag}
          onSelect={handleTagSelect}
        />
      </aside>

      {/* Main */}
      <div className="flex-1 min-w-0 space-y-4">
        <ContentSaveForm onSuccess={handleSaveSuccess} />
        <ContentList filters={filters} refreshKey={refreshKey} />
      </div>
    </div>
  );
}
