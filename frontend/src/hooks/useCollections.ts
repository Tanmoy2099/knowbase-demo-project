"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import type { Collection } from "@/types";

export function useCollections() {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    const res = await api.collections.list();
    if (res.error) setError(res.error.message);
    else setCollections(Array.isArray(res.data) ? res.data : []);
    setLoading(false);
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  return { collections, loading, error, refetch: fetch };
}
