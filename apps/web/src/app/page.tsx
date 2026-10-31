import Link from "next/link";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";
import AiCard from "@/components/AiCard";
import Card from "@/components/Card";
import FitBadge from "@/components/FitBadge";
import { ErrorBanner } from "@/components/Feedback";
import TitleCheck from "@/components/TitleCheck";
import { isActive, runSummary, salaryRange, since } from "@/lib/jobs";
import { formatSalary, labelOf, listOf } from "@/lib/profile";
import { backendGet } from "@/lib/session";
import type { AiStatus, JobList, Me, Presets, Search } from "@/lib/types";

// What the app will do, in the order it arrives (docs/roadmap.md).
const COMING = [
  { title: "Applications", body: "Tracks where every application stands." },
  { title: "CV workbench", body: "Keeps your CV content in one place and builds a tailored PDF per job." },
];

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-ink-muted">{label}</dt>
      <dd className="min-w-0">{children || <span className="text-ink-muted">Any</span>}</dd>
    </>
  );
}

export default async function DashboardPage() {
  const [me, presets, jobs, searches, ai] = await Promise.all([
    backendGet<Me>("/me"),
    backendGet<Presets>("/presets"),
    backendGet<JobList>("/jobs?view=matches&sort=fit&limit=5"),
    backendGet<Search[]>("/searches"),
    backendGet<AiStatus>("/me/ai"),
  ]);
  if (!me) return <ErrorBanner message="The API isn't answering. Check that it's running (see the README), then reload." />;
  const profile = me.profile;
  if (!profile?.onboarded_at) redirect("/onboarding");

  const latest = (searches ?? [])
    .map((search) => search.last_run)
    .filter((run) => run !== null)
    .sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
  const name = profile.display_name || me.name || me.email?.split("@")[0] || "there";
  const countries = profile.authorized_countries.map((code) => labelOf(presets?.countries, code));
  const salary =
    profile.salary_min !== null ? `${formatSalary(profile.salary_min, profile.salary_currency, profile.salary_period, presets?.salary_periods)} or more` : "";

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Welcome, {name}</h1>
        <p className="mt-2 text-[15px] text-ink-secondary">
          {[profile.headline, labelOf(presets?.industries, profile.industry), labelOf(presets?.markets, profile.market)].filter(Boolean).join(" · ")}
        </p>
      </div>

      <div className="grid items-start gap-4 lg:grid-cols-[3fr_2fr]">
        <div className="flex flex-col gap-4">
          <Card
            title="Best matches"
            subtitle={
              latest
                ? isActive(latest)
                  ? "Your search is running - new jobs will appear here."
                  : `${runSummary(latest)} · searched ${since(latest.finished_at ?? latest.created_at)}`
                : "Set up a search to start finding jobs."
            }
            action={
              <Link href="/jobs" className="shrink-0 rounded-lg border border-edge px-3 py-1.5 text-sm hover:bg-ink/[0.04]">
                All jobs
              </Link>
            }
          >
            {jobs && (
              <p className="mb-3 text-sm text-ink-secondary">
                <strong className="font-semibold text-ink tabular-nums">{jobs.counts.matches}</strong> matches ·{" "}
                <span className="tabular-nums">{jobs.counts.flagged}</span> flagged · <span className="tabular-nums">{jobs.counts.saved}</span> saved
              </p>
            )}
            {jobs && jobs.items.length > 0 ? (
              <ul className="flex flex-col divide-y divide-hairline">
                {jobs.items.map((item) => (
                  <li key={item.id} className="flex items-center gap-3 py-2 first:pt-0 last:pb-0">
                    <FitBadge score={item.score} size="sm" />
                    <span className="min-w-0 flex-1">
                      <span className="text-sm font-medium">{item.job.title}</span>
                      <span className="text-sm text-ink-secondary"> · {[item.job.company, item.job.location].filter(Boolean).join(" · ")}</span>
                    </span>
                    <span className="text-xs text-ink-muted">
                      {salaryRange(item.job.salary_min, item.job.salary_max, item.job.salary_currency, item.job.salary_period)}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-ink-secondary">No matches yet.</p>
            )}
          </Card>
          <Card
            title="What you’re looking for"
            subtitle="Job search will use this to find and filter postings."
            action={
              <Link href="/settings" className="shrink-0 rounded-lg border border-edge px-3 py-1.5 text-sm hover:bg-ink/[0.04]">
                Edit
              </Link>
            }
          >
            <div className="mb-4 flex flex-wrap gap-1.5">
              {me.targets.map((target) => (
                <span key={target.id} className="rounded-md bg-ink/[0.07] px-2 py-0.5 text-sm">
                  {target.label}
                </span>
              ))}
            </div>
            <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
              <Row label="Levels">{listOf(presets?.levels, profile.seniority_levels)}</Row>
              <Row label="Locations">{profile.locations.join(" · ")}</Row>
              <Row label="Arrangements">{listOf(presets?.arrangements, profile.work_arrangements)}</Row>
              <Row label="Work permits">
                {countries.join(", ")}
                {profile.open_to_sponsorship && <span className="text-ink-secondary">{countries.length ? " · " : ""}open to sponsorship</span>}
              </Row>
              <Row label="Salary">{salary}</Row>
              <Row label="Skills">{profile.skills.length ? profile.skills.join(", ") : <span className="text-ink-muted">None yet</span>}</Row>
            </dl>
          </Card>
          <TitleCheck />
        </div>

        <div className="flex flex-col gap-4">
        {ai && <AiCard ai={ai} />}
        <Card title="Coming next" subtitle="Each of these joins the menu when it’s ready.">
          <ol className="flex flex-col divide-y divide-hairline">
            {COMING.map((item, index) => (
              <li key={item.title} className="flex gap-3 py-2.5 first:pt-0 last:pb-0">
                <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full border border-edge text-[11px] text-ink-muted">
                  {index + 1}
                </span>
                <div>
                  <p className="text-sm font-medium">{item.title}</p>
                  <p className="text-sm text-ink-secondary">{item.body}</p>
                </div>
              </li>
            ))}
          </ol>
        </Card>
        </div>
      </div>
    </div>
  );
}
