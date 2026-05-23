"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import type { Tag } from "@/types";

export function useTags() {
  const [tags, setTags] = useState<Tag[]>([]);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    setLoading(true);
    const res = await api.tags.list();
    if (!res.error) setTags(Array.isArray(res.data) ? res.data : []);
    setLoading(false);
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  return { tags, loading, refetch: fetch };
}
