import { redirect } from "next/navigation";
import { auth, signIn, signInOptions } from "@/auth";
import { backendPublic } from "@/lib/backend";
import { demoMode } from "@/lib/demo";

// Auth.js error codes -> what to tell the person.
const ERRORS: Record<string, string> = {
  Verification: "That sign-in link has expired or was already used. Ask for a new one.",
  Configuration: "Sign-in isn't set up correctly on this server.",
  AccessDenied: "That account can't sign in here.",
  OAuthAccountNotLinked: "That email already signs in another way - use the method you used before.",
  DemoBusy: "The demo is busy right now - try again in a few minutes.",
  DemoFailed: "Couldn't start the demo. Try again in a moment.",
};

type DemoPerson = { key: string; name: string; headline: string; description: string };
type Demo = { enabled: boolean; account_hours: number; people: DemoPerson[] };

/** The demo site's sign-in: pick a fictional person (apps/api/app/demo.py). */
function DemoChoice({ demo }: { demo: Demo }) {
  return (
    <div className="flex flex-col gap-3">
      {demo.people.map((person) => (
        <form key={person.key} method="post" action="/demo/start" className="rounded-xl border border-edge bg-surface p-4">
          <input type="hidden" name="person" value={person.key} />
          <p className="font-medium">
            {person.name} <span className="font-normal text-ink-secondary">· {person.headline}</span>
          </p>
          <p className="mt-0.5 text-sm text-ink-secondary">{person.description}</p>
          <button type="submit" className="mt-3 h-9 w-full rounded-lg bg-foreground text-sm font-medium text-background hover:opacity-90">
            Try as {person.name.split(" ")[0]}
          </button>
        </form>
      ))}
      <p className="text-xs text-ink-muted">
        Everyone, every job and every company here is made up. You get your own copy of the account - change anything - and it&apos;s deleted after{" "}
        {demo.account_hours} hours.
      </p>
    </div>
  );
}

export default async function SignInPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  if ((await auth())?.user) redirect("/");
  const { error, callbackUrl, deleted } = await searchParams;
  const redirectTo = callbackUrl?.startsWith("/") ? callbackUrl : "/";
  const demo = demoMode() ? await backendPublic<Demo>("/demo") : null;
  const email = demo ? undefined : signInOptions.find((option) => option.type === "email");
  const oauth = demo ? [] : signInOptions.filter((option) => option.type !== "email");

  return (
    <div className="mx-auto flex max-w-sm flex-col gap-6 pt-10">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">{demo ? "Try Job Hunter" : "Sign in"}</h1>
        <p className="mt-2 text-[15px] text-ink-secondary">
          {demo
            ? "Pick someone to be: they arrive with jobs found and scored, applications in progress and a CV."
            : "Find, rank and track jobs, and build your CV - for any industry."}
        </p>
      </div>
      {deleted && (
        <p role="status" className="rounded-lg border border-edge bg-surface px-4 py-3 text-sm">
          Your account and everything in it have been deleted.
        </p>
      )}
      {error && (
        <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-700 dark:text-red-300">
          {ERRORS[error] ?? "Couldn't sign you in. Try again."}
        </p>
      )}
      {email && (
        <form
          className="flex flex-col gap-3"
          action={async (formData) => {
            "use server";
            // Straight to our check-email page (Auth.js's own redirect would leave
            // its /api/auth/verify-request address in the browser's address bar).
            const sent = await signIn(email.id, { email: String(formData.get("email") ?? ""), redirectTo, redirect: false });
            const error = new URL(sent, "http://localhost").searchParams.get("error");
            redirect(error ? `/signin?error=${encodeURIComponent(error)}` : "/signin/check-email");
          }}
        >
          <label className="flex flex-col gap-1 text-sm font-medium text-ink-secondary">
            Email
            <input
              name="email"
              type="email"
              required
              autoComplete="email"
              placeholder="you@example.com"
              className="h-10 rounded-lg border border-edge bg-surface px-3 text-[15px] text-ink"
            />
          </label>
          <button type="submit" className="h-10 rounded-xl bg-foreground text-sm font-medium text-background hover:opacity-90">
            Email me a sign-in link
          </button>
        </form>
      )}
      {oauth.length > 0 && (
        <div className="flex flex-col gap-2">
          {email && <p className="text-center text-xs text-ink-muted">or</p>}
          {oauth.map((option) => (
            <form
              key={option.id}
              action={async () => {
                "use server";
                await signIn(option.id, { redirectTo });
              }}
            >
              <button type="submit" className="h-10 w-full rounded-xl border border-edge bg-surface text-sm font-medium hover:bg-ink/[0.04]">
                Continue with {option.name}
              </button>
            </form>
          ))}
        </div>
      )}
      {demo && <DemoChoice demo={demo} />}
      {!demo && !signInOptions.length && (
        <p className="rounded-lg border border-edge bg-surface px-4 py-3 text-sm text-ink-secondary">
          No sign-in method is set up. Set <code>EMAIL_SERVER</code> (or GitHub / Google) in <code>.env</code> - see the README.
        </p>
      )}
    </div>
  );
}
