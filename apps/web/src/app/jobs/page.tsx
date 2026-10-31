import Link from "next/link";
import { ErrorBanner } from "@/components/Feedback";
import { VIEWS } from "@/lib/jobs";
import { backendGet } from "@/lib/session";
import type { JobCounts, JobList as Jobs, Search } from "@/lib/types";
import JobList from "./JobList";
import RunPanel from "./RunPanel";

type Params = { view?: string; q?: string; limit?: string; sort?: string };

function href(params: Params): string {
  const query = new URLSearchParams(Object.entries(params).filter(([, v]) => v) as [string, string][]).toString();
  return query ? `/jobs?${query}` : "/jobs";
}

export default async function JobsPage({ searchParams }: { searchParams: Promise<Params> }) {
  const params = await searchParams;
  const view = (VIEWS.find((v) => v.key === params.view) ?? VIEWS[0]).key;
  const q = (params.q ?? "").slice(0, 100);
  const limit = Math.min(Math.max(Number(params.limit) || 50, 50), 200);
  const sort = params.sort === "fit" ? "fit" : undefined;
  const query = new URLSearchParams({ view, q, limit: String(limit), sort: sort ?? "recent" });
  const [jobs, searches] = await Promise.all([backendGet<Jobs>(`/jobs?${query}`), backendGet<Search[]>("/searches")]);
  if (!jobs || !searches) return <ErrorBanner message="The API isn't answering. Check that it's running (see the README), then reload." />;
  const current = VIEWS.find((v) => v.key === view)!;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Jobs</h1>
          <p className="mt-2 text-[15px] text-ink-secondary">
            Found by your saved searches and checked against your profile.{" "}
            <Link href="/jobs/searches" className="underline underline-offset-2">
              Manage searches
            </Link>
          </p>
        </div>
        <RunPanel initial={searches} />
      </div>

      <div className="flex flex-col gap-3 border-b border-hairline sm:flex-row sm:items-end sm:justify-between">
        <nav aria-label="Job views" className="-mb-px flex gap-1 overflow-x-auto">
          {VIEWS.map((v) => {
            const on = v.key === view;
            return (
              <Link
                key={v.key}
                href={href({ view: v.key === "matches" ? undefined : v.key, q, sort })}
                aria-current={on ? "page" : undefined}
                className={`shrink-0 border-b-2 px-3 pb-2.5 text-sm transition-colors ${
                  on ? "border-foreground font-medium text-ink" : "border-transparent text-ink-secondary hover:text-ink"
                }`}
              >
                {v.label} <span className="tabular-nums text-ink-muted">{jobs.counts[v.key as keyof JobCounts]}</span>
              </Link>
            );
          })}
        </nav>
        <div className="flex flex-wrap items-center gap-3 pb-2.5">
        <nav aria-label="Sort" className="flex rounded-lg border border-edge p-0.5 text-sm">
          {[
            { key: undefined, label: "Newest" },
            { key: "fit", label: "Best fit" },
          ].map((option) => (
            <Link
              key={option.label}
              href={href({ view: view === "matches" ? undefined : view, q, sort: option.key })}
              aria-current={sort === option.key ? "true" : undefined}
              className={`rounded-md px-2.5 py-1 ${sort === option.key ? "bg-ink/[0.08] font-medium text-ink" : "text-ink-secondary hover:text-ink"}`}
            >
              {option.label}
            </Link>
          ))}
        </nav>
        <form action="/jobs" className="w-full sm:w-auto">
          {view !== "matches" && <input type="hidden" name="view" value={view} />}
          {sort && <input type="hidden" name="sort" value={sort} />}
          <label htmlFor="job-filter" className="sr-only">
            Filter by title, company or place
          </label>
          <input
            id="job-filter"
            name="q"
            defaultValue={q}
            placeholder="Filter by title, company or place"
            className="h-9 w-full rounded-lg border border-edge bg-surface px-3 text-sm sm:w-64"
          />
        </form>
        </div>
      </div>

      {searches.length === 0 ? (
        <div className="rounded-xl border border-dashed border-edge px-6 py-10 text-center">
          <p className="font-medium">No saved searches yet</p>
          <p className="mt-1 text-sm text-ink-secondary">A saved search tells Job Hunter what to look for and where.</p>
          <Link href="/jobs/searches" className="mt-4 inline-block rounded-xl bg-foreground px-4 py-2 text-sm font-medium text-background">
            Set up a search
          </Link>
        </div>
      ) : jobs.items.length === 0 ? (
        <p className="rounded-xl border border-dashed border-edge px-6 py-10 text-center text-sm text-ink-secondary">
          {q ? `Nothing in ${current.label.toLowerCase()} matches “${q}”.` : current.empty}
        </p>
      ) : (
        <>
          <JobList key={`${view}|${q}`} initial={jobs.items} view={view} />
          {jobs.total > jobs.items.length && (
            <Link href={href({ view: view === "matches" ? undefined : view, q, sort, limit: String(limit + 50) })} className="self-center text-sm underline underline-offset-2">
              Show more ({jobs.total - jobs.items.length} left)
            </Link>
          )}
        </>
      )}
    </div>
  );
}
