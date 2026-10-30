// A full industry or market preset (GET /presets/industries/{key} or
// /presets/markets/{key}), fetched once per key and kept for the page's life.
"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Industry, Market } from "@/lib/types";

const cache = new Map<string, Promise<unknown>>();

function load<T>(path: string): Promise<T> {
  if (!cache.has(path)) {
    const request = api<T>(path);
    request.catch(() => cache.delete(path)); // a failure is retried next time
    cache.set(path, request);
  }
  return cache.get(path) as Promise<T>;
}

function usePreset<T>(kind: "industries" | "markets", key: string): T | null {
  const [loaded, setLoaded] = useState<{ key: string; value: T } | null>(null);
  useEffect(() => {
    if (!key) return;
    let current = true;
    load<T>(`/presets/${kind}/${key}`).then(
      (value) => current && setLoaded({ key, value }),
      () => undefined,
    );
    return () => {
      current = false;
    };
  }, [kind, key]);
  return key && loaded?.key === key ? loaded.value : null;
}

export const useIndustry = (key: string) => usePreset<Industry>("industries", key);
export const useMarket = (key: string) => usePreset<Market>("markets", key);
