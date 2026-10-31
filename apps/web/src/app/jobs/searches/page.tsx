import Link from "next/link";
import { ErrorBanner } from "@/components/Feedback";
import { backendGet } from "@/lib/session";
import type { Me, Presets, Search, SearchWrite, Source } from "@/lib/types";
import SearchesEditor from "./SearchesEditor";

export default async function SearchesPage() {
  const [searches, suggestion, sources, presets, me] = await Promise.all([
    backendGet<Search[]>("/searches"),
    backendGet<SearchWrite>("/searches/suggestion"),
    backendGet<Source[]>("/sources"),
    backendGet<Presets>("/presets"),
    backendGet<Me>("/me"),
  ]);
  if (!searches || !suggestion || !sources || !presets || !me)
    return <ErrorBanner message="The API isn't answering. Check that it's running (see the README), then reload." />;
  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="text-sm text-ink-muted">
          <Link href="/jobs" className="hover:text-ink">
            Jobs
          </Link>{" "}
          /
        </p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">Saved searches</h1>
        <p className="mt-2 max-w-2xl text-[15px] text-ink-secondary">
          Each search asks the job sources for every term in every place, then checks what comes back against your profile. Daily searches
          run once a day in the background.
        </p>
      </div>
      {sources.length === 1 && sources[0].demo && (
        <p className="rounded-lg border border-dashed border-edge px-4 py-3 text-sm text-ink-secondary">
          Searches use <strong className="font-medium text-ink">sample jobs</strong> for now: built-in postings with fictional employers, so you
          can try everything. Real job boards are added as their terms are cleared - see the roadmap.
        </p>
      )}
      <SearchesEditor initial={searches} suggestion={suggestion} sources={sources} countries={presets.countries} locations={me.profile?.locations ?? []} />
    </div>
  );
}
