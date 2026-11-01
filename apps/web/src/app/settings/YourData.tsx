"use client";

import { useActionState, useId, useState } from "react";
import Card from "@/components/Card";
import { INPUT } from "@/components/Fields";
import { deleteAccount, type DeleteState } from "./actions";

export default function YourData({ email }: { email: string }) {
  const [state, action, pending] = useActionState<DeleteState, FormData>(deleteAccount, { error: null });
  const [typed, setTyped] = useState("");
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <Card title="Your data" subtitle="Everything kept about you is yours: take a copy, or delete it all.">
      <div className="flex flex-col gap-4">
        <div>
          {/* A file download through the API door, not a page - so a plain link. */}
          <a href="/api/backend/me/export" download className="inline-block rounded-lg border border-edge px-3 py-1.5 text-sm font-medium hover:bg-ink/[0.04]">
            Download my data
          </a>
          <p className="mt-1 text-xs text-ink-muted">A ZIP: your profile, searches, jobs and scores, applications and CV as JSON and CSV, and your CV PDFs.</p>
        </div>
        <div className="border-t border-hairline pt-4">
          {!open ? (
            <button type="button" onClick={() => setOpen(true)} className="text-sm font-medium text-red-700 hover:underline dark:text-red-400">
              Delete my account...
            </button>
          ) : (
            <form action={action} className="flex flex-col gap-2">
              <p className="text-sm text-ink-secondary">
                This deletes your account and everything in it - profile, jobs, applications, CV and PDFs - straight away. It can&apos;t be undone.
              </p>
              <label htmlFor={id} className="text-sm font-medium text-ink-secondary">
                Type your email address ({email}) to confirm
              </label>
              <input id={id} name="confirm" value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" className={INPUT} />
              {state.error && <p className="text-sm text-red-700 dark:text-red-400">{state.error}</p>}
              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={pending || typed.trim().toLowerCase() !== email.toLowerCase()}
                  className="h-9 rounded-lg bg-red-700 px-3.5 text-sm font-medium text-white hover:bg-red-800 disabled:opacity-40"
                >
                  {pending ? "Deleting..." : "Delete everything"}
                </button>
                <button type="button" onClick={() => setOpen(false)} className="h-9 rounded-lg px-3.5 text-sm text-ink-secondary hover:bg-ink/[0.05]">
                  Cancel
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </Card>
  );
}
