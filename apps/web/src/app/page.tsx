import Link from "next/link";
import Card from "@/components/Card";
import { ErrorBanner } from "@/components/Feedback";
import { backendGet } from "@/lib/session";
import type { Me, Presets } from "@/lib/types";

// What the app will do, in the order it arrives (docs/roadmap.md).
const COMING = [
  { title: "Job search", body: "Searches the job boards for your industry and market, every day." },
  { title: "Ranking", body: "Scores each posting against your profile and explains the fit." },
  { title: "Applications", body: "Tracks where every application stands." },
  { title: "CV workbench", body: "Keeps your CV content in one place and builds a tailored PDF per job." },
];

function label(options: { key: string; label: string }[] | undefined, key: string): string {
  return options?.find((option) => option.key === key)?.label ?? key;
}

export default async function DashboardPage() {
  const [me, presets] = await Promise.all([backendGet<Me>("/me"), backendGet<Presets>("/presets")]);
  if (!me) return <ErrorBanner message="The API isn't answering. Check that it's running (see the README), then reload." />;

  const profile = me.profile;
  const name = profile?.display_name || me.name || me.email?.split("@")[0] || "there";
  const ready = Boolean(profile?.industry && profile?.market);

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Welcome, {name}</h1>
        <p className="mt-2 text-[15px] text-ink-secondary">Job Hunter is in early development - here’s what’s ready and what’s next.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-[2fr_3fr]">
        <Card
          title="Your profile"
          subtitle={ready ? "Searches and scoring will use this." : "Tell Job Hunter what you're looking for."}
          action={
            <Link href="/settings" className="shrink-0 rounded-lg border border-edge px-3 py-1.5 text-sm hover:bg-ink/[0.04]">
              {profile ? "Edit" : "Set up"}
            </Link>
          }
        >
          {profile ? (
            <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
              <dt className="text-ink-muted">Headline</dt>
              <dd>{profile.headline || "-"}</dd>
              <dt className="text-ink-muted">Industry</dt>
              <dd>{profile.industry ? label(presets?.industries, profile.industry) : "-"}</dd>
              <dt className="text-ink-muted">Market</dt>
              <dd>{profile.market ? label(presets?.markets, profile.market) : "-"}</dd>
            </dl>
          ) : (
            <p className="text-sm text-ink-secondary">No profile yet. It takes a minute: a headline, your industry and where you want to work.</p>
          )}
        </Card>

        <Card title="Coming next" subtitle="Each of these joins the menu when it's ready.">
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
  );
}
