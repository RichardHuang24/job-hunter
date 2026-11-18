"use client";

import { useState } from "react";

export default function RoleStart() {
  const [title, setTitle] = useState("");
  const [starting, setStarting] = useState(false);
  return (
    <form method="post" action="/demo/start" onSubmit={() => setStarting(true)} className="flex flex-col gap-4">
      <label htmlFor="target-role" className="text-sm font-medium">What role are you looking for?</label>
      <div className="flex flex-col gap-3 sm:flex-row">
        <input id="target-role" name="job_title" value={title} onChange={(event) => setTitle(event.target.value)}
          required minLength={2} maxLength={80} autoComplete="off" placeholder="e.g. Data Analyst"
          className="h-12 min-w-0 flex-1 rounded-xl border border-edge bg-background px-4 text-base outline-offset-4" />
        <button type="submit" disabled={starting} className="h-12 rounded-xl bg-foreground px-6 font-medium text-background hover:opacity-90 disabled:opacity-60">
          {starting ? "Opening your workspace…" : "Start exploring →"}
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs text-ink-secondary">
        <span>Try a role</span>
        {["Data Analyst", "Registered Nurse", "Product Designer"].map((role) => (
          <button key={role} type="button" onClick={() => setTitle(role)} className="rounded-full border border-edge px-3 py-1.5 hover:bg-ink/[0.04]">{role}</button>
        ))}
      </div>
    </form>
  );
}
