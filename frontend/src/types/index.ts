export type ContentType = "link" | "note" | "pdf" | "youtube";
export type ContentStatus = "pending" | "fetching" | "enriched" | "failed";

export interface ContentItem {
  id: string;
  type: ContentType;
  raw_url: string | null;
  title: string | null;
  body: string | null;
  status: ContentStatus;
  created_at: string;
  updated_at: string;
}

export interface Summary {
  id: string;
  text: string;
  ai_provider: string | null;
  model: string | null;
  created_at: string;
}

export interface Tag {
  id: string;
  name: string;
  slug: string;
  item_count?: number;
}

export interface Collection {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  ai_suggested: boolean;
  item_count?: number;
}

export interface ContentItemDetail extends ContentItem {
  summary: Summary | null;
  tags: Tag[];
  collections: Collection[];
}

export interface PaginationMeta {
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

export interface ApiResponse<T> {
  data: T | null;
  meta?: PaginationMeta;
  error: { code: string; message: string; details?: unknown[] } | null;
}

export interface CreateContentRequest {
  type: ContentType;
  raw_url?: string;
  title?: string;
  body?: string;
}

export interface UpdateContentRequest {
  title?: string;
  tag_names?: string[];
  collection_id?: string;
}

export interface ContentListParams {
  tag?: string;
  collection?: string;
  type?: ContentType;
  q?: string;
  status?: ContentStatus;
  page?: number;
  per_page?: number;
}
