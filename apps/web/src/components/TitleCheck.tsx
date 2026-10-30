"use client";

import { useState, type FormEvent } from "react";
import Card from "@/components/Card";
import { ErrorBanner } from "@/components/Feedback";
import { INPUT } from "@/components/Fields";
import { api } from "@/lib/api";
import type { TitleCheck as Result } from "@/lib/types";

/** Try a job title against the saved roles and levels - the rules job search will use. */
export default function TitleCheck() {
  const [title, setTitle] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function check(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!title.trim()) return;
    setError(null);
    try {
      setResult(await api<Result>("/me/title-check", { method: "POST", body: JSON.stringify({ title }) }));
    } catch (failure) {
      setResult(null);
      setError(failure instanceof Error ? failure.message : "Couldn't check that title.");
    }
  }

  return (
    <Card title="Check a job title" subtitle="How job search will read a title, using your saved roles and levels.">
      <form onSubmit={check} className="flex gap-2">
        <label htmlFor="title-check" className="sr-only">
          Job title
        </label>
        <input
          id="title-check"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="e.g. Senior Staff Nurse - Band 6"
          maxLength={200}
          className={INPUT}
        />
        <button type="submit" className="h-10 shrink-0 rounded-xl border border-edge px-4 text-sm font-medium hover:bg-ink/[0.04]">
          Check
        </button>
      </form>
      <div aria-live="polite">
        {error && (
          <div className="mt-3">
            <ErrorBanner message={error} />
          </div>
        )}
        {result && (
          <div className="mt-3 rounded-lg border border-edge px-4 py-3">
            <p className="flex items-center gap-2 text-[15px] font-medium">
              <span
                aria-hidden
                className={`grid size-5 place-items-center rounded-full text-xs text-white ${result.wanted ? "bg-green-700" : "bg-ink-muted"}`}
              >
                {result.wanted ? "✓" : "–"}
              </span>
              {result.wanted ? "Would be included" : "Would be left out"}
            </p>
            <p className="mt-1 text-sm text-ink-secondary">{result.explanation}</p>
            <p className="mt-2 text-xs text-ink-muted">
              Level: {result.level.label}
              {result.level_words.length > 0 && ` (from “${result.level_words.join("”, “")}”)`}
            </p>
          </div>
        )}
      </div>
    </Card>
  );
}
