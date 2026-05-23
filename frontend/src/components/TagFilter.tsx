"use client";

import { useTags } from "@/hooks/useTags";

interface TagFilterProps {
  selectedSlug?: string;
  onSelect: (slug: string | undefined) => void;
}

export function TagFilter({ selectedSlug, onSelect }: TagFilterProps) {
  const { tags, loading } = useTags();

  if (loading || !tags.length) return null;

  return (
    <div>
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
        Tags
      </h3>
      <div className="flex flex-wrap gap-1.5">
        {selectedSlug && (
          <button
            onClick={() => onSelect(undefined)}
            className="rounded-full bg-gray-700 text-gray-300 text-xs px-2 py-0.5 hover:bg-gray-600"
          >
            Clear
          </button>
        )}
        {tags.map((tag) => (
          <button
            key={tag.id}
            onClick={() => onSelect(selectedSlug === tag.slug ? undefined : tag.slug)}
            className={`rounded-full text-xs px-2 py-0.5 transition-colors ${
              selectedSlug === tag.slug
                ? "bg-blue-600 text-white"
                : "bg-gray-800 text-gray-400 hover:bg-gray-700"
            }`}
          >
            #{tag.name}
            {tag.item_count !== undefined && (
              <span className="ml-1 text-gray-500">{tag.item_count}</span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
