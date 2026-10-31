"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { isActive, runSummary, since } from "@/lib/jobs";
import type { Run, Search } from "@/lib/types";

const POLL_MS = 2000;

/** Runs every saved search on demand, and follows runs until they finish. */
export default function RunPanel({ initial }: { initial: Search[] }) {
  const router = useRouter();
  const [searches, setSearches] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const [now, setNow] = useState<number | null>(null); // set while polling, for "is the worker running?"
  const runs = searches.map((s) => s.last_run).filter((r): r is Run => r !== null);
  const active = runs.filter(isActive);
  const busy = active.length > 0;

  useEffect(() => {
    if (!busy) return;
    const timer = setInterval(async () => {
      setNow(Date.now());
      try {
        const fresh = await api<Search[]>("/searches");
        setSearches(fresh);
        if (!fresh.some((s) => isActive(s.last_run))) router.refresh();
      } catch {
        // try again on the next tick
      }
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [busy, router]);

  async function runAll() {
    setError(null);
    const started: Run[] = [];
    for (const search of searches) {
      if (isActive(search.last_run)) continue;
      try {
        started.push(await api<Run>(`/searches/${search.id}/run`, { method: "POST" }));
      } catch (failure) {
        if (!(failure instanceof ApiError && failure.status === 409)) setError(failure instanceof Error ? failure.message : "Couldn't start the search.");
      }
    }
    setSearches((current) => current.map((s) => ({ ...s, last_run: started.find((r) => r.search_id === s.id) ?? s.last_run })));
  }

  if (!searches.length) return null;
  const latest = [...runs].sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
  const waiting = now !== null && active.some((r) => r.status === "queued" && now - new Date(r.created_at).getTime() > 30_000);
  const failedSources = latest?.errors.map((e) => e.source).filter(Boolean) ?? [];

  return (
    <div className="flex flex-col items-start gap-1.5 sm:items-end">
      <button
        type="button"
        onClick={runAll}
        disabled={busy}
        className="inline-flex h-10 items-center gap-2 rounded-xl bg-foreground px-4 text-sm font-medium text-background hover:opacity-90 disabled:opacity-60"
      >
        {busy && <span aria-hidden className="size-3.5 animate-spin rounded-full border-2 border-background/40 border-t-background" />}
        {busy ? "Searching..." : "Search now"}
      </button>
      <p role="status" className="text-xs text-ink-muted" suppressHydrationWarning>
        {busy
          ? waiting
            ? "Waiting for the background worker - is it running?"
            : `Checking ${searches.length === 1 ? "your search" : `${active.length} searches`}`
          : latest
            ? `${runSummary(latest)} · ${since(latest.finished_at ?? latest.created_at)}`
            : "Not searched yet"}
        {!busy && failedSources.length > 0 && (
          <>
            {" · "}
            <Link href="/jobs/searches" className="text-red-700 underline underline-offset-2 dark:text-red-400">
              {failedSources.length === 1 ? `${failedSources[0]} failed` : `${failedSources.length} sources failed`}
            </Link>
          </>
        )}
      </p>
      {error && <p className="text-xs text-red-700 dark:text-red-400">{error}</p>}
    </div>
  );
}
