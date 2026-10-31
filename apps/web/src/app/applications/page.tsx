import Link from "next/link";
import { ErrorBanner } from "@/components/Feedback";
import { appViews, viewCount } from "@/lib/applications";
import { backendGet } from "@/lib/session";
import type { ApplicationList, Presets } from "@/lib/types";
import ApplicationsView, { AddApplication } from "./ApplicationsView";

type Params = { view?: string; q?: string; sort?: string };

function href(params: Params): string {
  const query = new URLSearchParams(Object.entries(params).filter(([, v]) => v) as [string, string][]).toString();
  return query ? `/applications?${query}` : "/applications";
}

export default async function ApplicationsPage({ searchParams }: { searchParams: Promise<Params> }) {
  const params = await searchParams;
  const presets = await backendGet<Presets>("/presets");
  if (!presets) return <ErrorBanner message="The API isn't answering. Check that it's running (see the README), then reload." />;
  const views = appViews(presets.application_statuses);
  const current = views.find((v) => v.key === params.view) ?? views[0];
  const q = (params.q ?? "").slice(0, 100);
  const sort = params.sort === "next_step" ? "next_step" : undefined;
  const list = await backendGet<ApplicationList>(`/applications?${new URLSearchParams({ view: current.key, q, sort: sort ?? "updated" })}`);
  if (!list) return <ErrorBanner message="The API isn't answering. Check that it's running (see the README), then reload." />;
  const keep = { q, sort };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Applications</h1>
          <p className="mt-2 text-[15px] text-ink-secondary">
            Every job you&apos;ve applied for, or mean to, and where each one stands.{" "}
            <a href="/api/backend/applications/export.csv" className="underline underline-offset-2">
              Export as CSV
            </a>
          </p>
        </div>
        <AddApplication statuses={presets.application_statuses} />
      </div>

      <div className="flex flex-col gap-3 border-b border-hairline sm:flex-row sm:items-end sm:justify-between">
        <nav aria-label="Application views" className="-mb-px flex gap-1 overflow-x-auto">
          {views.map((v) => {
            const on = v.key === current.key;
            return (
              <Link
                key={v.key}
                href={href({ ...keep, view: v.key === "active" ? undefined : v.key })}
                aria-current={on ? "page" : undefined}
                className={`shrink-0 border-b-2 px-3 pb-2.5 text-sm transition-colors ${
                  on ? "border-foreground font-medium text-ink" : "border-transparent text-ink-secondary hover:text-ink"
                }`}
              >
                {v.label} <span className="tabular-nums text-ink-muted">{viewCount(v.key, list.counts)}</span>
              </Link>
            );
          })}
        </nav>
        <div className="flex flex-wrap items-center gap-3 pb-2.5">
          <nav aria-label="Sort" className="flex rounded-lg border border-edge p-0.5 text-sm">
            {[
              { key: undefined, label: "Recent" },
              { key: "next_step", label: "Next step" },
            ].map((option) => (
              <Link
                key={option.label}
                href={href({ view: current.key === "active" ? undefined : current.key, q, sort: option.key })}
                aria-current={sort === option.key ? "true" : undefined}
                className={`rounded-md px-2.5 py-1 ${sort === option.key ? "bg-ink/[0.08] font-medium text-ink" : "text-ink-secondary hover:text-ink"}`}
              >
                {option.label}
              </Link>
            ))}
          </nav>
          <form action="/applications" className="w-full sm:w-auto">
            {current.key !== "active" && <input type="hidden" name="view" value={current.key} />}
            {sort && <input type="hidden" name="sort" value={sort} />}
            <label htmlFor="application-filter" className="sr-only">
              Filter by title, company or notes
            </label>
            <input
              id="application-filter"
              name="q"
              defaultValue={q}
              placeholder="Filter by title, company or notes"
              className="h-9 w-full rounded-lg border border-edge bg-surface px-3 text-sm placeholder:text-ink-muted sm:w-64"
            />
          </form>
        </div>
      </div>

      <ApplicationsView key={`${current.key}|${q}|${sort}|${list.items.map((a) => a.id + a.updated_at).join()}`} initial={list.items} statuses={presets.application_statuses} view={current.key} empty={current.empty} />
    </div>
  );
}
