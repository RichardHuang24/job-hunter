// The API's response shapes (apps/api/app/schemas).

export type Option = { key: string; label: string };
export type Language = { name: string; level: string };

export type ProfileWrite = {
  display_name: string;
  headline: string;
  summary: string;
  industry: string;
  market: string;
  years_experience: number | null;
  seniority_levels: string[];
  skills: string[];
  languages: Language[];
  locations: string[];
  work_arrangements: string[];
  authorized_countries: string[];
  open_to_sponsorship: boolean;
  salary_min: number | null;
  salary_currency: string;
  salary_period: string;
};

export type Profile = ProfileWrite & { onboarded_at: string | null; updated_at: string };

export type TargetWrite = {
  label: string;
  titles: string[];
  exclude: string[];
  search: string[];
  preset_role: string;
};

export type Target = TargetWrite & { id: string; position: number };

export type Me = {
  id: number;
  email: string | null;
  name: string | null;
  profile: Profile | null;
  targets: Target[];
};

export type Presets = {
  industries: (Option & { description: string })[];
  markets: (Option & { currency: string })[];
  levels: Option[];
  arrangements: Option[];
  salary_periods: Option[];
  language_levels: Option[];
  countries: Option[];
  currencies: string[];
};

export type Role = Option & { titles: string[]; exclude: string[]; search: string[] };

export type Industry = Option & {
  description: string;
  skills: string[];
  roles: Role[];
  scoring: (Option & { description: string; weight: number })[];
  seniority: Record<string, string[]>;
};

export type Market = Option & {
  currency: string;
  salary_period: string;
  locations: string[];
  arrangements: string[];
  countries: Option[];
};

export type TitleCheck = {
  title: string;
  target: Target | null;
  matched: string;
  level: Option;
  level_words: string[];
  wanted: boolean;
  explanation: string;
};
