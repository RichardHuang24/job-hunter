"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ARRANGEMENTS, daysAgo, salaryRange } from "@/lib/jobs";
import type { Check, UserJob } from "@/lib/types";

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

function Detail({ item }: { item: UserJob }) {
  const [description, setDescription] = useState<string | null>(item.job.description ?? null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (item.job.description !== undefined) return;
    let current = true;
    api<UserJob>(`/jobs/${item.id}`).then(
      (full) => current && setDescription(full.job.description ?? ""),
      () => current && setFailed(true),
    );
    return () => {
      current = false;
    };
  }, [item.id, item.job.description]);
  return (
    <div className="grid gap-5 border-t border-hairline px-4 py-4 sm:grid-cols-[2fr_3fr] sm:px-5">
      <div>
        <h3 className="text-xs font-medium tracking-wide text-ink-muted uppercase">Against your profile</h3>
        <div className="mt-2">
          <Checks checks={item.checks} />
        </div>
      </div>
      <div className="min-w-0">
        <h3 className="text-xs font-medium tracking-wide text-ink-muted uppercase">The posting</h3>
        <p className="mt-2 text-sm whitespace-pre-line text-ink-secondary">
          {failed ? "Couldn't load the description." : (description ?? "Loading...")}
        </p>
        <a
          href={item.job.url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-block text-sm font-medium underline underline-offset-2"
        >
          {item.job.demo ? "Open the sample posting" : `Open on ${item.job.source_label}`} ↗
        </a>
      </div>
    </div>
  );
}

export default function JobList({ initial, view }: { initial: UserJob[]; view: string }) {
  const router = useRouter();
  const [items, setItems] = useState(initial);
  const [open, setOpen] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function move(item: UserJob, state: UserJob["state"]) {
    setError(null);
    try {
      const updated = await api<UserJob>(`/jobs/${item.id}`, { method: "PATCH", body: JSON.stringify({ state }) });
      const stays = view === "saved" ? state === "saved" : view === "hidden" ? state === "hidden" : state !== "hidden";
      setItems((current) => (stays ? current.map((i) => (i.id === item.id ? { ...i, state: updated.state } : i)) : current.filter((i) => i.id !== item.id)));
      router.refresh();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Couldn't update that job.");
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
          const meta = [job.company, job.location, ARRANGEMENTS[job.arrangement]].filter(Boolean).join(" · ");
          const problem = item.checks.find((c) => c.status === "fail") ?? item.checks.find((c) => c.status === "flag");
          return (
            <li key={item.id} className="rounded-xl border border-edge bg-surface">
              <div className="flex flex-col gap-3 px-4 py-3.5 sm:flex-row sm:items-start sm:gap-4 sm:px-5">
                <button
                  type="button"
                  onClick={() => setOpen(expanded ? null : item.id)}
                  aria-expanded={expanded}
                  className="min-w-0 flex-1 text-left"
                >
                  <span className="flex flex-wrap items-baseline gap-x-2">
                    <span className="text-[15px] font-medium">{job.title}</span>
                    {salary && <span className="text-sm text-ink-secondary">{salary}</span>}
                  </span>
                  <span className="mt-0.5 block text-sm text-ink-secondary">{meta}</span>
                  <span className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
                    {item.role && <span className="rounded-md bg-ink/[0.07] px-1.5 py-0.5">{item.role}</span>}
                    <span className="rounded-md bg-ink/[0.07] px-1.5 py-0.5">{item.level.label}</span>
                    {job.demo && <span className="rounded-md border border-dashed border-edge px-1.5 py-0.5 text-ink-muted">Sample</span>}
                    {item.state === "saved" && view !== "saved" && <span className="rounded-md bg-foreground px-1.5 py-0.5 text-background">Saved</span>}
                    {problem && (
                      <span className={problem.status === "fail" ? "text-red-700 dark:text-red-400" : "text-amber-700 dark:text-amber-400"}>
                        {problem.detail}
                      </span>
                    )}
                    <span className="text-ink-muted" suppressHydrationWarning>
                      {job.posted_at ? `Posted ${daysAgo(job.posted_at)}` : ""}
                    </span>
                  </span>
                </button>
                <div className="flex shrink-0 gap-1.5">
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
              {expanded && <Detail item={item} />}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
