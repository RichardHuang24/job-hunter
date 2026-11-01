import type { Metadata } from "next";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import Card from "@/components/Card";
import { ErrorBanner } from "@/components/Feedback";
import { budgetTone, compact, duration, percent, sourceHealth, usd, type Health } from "@/lib/admin";
import { backendFetch } from "@/lib/backend";
import { since } from "@/lib/jobs";
import { userId } from "@/lib/session";
import type { AdminOverview } from "@/lib/types";

export const metadata: Metadata = { title: "Admin - Job Hunter" };

const TONE: Record<Health["tone"], string> = {
  good: "text-green-700 dark:text-green-400",
  warning: "text-amber-700 dark:text-amber-400",
  critical: "text-red-700 dark:text-red-400",
  none: "text-ink-muted",
};
// Meter fills, each on a lighter step of its own colour (the track).
const METER = {
  accent: { fill: "bg-foreground", track: "bg-ink/[0.10]" },
  warning: { fill: "bg-amber-500", track: "bg-amber-500/20" },
  critical: { fill: "bg-red-600", track: "bg-red-600/20" },
};
const TH = "px-3 py-2 text-left text-xs font-medium text-ink-muted first:pl-0 last:pr-0";
const TD = "px-3 py-2.5 align-top first:pl-0 last:pr-0";
const NUM = `${TD} text-right tabular-nums`;

function Tile({ label, value, children }: { label: string; value: string; children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-edge bg-surface p-4">
      <p className="text-sm text-ink-secondary">{label}</p>
      <p className="mt-1 text-3xl font-semibold tracking-tight">{value}</p>
      {children && <p className="mt-1 text-xs text-ink-muted">{children}</p>}
    </div>
  );
}

function State({ health }: { health: Health }) {
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap ${TONE[health.tone]}`}>
      <span aria-hidden className="grid size-4 place-items-center rounded-full border border-current text-[10px] leading-none">
        {health.icon}
      </span>
      {health.label}
    </span>
  );
}

function Meter({ used }: { used: number | null }) {
  if (used === null) return <span className="text-ink-muted">-</span>;
  const style = METER[budgetTone(used)];
  return (
    <span className="flex items-center justify-end gap-2">
      <span
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(used * 100)}
        aria-label="Budget used this month"
        className={`h-1.5 w-20 overflow-hidden rounded-full ${style.track}`}
      >
        <span className={`block h-full rounded-full ${style.fill}`} style={{ width: `${Math.min(used, 1) * 100}%` }} />
      </span>
      <span className="w-10 text-right tabular-nums">{percent(used)}</span>
    </span>
  );
}

function Table({ head, children }: { head: ReactNode; children: ReactNode }) {
  return (
    <div className="-mx-5 overflow-x-auto px-5">
      <table className="w-full min-w-[36rem] text-sm">
        <thead className="border-b border-hairline">{head}</thead>
        <tbody className="divide-y divide-hairline">{children}</tbody>
      </table>
    </div>
  );
}

export default async function AdminPage() {
  const id = await userId();
  let status = 0;
  let data: AdminOverview | null = null;
  try {
    const response = await backendFetch(id, "/admin/overview");
    status = response.status;
    if (response.ok) data = (await response.json()) as AdminOverview;
  } catch (error) {
    console.error("API GET /admin/overview failed:", error);
  }
  if (status === 403) notFound(); // not an admin: the page doesn't exist for them
  if (!data) return <ErrorBanner message="The API isn't answering. Check that it's running (see the README), then reload." />;
  const { people, ai, sources, queue, cv_pdfs: pdfs } = data;
  const waiting = queue.by_kind.reduce((n, k) => n + k.queued, 0);

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Admin</h1>
        <p className="mt-2 text-[15px] text-ink-secondary" suppressHydrationWarning>
          How this Job Hunter is doing, as of {since(data.generated_at)}. Only the addresses in ADMIN_EMAILS see this page.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile label="People" value={compact(people.total)}>
          {people.set_up} set up · {people.new_7_days} new this week
        </Tile>
        <Tile label="AI spend this month" value={usd(ai.cost_usd)}>
          {compact(ai.scores)} scores by {ai.people_scoring} {ai.people_scoring === 1 ? "person" : "people"}
        </Tile>
        <Tile label="Tasks waiting" value={compact(waiting)}>
          {waiting ? `oldest ${duration(queue.waiting_seconds)}` : "none"}
          {queue.stuck > 0 && <span className={TONE.critical}> · {queue.stuck} stuck</span>}
        </Tile>
        <Tile label="CV PDFs this week" value={compact(pdfs.done_7_days)}>
          {pdfs.failed_7_days ? <span className={TONE.critical}>{pdfs.failed_7_days} failed</span> : "none failed"}
        </Tile>
      </div>

      <Card title="AI costs this month" subtitle={`${ai.month} · each person may use ${ai.scores_per_person} scores and ${usd(ai.budget_per_person_usd)}`}>
        {ai.by_user.length === 0 ? (
          <p className="text-sm text-ink-secondary">No AI scores yet this month.</p>
        ) : (
          <Table
            head={
              <tr>
                <th className={TH}>Person</th>
                <th className={`${TH} text-right`}>Scores</th>
                <th className={`${TH} text-right`}>Tokens in / out</th>
                <th className={`${TH} text-right`}>Cost</th>
                <th className={`${TH} text-right`}>Budget used</th>
              </tr>
            }
          >
            {ai.by_user.map((u) => (
              <tr key={u.user_id}>
                <td className={`${TD} max-w-64 truncate`} title={u.email}>
                  {u.email || `#${u.user_id}`}
                </td>
                <td className={NUM}>{compact(u.scores)}</td>
                <td className={NUM}>
                  {compact(u.input_tokens)} / {compact(u.output_tokens)}
                </td>
                <td className={NUM}>{usd(u.cost_usd)}</td>
                <td className={`${TD} text-right`}>
                  <Meter used={u.budget_used} />
                </td>
              </tr>
            ))}
          </Table>
        )}
        {ai.by_model.length > 0 && (
          <p className="mt-4 text-xs text-ink-muted">By model: {ai.by_model.map((m) => `${m.model} ${compact(m.scores)} scores, ${usd(m.cost_usd)}`).join(" · ")}</p>
        )}
      </Card>

      <Card title="Job sources, last 7 days" subtitle="How often each source failed in the searches that asked it.">
        <Table
          head={
            <tr>
              <th className={TH}>Source</th>
              <th className={TH}>State</th>
              <th className={`${TH} text-right`}>Runs</th>
              <th className={`${TH} text-right`}>Failed</th>
              <th className={`${TH} text-right`}>Jobs found</th>
              <th className={TH}>Last error</th>
              <th className={TH}>Last check for closed jobs</th>
            </tr>
          }
        >
          {sources.map((s) => (
            <tr key={s.key}>
              <td className={TD}>
                {s.label}
                {!s.enabled && <span className="block text-xs text-ink-muted">not in JOB_SOURCES</span>}
              </td>
              <td className={TD}>
                <State health={sourceHealth(s)} />
              </td>
              <td className={NUM}>{compact(s.runs)}</td>
              <td className={NUM}>
                {compact(s.failed)}
                {s.runs > 0 && <span className="block text-xs text-ink-muted">{percent(s.error_rate)}</span>}
              </td>
              <td className={NUM}>{compact(s.postings)}</td>
              <td className={`${TD} max-w-72`}>
                {s.last_error ? (
                  <>
                    <span className="line-clamp-2 font-mono text-xs" title={s.last_error}>
                      {s.last_error}
                    </span>
                    <span className="text-xs text-ink-muted" suppressHydrationWarning>
                      {s.last_error_at ? since(s.last_error_at) : ""}
                    </span>
                  </>
                ) : (
                  <span className="text-ink-muted">None</span>
                )}
              </td>
              <td className={TD}>
                {s.last_recheck ? (
                  Object.entries(s.last_recheck)
                    .map(([k, v]) => `${v} ${k}`)
                    .join(", ")
                ) : (
                  <span className="text-ink-muted">-</span>
                )}
              </td>
            </tr>
          ))}
        </Table>
      </Card>

      <Card title="Task queue" subtitle={`Waiting now, and finished in the last 24 hours.${queue.stuck ? "" : " Nothing stuck."}`}>
        {queue.stuck > 0 && (
          <p className="mb-3 text-sm">
            <State health={{ label: `${queue.stuck} running past their lease - a worker may have died; another will take them over`, icon: "×", tone: "critical" }} />
          </p>
        )}
        {queue.by_kind.length === 0 ? (
          <p className="text-sm text-ink-secondary">No tasks in the last 24 hours.</p>
        ) : (
          <Table
            head={
              <tr>
                <th className={TH}>Kind</th>
                <th className={`${TH} text-right`}>Waiting</th>
                <th className={`${TH} text-right`}>Running</th>
                <th className={`${TH} text-right`}>Done</th>
                <th className={`${TH} text-right`}>Failed</th>
              </tr>
            }
          >
            {queue.by_kind.map((k) => (
              <tr key={k.kind}>
                <td className={`${TD} font-mono text-xs`}>{k.kind}</td>
                <td className={NUM}>{compact(k.queued)}</td>
                <td className={NUM}>{compact(k.running)}</td>
                <td className={NUM}>{compact(k.succeeded_24h)}</td>
                <td className={`${NUM} ${k.failed_24h ? TONE.critical : ""}`}>{compact(k.failed_24h)}</td>
              </tr>
            ))}
          </Table>
        )}
        {queue.recent_failures.length > 0 && (
          <div className="mt-5">
            <h3 className="text-xs font-medium text-ink-muted">Latest failures</h3>
            <ul className="mt-2 flex flex-col divide-y divide-hairline">
              {queue.recent_failures.map((f, i) => (
                <li key={i} className="flex flex-col gap-0.5 py-2 text-sm first:pt-0">
                  <span suppressHydrationWarning>
                    <span className="font-mono text-xs">{f.kind}</span>
                    <span className="text-xs text-ink-muted">
                      {" "}
                      · {f.at ? since(f.at) : ""}
                      {f.user_id ? ` · account #${f.user_id}` : ""}
                    </span>
                  </span>
                  <span className="line-clamp-2 font-mono text-xs text-ink-secondary" title={f.error}>
                    {f.error}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </Card>
    </div>
  );
}
