"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { api } from "@/lib/api";
import type {
  ContentItem,
  ContentItemDetail,
  ContentListParams,
  PaginationMeta,
} from "@/types";

export function useContentList(params?: ContentListParams) {
  const [items, setItems] = useState<ContentItem[]>([]);
  const [meta, setMeta] = useState<PaginationMeta | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const paramsKey = JSON.stringify(params ?? {});

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    const res = await api.content.list(params);
    if (res.error) {
      setError(res.error.message);
    } else {
      setItems(Array.isArray(res.data) ? res.data : []);
      setMeta(res.meta ?? null);
    }
    setLoading(false);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramsKey]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { items, meta, loading, error, refetch: fetch };
}

export function useContentItem(id: string | null) {
  const [item, setItem] = useState<ContentItemDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const cancelledRef = useRef(false);

  useEffect(() => {
    if (!id) {
      setItem(null);
      return;
    }

    cancelledRef.current = false;
    setLoading(true);

    const poll = async () => {
      const res = await api.content.get(id);
      if (cancelledRef.current) return;

      if (res.data) {
        setItem(res.data);
        if (res.data.status === "pending" || res.data.status === "fetching") {
          setTimeout(poll, 3000);
        } else {
          setLoading(false);
        }
      } else {
        setLoading(false);
      }
    };

    poll();

    return () => {
      cancelledRef.current = true;
    };
  }, [id]);

  return { item, loading };
}
