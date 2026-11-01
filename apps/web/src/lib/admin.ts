// The admin page's small pure helpers.
import type { AdminSource } from "./types";

export function usd(amount: number): string {
  if (amount === 0) return "$0";
  if (amount < 0.01) return `$${amount.toFixed(4)}`;
  return `$${amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** 1284 -> "1,284"; 12900 -> "12.9K"; 4200000 -> "4.2M" */
export function compact(n: number): string {
  if (n < 10_000) return n.toLocaleString("en-US");
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(n);
}

export function percent(share: number | null): string {
  return share === null ? "-" : `${Math.round(share * 100)}%`;
}

export function duration(seconds: number): string {
  if (seconds < 60) return `${seconds} s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
  if (seconds < 86_400) return `${Math.round(seconds / 3600)} h`;
  return `${Math.round(seconds / 86_400)} days`;
}

export type Health = { label: string; icon: string; tone: "good" | "warning" | "critical" | "none" };

/** A source's state over the last 7 days - always an icon and words, never colour alone. */
export function sourceHealth(source: Pick<AdminSource, "runs" | "failed" | "error_rate">): Health {
  if (!source.runs) return { label: "Not asked", icon: "–", tone: "none" };
  if (!source.failed) return { label: "Healthy", icon: "✓", tone: "good" };
  if ((source.error_rate ?? 0) < 0.5) return { label: "Some failures", icon: "!", tone: "warning" };
  return { label: "Failing", icon: "×", tone: "critical" };
}

/** The budget meter's fill: fine, nearly used (80%), used up. */
export function budgetTone(used: number | null): "accent" | "warning" | "critical" {
  if (used === null || used < 0.8) return "accent";
  return used < 1 ? "warning" : "critical";
}
