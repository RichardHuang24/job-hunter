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
  application_statuses: Option[];
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

export type Source = {
  key: string;
  label: string;
  description: string;
  homepage: string;
  countries: string[];
  commercial: boolean;
  demo: boolean;
  remote_only: boolean;
};

export type SearchWrite = {
  name: string;
  terms: string[];
  locations: string[];
  countries: string[];
  include_remote: boolean;
  sources: string[];
  daily: boolean;
};

export type Run = {
  id: string;
  search_id: string;
  status: "queued" | "running" | "succeeded" | "failed";
  trigger: string;
  counts: { queries?: number; found?: number; new?: number; matches?: number; flagged?: number; filtered?: number; by_source?: Record<string, number> };
  errors: { source: string; message: string }[];
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type Search = SearchWrite & {
  id: string;
  next_run_at: string | null;
  last_run_at: string | null;
  created_at: string;
  last_run: Run | null;
};

export type Check = { key: string; status: "pass" | "flag" | "fail" | "unknown"; detail: string };

export type JobPosting = {
  id: string;
  source: string;
  source_label: string;
  source_url: string;
  demo: boolean;
  closed: boolean;
  url: string;
  title: string;
  company: string;
  location: string;
  country: string;
  arrangement: string;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string;
  salary_period: string;
  posted_at: string | null;
  description?: string;
};

export type UserJob = {
  id: string;
  state: "new" | "saved" | "hidden";
  verdict: "match" | "flagged" | "filtered";
  role: string;
  level: Option;
  checks: Check[];
  first_seen_at: string;
  job: JobPosting;
  score: ScoreBrief | Score | null;
  application: { id: string; status: string } | null;
};

export type JobCounts = { matches: number; flagged: number; filtered: number; saved: number; hidden: number };
export type JobList = { items: UserJob[]; total: number; counts: JobCounts };

export type ScoreBrief = {
  status: "queued" | "done" | "failed";
  overall: number | null;
  band: string;
  simulated: boolean;
  stale: boolean;
};

export type Evidence = { requirement: string; verified: boolean; detail: string; note: string; kind: string };

export type Score = ScoreBrief & {
  advice: string;
  provider: string;
  model: string;
  dimensions: { key: string; label: string; weight: number; score: number; reason: string }[];
  summary: string;
  matched: Evidence[];
  missing: Evidence[];
  risks: string[];
  unclear: string[];
  error: string;
  error_code: string;
  cost_usd: number;
  requested_at: string;
  scored_at: string | null;
};

export type AiStatus = {
  provider: "anthropic" | "simulated";
  model: string;
  effort: string;
  auto_score: boolean;
  month: string;
  scores_used: number;
  scores_limit: number;
  queued: number;
  cost_usd: number;
  budget_usd: number;
};

export type Experience = { title: string; employer: string; location: string; start: string; end: string; bullets: string[] };

export type Education = { qualification: string; institution: string; location: string; start: string; end: string; details: string };

export type CvContent = {
  name: string;
  headline: string;
  email: string;
  phone: string;
  location: string;
  links: string[];
  summary: string;
  experience: Experience[];
  education: Education[];
  skills: string[];
  languages: Language[];
};

export type CvDocument = {
  id: string;
  kind: string;
  status: "queued" | "done" | "failed";
  filename: string;
  size_bytes: number;
  pages: number;
  error: string;
  requested_at: string;
  finished_at: string | null;
};

export type Cv = { content: CvContent; saved: boolean; updated_at: string | null; documents: CvDocument[] };

export type ApplicationEvent = { kind: "created" | "status"; status: string; at: string };

export type Application = {
  id: string;
  user_job_id: string | null;
  title: string;
  company: string;
  location: string;
  url: string;
  status: string;
  applied_on: string | null;
  next_step: string;
  next_step_on: string | null;
  notes: string;
  job_closed: boolean;
  created_at: string;
  updated_at: string;
  events?: ApplicationEvent[];
};

export type ApplicationCounts = { active: number; closed: number; by_status: Record<string, number> };

export type ApplicationList = { items: Application[]; total: number; counts: ApplicationCounts };
