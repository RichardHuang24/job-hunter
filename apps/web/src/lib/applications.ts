// The Applications page's small pure helpers.
import type { ApplicationCounts, Option } from "./types";

export const ACTIVE = ["planned", "applied", "interviewing", "offer"];

/** The API's labels (APPLICATION_STATUSES), for places that don't load the presets. */
export const STATUS_LABELS: Record<string, string> = {
  planned: "To apply", applied: "Applied", interviewing: "Interviewing", offer: "Offer",
  accepted: "Accepted", rejected: "Rejected", withdrawn: "Withdrawn", no_response: "No response",
};

export type AppView = { key: string; label: string; empty: string };

/** The tabs: everything still open, each open status, then closed and all. */
export function appViews(statuses: Option[]): AppView[] {
  const label = (key: string) => statuses.find((s) => s.key === key)?.label ?? key;
  return [
    { key: "active", label: "Active", empty: "Nothing in progress. Track a job from Jobs (“I've applied”), or add one here." },
    ...ACTIVE.map((key) => ({ key, label: label(key), empty: `Nothing at “${label(key)}”.` })),
    { key: "closed", label: "Closed", empty: "Applications that ended - an answer, or none - go here." },
    { key: "all", label: "All", empty: "No applications yet." },
  ];
}

export function viewCount(key: string, counts: ApplicationCounts): number {
  if (key === "active") return counts.active;
  if (key === "closed") return counts.closed;
  if (key === "all") return counts.active + counts.closed;
  return counts.by_status[key] ?? 0;
}

/** "2026-11-12" -> "12 Nov" (with the year when it isn't this year). */
export function day(iso: string, today = new Date()): string {
  const date = new Date(`${iso}T00:00:00Z`);
  const sameYear = date.getUTCFullYear() === today.getUTCFullYear();
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: sameYear ? undefined : "numeric", timeZone: "UTC" });
}

export function todayIso(now = new Date()): string {
  return now.toISOString().slice(0, 10);
}

/** How soon a next step is: overdue, today, tomorrow, or a date. */
export function due(iso: string, now = new Date()): { text: string; tone: "late" | "soon" | "later" } {
  const days = Math.round((Date.parse(`${iso}T00:00:00Z`) - Date.parse(`${todayIso(now)}T00:00:00Z`)) / 86_400_000);
  if (days < 0) return { text: `Overdue - ${day(iso, now)}`, tone: "late" };
  if (days === 0) return { text: "Today", tone: "soon" };
  if (days === 1) return { text: "Tomorrow", tone: "soon" };
  return { text: day(iso, now), tone: "later" };
}
