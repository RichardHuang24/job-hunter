// The API's response shapes (apps/api/app/schemas).

export type Profile = {
  display_name: string;
  headline: string;
  industry: string;
  market: string;
  updated_at: string;
};

export type Me = {
  id: number;
  email: string | null;
  name: string | null;
  profile: Profile | null;
};

export type Preset = { key: string; label: string };
export type Presets = { industries: Preset[]; markets: Preset[] };
