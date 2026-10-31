import { ErrorBanner } from "@/components/Feedback";
import { backendGet } from "@/lib/session";
import type { Cv, Presets } from "@/lib/types";
import CvEditor from "./CvEditor";

export default async function CvPage() {
  const [cv, presets] = await Promise.all([backendGet<Cv>("/cv"), backendGet<Presets>("/presets")]);
  if (!cv || !presets) return <ErrorBanner message="The API isn't answering. Check that it's running (see the README), then reload." />;
  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">CV</h1>
        <p className="mt-2 max-w-2xl text-[15px] text-ink-secondary">
          Your CV, kept as plain facts - and a PDF made from it whenever you want one.
        </p>
      </div>
      <CvEditor initial={cv} levels={presets.language_levels} />
    </div>
  );
}
