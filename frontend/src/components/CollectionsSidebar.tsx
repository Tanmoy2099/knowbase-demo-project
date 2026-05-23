"use client";

import { useCollections } from "@/hooks/useCollections";

interface CollectionsSidebarProps {
  selectedSlug?: string;
  onSelect: (slug: string | undefined) => void;
}

export function CollectionsSidebar({ selectedSlug, onSelect }: CollectionsSidebarProps) {
  const { collections, loading } = useCollections();

  return (
    <nav aria-label="Collections">
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
        Collections
      </h3>

      {loading ? (
        <div className="space-y-1">
          {[1, 2, 3].map((n) => (
            <div key={n} className="h-7 bg-gray-800 rounded animate-pulse" />
          ))}
        </div>
      ) : (
        <ul className="space-y-0.5">
          <li>
            <button
              onClick={() => onSelect(undefined)}
              className={`w-full text-left rounded-lg px-3 py-1.5 text-sm transition-colors ${
                !selectedSlug
                  ? "bg-blue-900/40 text-blue-300"
                  : "text-gray-400 hover:bg-gray-800"
              }`}
            >
              All
            </button>
          </li>
          {collections.map((col) => (
            <li key={col.id}>
              <button
                onClick={() => onSelect(col.slug)}
                className={`w-full text-left rounded-lg px-3 py-1.5 text-sm transition-colors flex items-center justify-between ${
                  selectedSlug === col.slug
                    ? "bg-blue-900/40 text-blue-300"
                    : "text-gray-400 hover:bg-gray-800"
                }`}
              >
                <span className="truncate">{col.name}</span>
                {col.item_count !== undefined && (
                  <span className="text-xs text-gray-600 shrink-0 ml-1">
                    {col.item_count}
                  </span>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </nav>
  );
}
