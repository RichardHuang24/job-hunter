import { backendPublic } from "@/lib/backend";
import RoleStart from "./RoleStart";

type Demo = { account_hours: number; people: {key: string; name: string; headline: string}[] };

export default async function Welcome({ error, deleted }: { error?: string; deleted?: string }) {
  const demo = await backendPublic<Demo>("/demo");
  const message = error === "InvalidRole" ? "Enter a job title between 2 and 80 characters."
    : error === "DemoBusy" ? "The demo is busy. Please try again in a few minutes."
    : error ? "We couldn't open your workspace. Please try again." : null;
  return (
    <div className="flex flex-col gap-12 py-4 sm:py-10">
      <section className="grid items-center gap-10 lg:grid-cols-[1.2fr_1fr]">
        <div>
          <p className="mb-5 text-xs font-semibold uppercase tracking-[0.2em] text-ink-muted">Job Hunter / Interactive project</p>
          <h1 className="text-4xl leading-[1.08] font-semibold tracking-tight sm:text-6xl">Your next role.<br /><span className="text-ink-secondary">Your own workspace.</span></h1>
          <p className="mt-6 max-w-lg text-lg leading-relaxed text-ink-secondary">Find, compare and track opportunities. Start with a job title, then build a CV that tells your story.</p>
          <p className="mt-5 text-sm text-ink-secondary">No sign-up · Any target role · A blank CV to make your own</p>
        </div>
        <div className="rounded-2xl border border-edge bg-surface p-6 shadow-sm sm:p-8">
          {deleted && <p role="status" className="mb-4 text-sm">Your workspace and its data have been deleted.</p>}
          {message && <p role="alert" className="mb-4 rounded-lg border border-red-500/30 p-3 text-sm text-red-700 dark:text-red-300">{message}</p>}
          {demo ? <RoleStart /> : <p role="status">The workspace service is temporarily unavailable. Please try again shortly.</p>}
          <p className="mt-5 border-t border-hairline pt-4 text-xs leading-relaxed text-ink-secondary">A separate space for each visitor. Your CV starts empty; no profile or work history is invented. This demo workspace and its data expire after {demo?.account_hours ?? 24} hours. Export anything you want to keep.</p>
        </div>
      </section>
      <section aria-label="How to try Job Hunter" className="grid gap-4 sm:grid-cols-3">
        {[
          ["01", "Choose your direction", "Start with your target role. Refine your location, skills and preferences in Settings."],
          ["02", "Explore and keep track", "Inspect match reasons, save opportunities and move applications through your own pipeline."],
          ["03", "Make your CV yours", "Add your details, experience and education, then generate a downloadable PDF."],
        ].map(([number, heading, text]) => <article key={number} className="rounded-xl border border-edge p-5"><p className="mb-4 font-mono text-xs text-ink-muted">{number}</p><h2 className="font-semibold">{heading}</h2><p className="mt-2 text-sm leading-relaxed text-ink-secondary">{text}</p></article>)}
      </section>
      <div className="flex flex-col gap-4 border-t border-hairline pt-6 text-sm text-ink-secondary">
        <p><strong className="font-medium text-ink">What you are trying:</strong> this public demo uses fictional sample jobs and simulated fit scores. Any role is accepted; the sample dataset may not include a match. No real application is submitted.</p>
        {demo && <details><summary className="cursor-pointer font-medium text-ink">Prefer a ready-made walkthrough?</summary><p className="my-3 text-xs">These optional fictional profiles include sample CVs and applications.</p><div className="flex flex-wrap gap-2">{demo.people.map((person) => <form key={person.key} method="post" action="/demo/start"><input type="hidden" name="person" value={person.key} /><button type="submit" className="rounded-lg border border-edge px-4 py-2 hover:bg-ink/[0.04]">Try as {person.name.split(" ")[0]}</button></form>)}</div></details>}
      </div>
    </div>
  );
}
