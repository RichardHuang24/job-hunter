// Job and search helpers shared by the Jobs pages and the dashboard. Pure -
// tested in jobs.test.mts.
import type { JobCounts, Run } from "./types.ts";

export const VIEWS: { key: keyof JobCounts; label: string; empty: string }[] = [
  { key: "matches", label: "Matches", empty: "No matches yet. Have a look at Flagged and Filtered out, or widen your search." },
  { key: "flagged", label: "Flagged", empty: "Nothing flagged. Flagged jobs pass your deal-breakers but have something worth checking." },
  { key: "filtered", label: "Filtered out", empty: "Nothing filtered out." },
  { key: "saved", label: "Saved", empty: "Save jobs you want to come back to." },
  { key: "hidden", label: "Hidden", empty: "Jobs you hide go here." },
];

export const ARRANGEMENTS: Record<string, string> = { onsite: "On-site", hybrid: "Hybrid", remote: "Remote" };
const PERIODS: Record<string, string> = { year: "a year", month: "a month", day: "a day", hour: "an hour" };

function money(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat("en-GB", { style: "currency", currency, maximumFractionDigits: 0 }).format(amount);
  } catch {
    return `${amount.toLocaleString("en-GB")} ${currency}`;
  }
}

/** 31000, 37000, "GBP", "year" -> "£31,000–£37,000 a year"; "" when the posting has no salary. */
export function salaryRange(min: number | null, max: number | null, currency: string, period: string): string {
  if (!currency || (min === null && max === null)) return "";
  const low = min ?? max!;
  const high = max ?? min!;
  const amount = low === high ? money(low, currency) : `${money(low, currency)}–${money(high, currency)}`;
  return `${amount} ${PERIODS[period] ?? ""}`.trim();
}

const DAY = 86_400_000;

/** By the calendar day: "today", "yesterday", "3 days ago", "2 weeks ago". */
export function daysAgo(iso: string | null, now = new Date()): string {
  if (!iso) return "";
  const startOf = (d: Date) => Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
  const days = Math.round((startOf(now) - startOf(new Date(iso))) / DAY);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 14) return `${days} days ago`;
  if (days < 60) return `${Math.floor(days / 7)} weeks ago`;
  return `${Math.floor(days / 30)} months ago`;
}

/** "just now", "4 minutes ago", "2 hours ago", "3 days ago" */
export function since(iso: string | null, now = new Date()): string {
  if (!iso) return "";
  const minutes = Math.floor((now.getTime() - new Date(iso).getTime()) / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  return daysAgo(iso, now);
}

export function isActive(run: Run | null | undefined): boolean {
  return run?.status === "queued" || run?.status === "running";
}

/** What a finished run found: "6 new jobs, 4 matches" / "Nothing new". */
export function runSummary(run: Run): string {
  if (run.status === "failed") return "The search failed";
  if (isActive(run)) return run.status === "queued" ? "Waiting to start" : "Searching";
  const fresh = run.counts.new ?? 0;
  if (!fresh) return "Nothing new";
  const matches = run.counts.matches ?? 0;
  return `${fresh} new job${fresh === 1 ? "" : "s"}, ${matches} match${matches === 1 ? "" : "es"} in all`;
}
