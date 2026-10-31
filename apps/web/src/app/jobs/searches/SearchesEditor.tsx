"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Card from "@/components/Card";
import { ErrorBanner } from "@/components/Feedback";
import { Checkbox, MultiSelect, PillGroup, TagInput, TextField } from "@/components/Fields";
import { api, ApiError } from "@/lib/api";
import { isActive, runSummary, since } from "@/lib/jobs";
import type { Option, Run, Search, SearchWrite, Source } from "@/lib/types";

const MAX = 5;

function toWrite(search: Search | SearchWrite): SearchWrite {
  const { name, terms, locations, countries, include_remote, sources, daily } = search;
  return { name, terms, locations, countries, include_remote, sources, daily };
}

function chosen(sources: Source[], draft: SearchWrite): Source[] {
  return draft.sources.length ? sources.filter((s) => draft.sources.includes(s.key)) : sources;
}

function onlyRemoteSources(sources: Source[], draft: SearchWrite): boolean {
  const used = chosen(sources, draft);
  return used.length > 0 && used.every((s) => s.remote_only);
}

function listNames(names: string[]): string {
  return names.length < 2 ? (names[0] ?? "") : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

type Props = { search: Search | null; draft: SearchWrite; sources: Source[]; countries: Option[]; locations: string[]; onSaved: (s: Search) => void; onDeleted: () => void };

function SearchCard({ search, draft: start, sources, countries, locations, onSaved, onDeleted }: Props) {
  const router = useRouter();
  const [draft, setDraft] = useState<SearchWrite>(start);
  const [run, setRun] = useState<Run | null>(search?.last_run ?? null);
  const [state, setState] = useState<{ busy: boolean; note: string | null; error: string | null }>({ busy: false, note: null, error: null });
  const set = (change: Partial<SearchWrite>) => setDraft((d) => ({ ...d, ...change }));
  const runId = run && isActive(run) ? run.id : null;

  // Follow a queued or running search until it finishes.
  useEffect(() => {
    if (!runId) return;
    const timer = setInterval(async () => {
      try {
        const fresh = await api<Run>(`/runs/${runId}`);
        setRun(fresh);
        if (!isActive(fresh)) router.refresh();
      } catch {
        // try again on the next tick
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [runId, router]);

  async function save() {
    if (!draft.name.trim() || !draft.terms.length) return setState({ busy: false, note: null, error: "Give the search a name and at least one search term." });
    setState({ busy: true, note: null, error: null });
    try {
      const saved = await api<Search>(search ? `/searches/${search.id}` : "/searches", {
        method: search ? "PUT" : "POST",
        body: JSON.stringify(draft),
      });
      onSaved(saved);
      setState({ busy: false, note: "Saved.", error: null });
      router.refresh();
    } catch (failure) {
      setState({ busy: false, note: null, error: failure instanceof Error ? failure.message : "Couldn't save." });
    }
  }

  async function runNow() {
    if (!search) return;
    setState({ busy: true, note: null, error: null });
    try {
      const started = await api<Run>(`/searches/${search.id}/run`, { method: "POST" });
      setRun(started);
      setState({ busy: false, note: "Started - results appear under Jobs.", error: null });
    } catch (failure) {
      const message = failure instanceof ApiError && failure.status === 409 ? "It's already running." : failure instanceof Error ? failure.message : "Couldn't start it.";
      setState({ busy: false, note: null, error: message });
    }
  }

  async function remove() {
    if (!search) return onDeleted();
    if (!window.confirm(`Delete “${search.name}”? The jobs it found stay.`)) return;
    try {
      await api(`/searches/${search.id}`, { method: "DELETE" });
      onDeleted();
      router.refresh();
    } catch (failure) {
      setState({ busy: false, note: null, error: failure instanceof Error ? failure.message : "Couldn't delete it." });
    }
  }

  const status = run
    ? `${isActive(run) ? runSummary(run) : `Last run ${since(run.finished_at ?? run.created_at)}: ${runSummary(run).toLowerCase()}`}`
    : search
      ? "Not run yet"
      : "New search - save it to run it";
  return (
    <Card title={search ? search.name : "New search"} subtitle={status}>
      <div className="flex flex-col gap-4">
        <TextField label="Name" value={draft.name} onChange={(name) => set({ name })} maxLength={80} />
        <TagInput label="Search for" values={draft.terms} onChange={(terms) => set({ terms })} max={10} placeholder="e.g. staff nurse" hint="Job titles or keywords, as you'd type them into a job board." />
        <TagInput
          label="Where"
          values={draft.locations}
          onChange={(values) => set({ locations: values })}
          suggestions={locations}
          max={10}
          split={false}
          placeholder="A city, region or “Remote”"
          hint="Leave empty to search the whole of the countries below."
        />
        <MultiSelect label="Countries" options={countries} values={draft.countries} onChange={(values) => set({ countries: values })} addLabel="Add a country..." hint="Leave empty for anywhere." />
        {sources.length > 1 && (
          <PillGroup
            label="Sources"
            options={sources.map((s) => ({ key: s.key, label: s.remote_only ? `${s.label} (remote only)` : s.label }))}
            values={draft.sources}
            onChange={(values) => set({ sources: values })}
            hint="Leave them all off to use every source."
          />
        )}
        <Checkbox label="Also look for remote jobs" checked={draft.include_remote} onChange={(include_remote) => set({ include_remote })} />
        {onlyRemoteSources(sources, draft) && !draft.include_remote && !draft.locations.some((l) => l.toLowerCase().startsWith("remote")) && (
          <p className="-mt-2 text-sm text-amber-700 dark:text-amber-400">
            {listNames(chosen(sources, draft).map((s) => s.label))} only list remote jobs, so this search won&apos;t find anything until you tick this or add “Remote” under Where.
          </p>
        )}
        <Checkbox label="Run every day" checked={draft.daily} onChange={(daily) => set({ daily })} hint="New jobs appear under Jobs without you asking." />
        {run && run.errors.length > 0 && (
          <ErrorBanner message={`Last run: ${run.errors.map((e) => `${e.source || "search"} - ${e.message}`).join("; ")}`} />
        )}
        {state.error && <ErrorBanner message={state.error} />}
        <div className="flex flex-wrap items-center gap-2 border-t border-hairline pt-4">
          <button type="button" onClick={save} disabled={state.busy} className="h-10 rounded-xl bg-foreground px-5 text-sm font-medium text-background hover:opacity-90 disabled:opacity-50">
            Save
          </button>
          {search && (
            <button type="button" onClick={runNow} disabled={state.busy || isActive(run)} className="h-10 rounded-xl border border-edge px-4 text-sm hover:bg-ink/[0.04] disabled:opacity-50">
              Run now
            </button>
          )}
          <button type="button" onClick={remove} className="ml-auto h-10 rounded-xl px-3 text-sm text-ink-secondary hover:bg-ink/[0.04] hover:text-ink">
            {search ? "Delete" : "Discard"}
          </button>
          <p role="status" className="w-full text-sm text-ink-secondary sm:w-auto">
            {state.note}
          </p>
        </div>
      </div>
    </Card>
  );
}

export default function SearchesEditor({
  initial,
  suggestion,
  sources,
  countries,
  locations,
}: {
  initial: Search[];
  suggestion: SearchWrite;
  sources: Source[];
  countries: Option[];
  locations: string[];
}) {
  const [searches, setSearches] = useState<Search[]>(initial);
  const [adding, setAdding] = useState(initial.length === 0);
  return (
    <div className="grid items-start gap-6 lg:grid-cols-2">
      {searches.map((search) => (
        <SearchCard
          key={search.id}
          search={search}
          draft={toWrite(search)}
          sources={sources}
          countries={countries}
          locations={locations}
          onSaved={(saved) => setSearches((all) => all.map((s) => (s.id === saved.id ? saved : s)))}
          onDeleted={() => setSearches((all) => all.filter((s) => s.id !== search.id))}
        />
      ))}
      {adding ? (
        <SearchCard
          search={null}
          draft={{ ...suggestion, name: searches.length ? "Another search" : suggestion.name }}
          sources={sources}
          countries={countries}
          locations={locations}
          onSaved={(saved) => {
            setSearches((all) => [...all, saved]);
            setAdding(false);
          }}
          onDeleted={() => setAdding(false)}
        />
      ) : (
        searches.length < MAX && (
          <button
            type="button"
            onClick={() => setAdding(true)}
            className="rounded-xl border border-dashed border-edge px-6 py-10 text-sm text-ink-secondary hover:bg-ink/[0.03] hover:text-ink"
          >
            + New search
          </button>
        )
      )}
    </div>
  );
}
