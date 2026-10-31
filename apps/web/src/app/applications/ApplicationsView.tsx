"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { EmptyState, ErrorBanner } from "@/components/Feedback";
import { INPUT, SelectField, TextArea, TextField } from "@/components/Fields";
import { api } from "@/lib/api";
import { day, due } from "@/lib/applications";
import { since } from "@/lib/jobs";
import type { Application, Option } from "@/lib/types";

const TONES = { late: "text-red-700 dark:text-red-400", soon: "text-amber-700 dark:text-amber-400", later: "text-ink-secondary" };
const BUTTON = "h-9 rounded-lg px-3.5 text-sm font-medium disabled:opacity-50";

type Draft = Pick<Application, "title" | "company" | "location" | "url" | "applied_on" | "next_step" | "next_step_on" | "notes">;

function draftOf(app: Application): Draft {
  const { title, company, location, url, applied_on, next_step, next_step_on, notes } = app;
  return { title, company, location, url, applied_on, next_step, next_step_on, notes };
}

function Details({ app, statuses, onSaved, onDeleted }: { app: Application; statuses: Option[]; onSaved: (app: Application) => void; onDeleted: () => void }) {
  const [draft, setDraft] = useState<Draft>(draftOf(app));
  const [events, setEvents] = useState(app.events ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (change: Partial<Draft>) => setDraft((d) => ({ ...d, ...change }));
  const label = (key: string) => statuses.find((s) => s.key === key)?.label ?? key;

  useEffect(() => {
    if (app.events) return;
    let current = true;
    api<Application>(`/applications/${app.id}`).then(
      (full) => current && setEvents(full.events ?? []),
      () => current && setEvents([]),
    );
    return () => {
      current = false;
    };
  }, [app.id, app.events]);

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const saved = await api<Application>(`/applications/${app.id}`, {
        method: "PATCH",
        body: JSON.stringify({ ...draft, applied_on: draft.applied_on || null, next_step_on: draft.next_step_on || null }),
      });
      setEvents(saved.events ?? []);
      onSaved(saved);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Couldn't save it.");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm(`Delete the application for “${app.title}”? Its history goes too.`)) return;
    try {
      await api(`/applications/${app.id}`, { method: "DELETE" });
      onDeleted();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Couldn't delete it.");
    }
  }

  return (
    <form onSubmit={save} className="grid gap-5 border-t border-hairline px-4 py-4 sm:grid-cols-[3fr_2fr] sm:px-5">
      <div className="flex flex-col gap-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <TextField label="Job title" value={draft.title} onChange={(title) => set({ title })} maxLength={300} />
          <TextField label="Company" value={draft.company} onChange={(company) => set({ company })} maxLength={200} />
          <TextField label="Place" value={draft.location} onChange={(location) => set({ location })} maxLength={200} />
          <TextField label="Applied on" type="date" value={draft.applied_on ?? ""} onChange={(applied_on) => set({ applied_on })} />
        </div>
        <div className="grid gap-3 sm:grid-cols-[2fr_1fr]">
          <TextField label="Next step" value={draft.next_step} onChange={(next_step) => set({ next_step })} placeholder="e.g. Phone interview" maxLength={200} />
          <TextField label="When" type="date" value={draft.next_step_on ?? ""} onChange={(next_step_on) => set({ next_step_on })} />
        </div>
        <TextField label="Link to the posting" type="url" value={draft.url} onChange={(url) => set({ url })} placeholder="https://..." maxLength={2000} />
        <TextArea label="Notes" value={draft.notes} onChange={(notes) => set({ notes })} maxLength={5000} placeholder="Who you spoke to, what they asked, what to follow up" />
        {error && <ErrorBanner message={error} />}
        <div className="flex items-center gap-2">
          <button type="submit" disabled={busy || !draft.title.trim()} className={`${BUTTON} bg-foreground text-background hover:opacity-90`}>
            Save
          </button>
          <button type="button" onClick={remove} className={`${BUTTON} text-ink-secondary hover:bg-ink/[0.05] hover:text-ink`}>
            Delete
          </button>
        </div>
      </div>
      <section>
        <h3 className="text-xs font-medium tracking-wide text-ink-muted uppercase">History</h3>
        {events === null ? (
          <p className="mt-2 text-sm text-ink-muted">Loading...</p>
        ) : (
          <ol className="mt-2 flex flex-col gap-2 border-l border-edge pl-3">
            {events.map((e, i) => (
              <li key={i} className="text-sm">
                <span className="font-medium">{e.kind === "created" ? `Added as ${label(e.status)}` : label(e.status)}</span>
                <span className="block text-xs text-ink-muted" suppressHydrationWarning>
                  {since(e.at)}
                </span>
              </li>
            ))}
          </ol>
        )}
      </section>
    </form>
  );
}

export default function ApplicationsView({ initial, statuses, view, empty }: { initial: Application[]; statuses: Option[]; view: string; empty: string }) {
  const router = useRouter();
  const [items, setItems] = useState(initial);
  const [open, setOpen] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const replace = (app: Application) => setItems((all) => all.map((a) => (a.id === app.id ? app : a)));

  async function move(app: Application, status: string) {
    setError(null);
    try {
      replace(await api<Application>(`/applications/${app.id}`, { method: "PATCH", body: JSON.stringify({ status }) }));
      router.refresh(); // the tab counts
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Couldn't change the status.");
    }
  }

  if (items.length === 0) return <EmptyState title="Nothing here" body={empty} />;
  return (
    <div className="flex flex-col gap-2">
      {error && <ErrorBanner message={error} />}
      <ul className="flex flex-col gap-2">
        {items.map((app) => {
          const expanded = open === app.id;
          const next = app.next_step_on ? due(app.next_step_on) : null;
          const meta = [app.company, app.location].filter(Boolean).join(" · ");
          const moved = view !== "all" && view !== "active" && view !== "closed" && app.status !== view;
          return (
            <li key={app.id} className={`rounded-xl border border-edge bg-surface ${moved ? "opacity-60" : ""}`}>
              <div className="flex flex-col gap-3 px-4 py-3.5 sm:flex-row sm:items-start sm:gap-4 sm:px-5">
                <button type="button" onClick={() => setOpen(expanded ? null : app.id)} aria-expanded={expanded} className="min-w-0 flex-1 text-left">
                  <span className="block text-[15px] font-medium">{app.title}</span>
                  {meta && <span className="mt-0.5 block text-sm text-ink-secondary">{meta}</span>}
                  <span className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                    {app.applied_on && <span className="text-ink-secondary" suppressHydrationWarning>Applied {day(app.applied_on)}</span>}
                    {(app.next_step || next) && (
                      <span className={next ? TONES[next.tone] : "text-ink-secondary"} suppressHydrationWarning>
                        Next: {app.next_step || "a step"}
                        {next && ` · ${next.text}`}
                      </span>
                    )}
                    {app.job_closed && <span className="rounded-md border border-edge px-1.5 py-0.5 text-ink-secondary">Posting closed</span>}
                    {!app.user_job_id && <span className="text-ink-muted">Added by hand</span>}
                  </span>
                </button>
                <div className="flex shrink-0 items-center gap-2">
                  <select
                    aria-label={`Status of ${app.title}`}
                    value={app.status}
                    onChange={(event) => move(app, event.target.value)}
                    className={`${INPUT} h-9 w-auto pr-8 text-sm`}
                  >
                    {statuses.map((s) => (
                      <option key={s.key} value={s.key}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                  {app.url && (
                    <a href={app.url} target="_blank" rel="noopener noreferrer" className="h-9 rounded-lg px-2.5 text-sm leading-9 whitespace-nowrap text-ink-secondary hover:bg-ink/[0.05] hover:text-ink">
                      Posting ↗
                    </a>
                  )}
                </div>
              </div>
              {expanded && (
                <Details
                  key={app.updated_at}
                  app={app}
                  statuses={statuses}
                  onSaved={replace}
                  onDeleted={() => {
                    setItems((all) => all.filter((a) => a.id !== app.id));
                    router.refresh();
                  }}
                />
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function AddApplication({ statuses }: { statuses: Option[] }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState({ title: "", company: "", location: "", url: "", status: "applied" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function add(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api("/applications", { method: "POST", body: JSON.stringify(draft) });
      setDraft({ title: "", company: "", location: "", url: "", status: "applied" });
      setOpen(false);
      router.refresh();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Couldn't add it.");
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className="h-10 rounded-xl bg-foreground px-4 text-sm font-medium text-background hover:opacity-90">
        + Add an application
      </button>
    );
  }
  return (
    <form onSubmit={add} className="flex w-full flex-col gap-3 rounded-xl border border-edge bg-surface p-4 sm:p-5">
      <p className="text-sm text-ink-secondary">For a job you found elsewhere. Jobs found here: open one under Jobs and press “I&apos;ve applied”.</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <TextField label="Job title" value={draft.title} onChange={(title) => setDraft({ ...draft, title })} maxLength={300} />
        <TextField label="Company" value={draft.company} onChange={(company) => setDraft({ ...draft, company })} maxLength={200} />
        <TextField label="Place" value={draft.location} onChange={(location) => setDraft({ ...draft, location })} maxLength={200} />
        <SelectField label="Status" value={draft.status} onChange={(status) => setDraft({ ...draft, status })} options={statuses} />
      </div>
      <TextField label="Link to the posting (optional)" type="url" value={draft.url} onChange={(url) => setDraft({ ...draft, url })} placeholder="https://..." maxLength={2000} />
      {error && <ErrorBanner message={error} />}
      <div className="flex gap-2">
        <button type="submit" disabled={busy || !draft.title.trim()} className={`${BUTTON} bg-foreground text-background hover:opacity-90`}>
          Add
        </button>
        <button type="button" onClick={() => setOpen(false)} className={`${BUTTON} text-ink-secondary hover:bg-ink/[0.05]`}>
          Cancel
        </button>
      </div>
    </form>
  );
}
