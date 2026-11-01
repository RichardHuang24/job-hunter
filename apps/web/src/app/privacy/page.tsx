import type { Metadata } from "next";
import type { ReactNode } from "react";
import { backendPublic } from "@/lib/backend";
import type { PrivacyFacts } from "@/lib/types";

export const metadata: Metadata = { title: "Privacy - Job Hunter" };

// The facts come from this deployment's own settings (apps/api/app/privacy.py),
// so the page says what this server really does. The operator fills in who
// they are with PRIVACY_CONTROLLER and PRIVACY_CONTACT (docs/privacy.md).

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
      <div className="flex flex-col gap-2 text-[15px] leading-relaxed text-ink-secondary">{children}</div>
    </section>
  );
}

function mailHost(): string {
  try {
    return new URL(process.env.EMAIL_SERVER ?? "").hostname;
  } catch {
    return "";
  }
}

export default async function PrivacyPage() {
  const facts = await backendPublic<PrivacyFacts>("/privacy");
  const host = mailHost();
  const devMail = !host || ["mailpit", "localhost", "127.0.0.1"].includes(host);
  const contact = facts?.contact ? (
    <a href={`mailto:${facts.contact}`} className="underline underline-offset-2">
      {facts.contact}
    </a>
  ) : (
    "the person who runs this site"
  );

  return (
    <article className="mx-auto flex max-w-2xl flex-col gap-8 pb-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Privacy</h1>
        <p className="mt-2 text-[15px] text-ink-secondary">What this Job Hunter keeps about you, why, who else sees it, and what you can do about it.</p>
      </div>

      {(!facts || !facts.configured) && (
        <p role="note" className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-800 dark:text-amber-300">
          The person running this site hasn&apos;t added who they are and how to reach them yet (PRIVACY_CONTROLLER and PRIVACY_CONTACT).
        </p>
      )}

      <Section title="Who is responsible">
        <p>
          {facts?.controller ? <strong className="font-medium text-ink">{facts.controller}</strong> : "The person or organisation running this site"} decides how your data is
          used here - the &ldquo;controller&rdquo; under UK and EU data protection law. Questions, requests and complaints: {contact}.
        </p>
        <p>Job Hunter is open-source software; whoever runs this copy is responsible for it.</p>
      </Section>

      <Section title="What's kept, and why">
        <ul className="list-disc pl-5">
          <li>Your email address and name - to sign you in by emailed link.</li>
          <li>Your profile: field, target roles, levels, skills, languages, places, work arrangements, where you can work, the salary you want - to find jobs and check them against what you want.</li>
          <li>Your saved searches, the jobs found for you, what you saved or hid, and each job&apos;s fit score.</li>
          <li>Your applications: their status, dates, next steps and notes.</li>
          <li>Your CV and the PDFs made from it (the newest {facts?.cv_files_kept ?? 10}).</li>
          <li>How much AI scoring you&apos;ve used this month - to keep within the monthly allowance.</li>
          <li>Technical logs: which pages and features were used, when, by which account number. Never your CV, your notes or what you type.</li>
        </ul>
        <p>
          All of it is used only to give you the service you signed up for (the legal basis is the contract between you and the site); the logs also keep the site secure and working
          (legitimate interests). Nothing is sold, and there&apos;s no advertising or tracking.
        </p>
      </Section>

      <Section title="Who else sees it">
        <ul className="list-disc pl-5">
          {facts?.ai_provider === "anthropic" ? (
            <li>
              <strong className="font-medium text-ink">Anthropic</strong> (the Claude API), when a job&apos;s fit is scored: your profile - headline, summary, skills, levels,
              target roles, languages and the deal-breaker checks - and the job posting are sent to score the fit. Your email and your other data aren&apos;t sent. Anthropic is in
              the United States; see{" "}
              <a href="https://www.anthropic.com/legal/privacy" className="underline underline-offset-2">
                Anthropic&apos;s privacy policy
              </a>
              .
            </li>
          ) : (
            <li>AI fit scores are worked out on this server; nothing is sent to an AI company.</li>
          )}
          {facts && facts.sources.length > 0 && (
            <li>
              Job boards -{" "}
              {facts.sources.map((source, i) => (
                <span key={source.label}>
                  {i > 0 && ", "}
                  <a href={source.homepage} className="underline underline-offset-2">
                    {source.label}
                  </a>
                </span>
              ))}{" "}
              - receive only the search terms and countries, never anything about you.
            </li>
          )}
          <li>{devMail ? "Sign-in emails are caught on this server (it's set up for testing)." : `Sign-in emails are sent through ${host}, which sees your email address.`}</li>
          <li>{facts?.storage ? `CV PDFs are stored with ${facts.storage}.` : "CV PDFs are stored on this server."}</li>
          {facts?.error_reports && (
            <li>
              <strong className="font-medium text-ink">Sentry</strong> receives a report when something breaks: the error, without your details, what you sent or
              what you typed.
            </li>
          )}
          {facts?.billing && (
            <li>
              <strong className="font-medium text-ink">Stripe</strong> handles payments; card details go to Stripe, never to this site.
            </li>
          )}
        </ul>
        <p>Some of these services are outside the UK, in the United States for example; the person running this site is responsible for the safeguards such transfers need.</p>
      </Section>

      <Section title="Cookies">
        <p>One cookie, which keeps you signed in. It&apos;s needed for the site to work, so there&apos;s nothing to agree to. No analytics or advertising cookies.</p>
      </Section>

      <Section title="Automated checks">
        <p>
          Jobs are checked against your deal-breakers and given an AI fit score, to sort and filter them for you. These are suggestions: they don&apos;t decide anything about you,
          and you can see every job, including the ones filtered out.
        </p>
      </Section>

      <Section title="How long it's kept">
        <p>
          Until you delete it. Deleting your account removes everything above straight away, files included; backups the site keeps may hold a copy until they expire. Shared job
          postings stay, without anything of yours.
        </p>
      </Section>

      <Section title="Your rights">
        <ul className="list-disc pl-5">
          <li>See and take a copy of your data: Settings → Your data → Download my data (a ZIP with all of it, as JSON and CSV, and your CV PDFs).</li>
          <li>Correct it: everything is editable in Settings, Applications and CV.</li>
          <li>Delete it: Settings → Your data → Delete my account.</li>
          <li>Object to or restrict how it&apos;s used, or ask anything else: write to {contact}.</li>
          <li>
            Complain to the{" "}
            <a href="https://ico.org.uk/make-a-complaint/" className="underline underline-offset-2">
              Information Commissioner&apos;s Office
            </a>{" "}
            in the UK, or the data protection authority where you live.
          </li>
        </ul>
      </Section>

      <p className="text-sm text-ink-muted">This notice describes Job Hunter as of 1 November 2026, and what this site is set up to do.</p>
    </article>
  );
}
