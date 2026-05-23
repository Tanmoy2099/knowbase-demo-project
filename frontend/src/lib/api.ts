import type {
  ApiResponse,
  Collection,
  ContentItem,
  ContentItemDetail,
  ContentListParams,
  CreateContentRequest,
  Tag,
  UpdateContentRequest,
} from "@/types";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:5000";

async function apiFetch<T>(
  path: string,
  options?: RequestInit
): Promise<ApiResponse<T>> {
  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });

    if (res.status === 204) {
      return { data: null, error: null };
    }

    const json = await res.json();

    if (!res.ok) {
      return {
        data: null,
        error: json.error ?? {
          code: String(res.status),
          message: res.statusText,
        },
      };
    }

    return {
      data: json.data ?? json,
      meta: json.meta,
      error: null,
    };
  } catch (err) {
    return {
      data: null,
      error: {
        code: "NETWORK_ERROR",
        message: err instanceof Error ? err.message : "Network error",
      },
    };
  }
}

function buildQueryString(params?: Record<string, unknown>): string {
  if (!params) return "";
  const entries = Object.entries(params).filter(
    ([, v]) => v !== undefined && v !== null && v !== ""
  );
  if (!entries.length) return "";
  return "?" + new URLSearchParams(entries.map(([k, v]) => [k, String(v)])).toString();
}

export const api = {
  content: {
    create: (body: CreateContentRequest) =>
      apiFetch<ContentItem>("/api/content", {
        method: "POST",
        body: JSON.stringify(body),
      }),

    list: (params?: ContentListParams) =>
      apiFetch<ContentItem[]>(`/api/content${buildQueryString(params as Record<string, unknown>)}`),

    get: (id: string) =>
      apiFetch<ContentItemDetail>(`/api/content/${id}`),

    update: (id: string, body: UpdateContentRequest) =>
      apiFetch<ContentItem>(`/api/content/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),

    delete: (id: string) =>
      apiFetch<void>(`/api/content/${id}`, { method: "DELETE" }),

    uploadPdf: async (file: File, title?: string): Promise<ApiResponse<ContentItem>> => {
      const form = new FormData();
      form.append("file", file);
      if (title) form.append("title", title);
      try {
        const res = await fetch(`${BASE_URL}/api/content/upload`, {
          method: "POST",
          body: form,
          // Do NOT set Content-Type — browser sets multipart boundary automatically
        });
        if (!res.ok) {
          const json = await res.json().catch(() => ({}));
          return { data: null, error: json.error ?? { code: String(res.status), message: res.statusText } };
        }
        const json = await res.json();
        return { data: json.data, error: null };
      } catch (err) {
        return { data: null, error: { code: "NETWORK_ERROR", message: err instanceof Error ? err.message : "Network error" } };
      }
    },
  },

  collections: {
    list: () => apiFetch<Collection[]>("/api/collections"),
    create: (body: { name: string; description?: string }) =>
      apiFetch<Collection>("/api/collections", {
        method: "POST",
        body: JSON.stringify(body),
      }),
  },

  tags: {
    list: () => apiFetch<Tag[]>("/api/tags"),
  },

  admin: {
    health: () =>
      apiFetch<{ status: string; services: { db: boolean; n8n: boolean } }>(
        "/api/admin/health"
      ),
  },
} as const;
