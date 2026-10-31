"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import FitBadge from "@/components/FitBadge";
import Link from "next/link";
import { api, ApiError } from "@/lib/api";
import { STATUS_LABELS } from "@/lib/applications";
import { ARRANGEMENTS, daysAgo, salaryRange } from "@/lib/jobs";
import type { Check, Evidence, Score, UserJob } from "@/lib/types";

const CHECK_LABELS: Record<string, string> = {
  role: "Role",
  level: "Level",
  arrangement: "Arrangement",
  location: "Location",
  permit: "Work permit",
  salary: "Salary",
};

const STATUS: Record<Check["status"], { mark: string; label: string; className: string }> = {
  pass: { mark: "✓", label: "Passes", className: "bg-green-700 text-white" },
  flag: { mark: "!", label: "Worth checking", className: "bg-amber-500 text-black" },
  fail: { mark: "✕", label: "Fails", className: "bg-red-600 text-white" },
  unknown: { mark: "?", label: "Not stated", className: "bg-ink/10 text-ink-secondary" },
};

const POLL_MS = 3000;

function Heading({ children }: { children: React.ReactNode }) {
  return <h3 className="text-xs font-medium tracking-wide text-ink-muted uppercase">{children}</h3>;
}

function Checks({ checks }: { checks: Check[] }) {
  return (
    <ul className="flex flex-col gap-1.5">
      {checks.map((check) => {
        const status = STATUS[check.status];
        return (
          <li key={check.key} className="flex items-start gap-2.5 text-sm">
            <span aria-hidden className={`mt-0.5 grid size-4.5 shrink-0 place-items-center rounded-full text-[10px] font-bold ${status.className}`}>
              {status.mark}
            </span>
            <span>
              <span className="sr-only">{status.label}: </span>
              <span className="text-ink-muted">{CHECK_LABELS[check.key] ?? check.key}</span> {check.detail}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function Quotes({ items, empty }: { items: Evidence[]; empty: string }) {
  if (!items.length) return <p className="text-sm text-ink-muted">{empty}</p>;
  return (
    <ul className="flex flex-col gap-1.5 text-sm">
      {items.map((item, index) => (
        <li key={index}>
          <q className={item.verified ? "text-ink" : "text-ink-muted line-through decoration-ink-muted/50"}>{item.requirement}</q>
          {item.kind === "required" && <span className="ml-1.5 text-xs text-ink-muted">required</span>}
          <span className="text-ink-secondary"> - {item.detail || item.note}</span>
          {!item.verified && <span className="ml-1.5 text-xs text-ink-muted">(not found in the posting)</span>}
        </li>
      ))}
    </ul>
  );
}

function Fit({ score, onScore, busy }: { score: Score | null; onScore: () => void; busy: boolean }) {
  const button = (label: string) => (
    <button type="button" onClick={onScore} disabled={busy} className="h-8 shrink-0 rounded-lg border border-edge px-3 text-sm hover:bg-ink/[0.04] disabled:opacity-50">
      {label}
    </button>
  );
  if (!score)
    return (
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-ink-secondary">Not scored yet.</p>
        {button("Score this job")}
      </div>
    );
  if (score.status === "queued")
    return (
      <p className="flex items-center gap-2 text-sm text-ink-secondary">
        <span aria-hidden className="size-3.5 animate-spin rounded-full border-2 border-ink/20 border-t-ink/70" />
        Scoring in the background...
      </p>
    );
  if (score.status === "failed")
    return (
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-red-700 dark:text-red-400">Couldn’t score this job: {score.error}</p>
        {score.error_code !== "limit" && button("Try again")}
      </div>
    );
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <FitBadge score={score} />
          <div>
            <p className="text-[15px] font-medium">{score.band}</p>
            <p className="text-sm text-ink-secondary">{score.advice}</p>
          </div>
        </div>
        {button("Score again")}
      </div>
      {(score.simulated || score.stale) && (
        <p className="rounded-lg border border-dashed border-edge px-3 py-2 text-xs text-ink-secondary">
          {score.simulated && "Simulated score: it only counts your skills and reads the checks. Add an Anthropic API key for Claude’s assessment. "}
          {score.stale && "Out of date: your profile, roles or the posting changed since it was scored."}
        </p>
      )}
      {score.summary && <p className="text-sm">{score.summary}</p>}
      <ul className="flex flex-col gap-2.5">
        {score.dimensions.map((d) => (
          <li key={d.key} className="text-sm">
            <div className="flex items-baseline justify-between gap-3">
              <span className="font-medium">
                {d.label} <span className="text-xs font-normal text-ink-muted">counts {d.weight}%</span>
              </span>
              <span className="tabular-nums">{d.score}</span>
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-hairline" aria-hidden>
              <div className="h-full rounded-full bg-foreground/80" style={{ width: `${d.score}%` }} />
            </div>
            <p className="mt-1 text-ink-secondary">{d.reason}</p>
          </li>
        ))}
      </ul>
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <Heading>What you have</Heading>
          <div className="mt-2">
            <Quotes items={score.matched} empty="Nothing matched clearly." />
          </div>
        </div>
        <div>
          <Heading>Gaps</Heading>
          <div className="mt-2">
            <Quotes items={score.missing} empty="No clear gaps." />
          </div>
        </div>
      </div>
      {(score.risks.length > 0 || score.unclear.length > 0) && (
        <div className="grid gap-4 sm:grid-cols-2">
          {score.risks.length > 0 && (
            <div>
              <Heading>Risks</Heading>
              <ul className="mt-2 list-disc pl-4 text-sm text-ink-secondary">
                {score.risks.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            </div>
          )}
          {score.unclear.length > 0 && (
            <div>
              <Heading>Not stated</Heading>
              <ul className="mt-2 list-disc pl-4 text-sm text-ink-secondary">
                {score.unclear.map((u) => (
                  <li key={u}>{u}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
      {!score.simulated && (
        <p className="text-xs text-ink-muted">
          Scored by {score.model} · ${score.cost_usd.toFixed(4)}
        </p>
      )}
    </div>
  );
}

function Track({ item }: { item: UserJob }) {
  const router = useRouter();
  const [tracked, setTracked] = useState(item.application);
  const [error, setError] = useState<string | null>(null);

  async function track(status: string) {
    setError(null);
    try {
      const made = await api<{ id: string; status: string }>("/applications", { method: "POST", body: JSON.stringify({ user_job_id: item.id, status }) });
      setTracked({ id: made.id, status: made.status });
      router.refresh();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Couldn't track it.");
    }
  }

  if (tracked) {
    return (
      <p className="text-sm text-ink-secondary">
        Tracked as <span className="font-medium text-ink">{STATUS_LABELS[tracked.status] ?? tracked.status}</span> ·{" "}
        <Link href="/applications?view=all" className="underline underline-offset-2">
          Open in Applications
        </Link>
      </p>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-2">
      <button type="button" onClick={() => track("applied")} className="h-9 rounded-lg bg-foreground px-3.5 text-sm font-medium text-background hover:opacity-90">
        I&apos;ve applied
      </button>
      <button type="button" onClick={() => track("planned")} className="h-9 rounded-lg border border-edge px-3.5 text-sm hover:bg-ink/[0.04]">
        Plan to apply
      </button>
      {error && <p className="text-sm text-red-700 dark:text-red-400">{error}</p>}
    </div>
  );
}

function Detail({ item, onScore, busy }: { item: UserJob; onScore: () => void; busy: boolean }) {
  const [full, setFull] = useState<UserJob | null>(null);
  const [failed, setFailed] = useState(false);
  const version = `${item.score?.status}|${item.score?.overall}|${item.score?.stale}`;
  useEffect(() => {
    let current = true;
    api<UserJob>(`/jobs/${item.id}`).then(
      (loaded) => current && setFull(loaded),
      () => current && setFailed(true),
    );
    return () => {
      current = false;
    };
  }, [item.id, version]);
  const score = (full?.score as Score | null | undefined) ?? null;
  if (item.job.closed) {
    return (
      <div className="flex flex-col gap-3 border-t border-hairline px-4 py-4 text-sm text-ink-secondary sm:px-5">
        <p>This job has closed, so its posting is no longer shown. Hide it to tidy up, or keep it saved as a reminder.</p>
        {item.application && <Track item={item} />}
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-5 border-t border-hairline px-4 py-4 sm:px-5">
      <section>
        <Heading>Application</Heading>
        <div className="mt-2">
          <Track item={item} />
        </div>
      </section>
      <section>
        <Heading>Fit</Heading>
        <div className="mt-2">{full ? <Fit score={item.score?.status === "queued" ? { ...(score as Score), status: "queued" } : score} onScore={onScore} busy={busy} /> : <p className="text-sm text-ink-muted">Loading...</p>}</div>
      </section>
      <div className="grid gap-5 sm:grid-cols-[2fr_3fr]">
        <section>
          <Heading>Against your profile</Heading>
          <div className="mt-2">
            <Checks checks={item.checks} />
          </div>
        </section>
        <section className="min-w-0">
          <Heading>The posting</Heading>
          <p className="mt-2 text-sm whitespace-pre-line text-ink-secondary">
            {failed ? "Couldn't load the description." : (full?.job.description ?? "Loading...")}
          </p>
          <a href={item.job.url} target="_blank" rel="noopener noreferrer" className="mt-3 inline-block text-sm font-medium underline underline-offset-2">
            {item.job.demo ? "Open the sample posting" : `Open on ${item.job.source_label}`} ↗
          </a>
        </section>
      </div>
    </div>
  );
}

export default function JobList({ initial, view }: { initial: UserJob[]; view: string }) {
  const router = useRouter();
  const [states, setStates] = useState<Record<string, UserJob["state"]>>({});
  const [removed, setRemoved] = useState<Set<string>>(() => new Set());
  const [open, setOpen] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const items = initial.filter((i) => !removed.has(i.id)).map((i) => (states[i.id] ? { ...i, state: states[i.id] } : i));
  const scoring = items.some((i) => i.score?.status === "queued");

  // Scores are made in the background: refresh until they're all in.
  useEffect(() => {
    if (!scoring) return;
    const timer = setInterval(() => router.refresh(), POLL_MS);
    return () => clearInterval(timer);
  }, [scoring, router]);

  async function move(item: UserJob, state: UserJob["state"]) {
    setError(null);
    try {
      await api<UserJob>(`/jobs/${item.id}`, { method: "PATCH", body: JSON.stringify({ state }) });
      const stays = view === "saved" ? state === "saved" : view === "hidden" ? state === "hidden" : state !== "hidden";
      if (stays) setStates((all) => ({ ...all, [item.id]: state }));
      else setRemoved((all) => new Set(all).add(item.id));
      router.refresh();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Couldn't update that job.");
    }
  }

  async function score(item: UserJob) {
    setError(null);
    setBusy(item.id);
    try {
      await api(`/jobs/${item.id}/score`, { method: "POST" });
      router.refresh();
    } catch (failure) {
      if (!(failure instanceof ApiError && failure.status === 409)) setError(failure instanceof Error ? failure.message : "Couldn't score that job.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      {error && <p className="text-sm text-red-700 dark:text-red-400">{error}</p>}
      <ul className="flex flex-col gap-2">
        {items.map((item) => {
          const { job } = item;
          const expanded = open === item.id;
          const salary = salaryRange(job.salary_min, job.salary_max, job.salary_currency, job.salary_period);
          const arrangement = job.location.toLowerCase().startsWith(job.arrangement) ? "" : ARRANGEMENTS[job.arrangement]; // not "Remote (UK) · Remote"
          const meta = [job.company, job.location, arrangement].filter(Boolean).join(" · ");
          const problem = item.checks.find((c) => c.status === "fail") ?? item.checks.find((c) => c.status === "flag");
          return (
            <li key={item.id} className="rounded-xl border border-edge bg-surface">
              <div className="flex flex-col gap-3 px-4 py-3.5 sm:flex-row sm:items-start sm:gap-4 sm:px-5">
                <button type="button" onClick={() => setOpen(expanded ? null : item.id)} aria-expanded={expanded} className="flex min-w-0 flex-1 items-start gap-3.5 text-left">
                  <FitBadge score={item.score} />
                  <span className="min-w-0">
                    <span className="flex flex-wrap items-baseline gap-x-2">
                      <span className="text-[15px] font-medium">{job.title}</span>
                      {salary && <span className="text-sm text-ink-secondary">{salary}</span>}
                    </span>
                    <span className="mt-0.5 block text-sm text-ink-secondary">{meta}</span>
                    <span className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
                      {item.role && <span className="rounded-md bg-ink/[0.07] px-1.5 py-0.5">{item.role}</span>}
                      <span className="rounded-md bg-ink/[0.07] px-1.5 py-0.5">{item.level.label}</span>
                      {item.score?.status === "done" && <span className="text-ink-secondary">{item.score.band}</span>}
                      {job.demo && <span className="rounded-md border border-dashed border-edge px-1.5 py-0.5 text-ink-muted">Sample</span>}
                      {job.closed && <span className="rounded-md border border-edge px-1.5 py-0.5 text-ink-secondary">Closed</span>}
                      {item.state === "saved" && view !== "saved" && <span className="rounded-md bg-foreground px-1.5 py-0.5 text-background">Saved</span>}
                      {item.application && (
                        <span className="rounded-md border border-foreground/40 px-1.5 py-0.5 font-medium">{STATUS_LABELS[item.application.status] ?? item.application.status}</span>
                      )}
                      {problem && (
                        <span className={problem.status === "fail" ? "text-red-700 dark:text-red-400" : "text-amber-700 dark:text-amber-400"}>{problem.detail}</span>
                      )}
                      <span className="text-ink-muted" suppressHydrationWarning>
                        {job.posted_at ? `Posted ${daysAgo(job.posted_at)}` : ""}
                      </span>
                    </span>
                  </span>
                </button>
                {!job.demo && job.source_url && (
                  <a href={job.source_url} target="_blank" rel="noopener noreferrer" className="self-start text-xs text-ink-muted underline-offset-2 hover:underline sm:order-last sm:pt-2">
                    via {job.source_label}
                  </a>
                )}
                <div className="flex shrink-0 gap-1.5 sm:pl-0">
                  {item.state === "hidden" ? (
                    <button type="button" onClick={() => move(item, "new")} className="h-8 rounded-lg border border-edge px-3 text-sm hover:bg-ink/[0.04]">
                      Put back
                    </button>
                  ) : (
                    <>
                      <button
                        type="button"
                        onClick={() => move(item, item.state === "saved" ? "new" : "saved")}
                        aria-pressed={item.state === "saved"}
                        className="h-8 rounded-lg border border-edge px-3 text-sm hover:bg-ink/[0.04]"
                      >
                        {item.state === "saved" ? "Unsave" : "Save"}
                      </button>
                      <button type="button" onClick={() => move(item, "hidden")} className="h-8 rounded-lg px-3 text-sm text-ink-secondary hover:bg-ink/[0.04] hover:text-ink">
                        Hide
                      </button>
                    </>
                  )}
                </div>
              </div>
              {expanded && <Detail item={item} onScore={() => score(item)} busy={busy === item.id} />}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
