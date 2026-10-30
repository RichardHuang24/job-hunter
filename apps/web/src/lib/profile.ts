// Profile helpers shared by onboarding, settings and the dashboard. Pure -
// tested in profile.test.mts.
import type { Option, Profile, ProfileWrite } from "./types.ts";

export function emptyProfile(): ProfileWrite {
  return {
    display_name: "",
    headline: "",
    summary: "",
    industry: "",
    market: "",
    years_experience: null,
    seniority_levels: [],
    skills: [],
    languages: [],
    locations: [],
    work_arrangements: [],
    authorized_countries: [],
    open_to_sponsorship: false,
    salary_min: null,
    salary_currency: "",
    salary_period: "year",
  };
}

/** What PUT /me/profile takes, from what GET /me returned. */
export function toWrite(profile: Profile | null): ProfileWrite {
  const write = emptyProfile();
  if (!profile) return write;
  for (const key of Object.keys(write) as (keyof ProfileWrite)[]) {
    (write as Record<string, unknown>)[key] = profile[key] ?? write[key];
  }
  return write;
}

/** "32,000" or "£32k" -> 32000; "" -> null; anything else -> NaN. */
export function parseAmount(text: string): number | null {
  const compact = text.replace(/[\s,£$€]/g, "").toLowerCase();
  if (!compact) return null;
  const match = /^(\d+(?:\.\d+)?)(k?)$/.exec(compact);
  if (!match) return Number.NaN;
  return Math.round(Number(match[1]) * (match[2] ? 1000 : 1));
}

export function labelOf(options: Option[] | undefined, key: string): string {
  return options?.find((option) => option.key === key)?.label ?? key;
}

/** Keys -> "On-site, hybrid or remote" style text, in the options' order. */
export function listOf(options: Option[] | undefined, keys: string[], joiner = "or"): string {
  const labels = (options ?? []).filter((option) => keys.includes(option.key)).map((option) => option.label);
  if (labels.length <= 1) return labels[0] ?? "";
  const rest = labels.slice(1).map((label) => label.toLocaleLowerCase());
  return `${[labels[0], ...rest.slice(0, -1)].join(", ")} ${joiner} ${rest.at(-1)}`;
}

/** 32000, "GBP", "year" -> "£32,000 per year" */
export function formatSalary(amount: number, currency: string, period: string, periods?: Option[]): string {
  let money: string;
  try {
    money = new Intl.NumberFormat("en-GB", { style: "currency", currency, maximumFractionDigits: 0 }).format(amount);
  } catch {
    money = `${amount.toLocaleString("en-GB")} ${currency}`;
  }
  return `${money} ${labelOf(periods, period) === period ? `per ${period}` : labelOf(periods, period)}`;
}
