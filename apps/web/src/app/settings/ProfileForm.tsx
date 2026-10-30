"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";
import Card from "@/components/Card";
import { ErrorBanner } from "@/components/Feedback";
import { Checkbox, INPUT, MultiSelect, PillGroup, SelectField, TagInput, TextArea, TextField } from "@/components/Fields";
import { api } from "@/lib/api";
import { parseAmount, toWrite } from "@/lib/profile";
import type { Language, Presets, Profile, ProfileWrite } from "@/lib/types";
import { useIndustry, useMarket } from "@/lib/usePreset";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="flex flex-col gap-4 border-t border-hairline pt-5 first:border-t-0 first:pt-0">
      <legend className="float-left mb-1 w-full text-[15px] font-semibold">{title}</legend>
      {children}
    </fieldset>
  );
}

function Languages({ values, onChange, levels }: { values: Language[]; onChange: (values: Language[]) => void; levels: Presets["language_levels"] }) {
  const update = (index: number, change: Partial<Language>) => onChange(values.map((v, i) => (i === index ? { ...v, ...change } : v)));
  return (
    <div>
      <p className="text-sm font-medium text-ink-secondary">Languages</p>
      <div className="mt-1 flex flex-col gap-2">
        {values.map((language, index) => (
          <div key={index} className="grid grid-cols-[1fr_1fr_auto] gap-2">
            <input
              aria-label={`Language ${index + 1}`}
              value={language.name}
              onChange={(event) => update(index, { name: event.target.value })}
              placeholder="e.g. Spanish"
              maxLength={60}
              className={INPUT}
            />
            <select aria-label={`Level for language ${index + 1}`} value={language.level} onChange={(event) => update(index, { level: event.target.value })} className={INPUT}>
              {levels.map((level) => (
                <option key={level.key} value={level.key}>
                  {level.label}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => onChange(values.filter((_, i) => i !== index))}
              aria-label={`Remove ${language.name || "this language"}`}
              className="h-10 rounded-lg px-3 text-ink-muted hover:bg-ink/[0.05] hover:text-ink"
            >
              ×
            </button>
          </div>
        ))}
      </div>
      {values.length < 10 && (
        <button
          type="button"
          onClick={() => onChange([...values, { name: "", level: "professional" }])}
          className="mt-2 rounded-lg border border-edge px-3 py-1.5 text-sm hover:bg-ink/[0.04]"
        >
          Add a language
        </button>
      )}
    </div>
  );
}

export default function ProfileForm({ initial, presets }: { initial: Profile | null; presets: Presets }) {
  const router = useRouter();
  const [draft, setDraft] = useState<ProfileWrite>(() => toWrite(initial));
  const [salary, setSalary] = useState(initial?.salary_min?.toString() ?? "");
  const [years, setYears] = useState(initial?.years_experience?.toString() ?? "");
  const [state, setState] = useState<{ saving: boolean; saved: string | null; error: string | null }>({ saving: false, saved: null, error: null });
  const industry = useIndustry(draft.industry);
  const market = useMarket(draft.market);
  const set = (change: Partial<ProfileWrite>) => setDraft((current) => ({ ...current, ...change }));
  const amount = parseAmount(salary);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (Number.isNaN(amount)) return setState({ saving: false, saved: null, error: "Minimum salary: write a number, like 32000 or 32k." });
    if (years && !/^\d{1,2}$/.test(years)) return setState({ saving: false, saved: null, error: "Years of experience: write a whole number." });
    const body: ProfileWrite = {
      ...draft,
      salary_min: amount,
      salary_currency: amount === null ? draft.salary_currency : draft.salary_currency || market?.currency || "",
      years_experience: years ? Number(years) : null,
      languages: draft.languages.filter((language) => language.name.trim()),
    };
    setState({ saving: true, saved: null, error: null });
    try {
      const profile = await api<Profile>("/me/profile", { method: "PUT", body: JSON.stringify(body) });
      setDraft(toWrite(profile));
      setState({ saving: false, saved: new Date(profile.updated_at).toLocaleTimeString(), error: null });
      router.refresh();
    } catch (error) {
      setState({ saving: false, saved: null, error: error instanceof Error ? error.message : "Couldn't save." });
    }
  }

  return (
    <Card title="Profile" subtitle="What you’re looking for. Job search and scoring read this.">
      <form onSubmit={save} className="flex flex-col gap-5">
        <Section title="About you">
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField label="Your name" value={draft.display_name} onChange={(value) => set({ display_name: value })} />
            <TextField label="Headline" value={draft.headline} onChange={(value) => set({ headline: value })} placeholder="e.g. Registered nurse" />
          </div>
          <TextArea label="What you’re looking for, in your own words" value={draft.summary} onChange={(value) => set({ summary: value })} />
        </Section>

        <Section title="Field and level">
          <div className="grid gap-4 sm:grid-cols-2">
            <SelectField label="Industry" value={draft.industry} onChange={(value) => set({ industry: value })} options={presets.industries} empty="Not set" />
            <SelectField label="Job market" value={draft.market} onChange={(value) => set({ market: value })} options={presets.markets} empty="Not set" />
          </div>
          <PillGroup
            label="Levels you’re after"
            options={presets.levels}
            values={draft.seniority_levels}
            onChange={(values) => set({ seniority_levels: values })}
            hint="Leave them all off to see every level."
          />
          <div className="max-w-48">
            <TextField label="Years of experience" value={years} onChange={setYears} inputMode="numeric" maxLength={2} />
          </div>
        </Section>

        <Section title="Where and how">
          <TagInput
            label="Locations"
            values={draft.locations}
            onChange={(values) => set({ locations: values })}
            suggestions={market?.locations ?? []}
            placeholder="A city, region or “Remote”"
            max={20}
            split={false}
            showSuggestions={20}
          />
          <PillGroup
            label="Work arrangements you’d accept"
            options={presets.arrangements}
            values={draft.work_arrangements}
            onChange={(values) => set({ work_arrangements: values })}
            hint="Leave them all off if any is fine."
          />
          <MultiSelect
            label="Where you can work without a visa"
            options={presets.countries}
            values={draft.authorized_countries}
            onChange={(values) => set({ authorized_countries: values })}
            first={market?.countries.map((c) => c.key) ?? []}
            addLabel="Add a country..."
          />
          <Checkbox
            label="I’m open to jobs elsewhere that sponsor a visa"
            checked={draft.open_to_sponsorship}
            onChange={(checked) => set({ open_to_sponsorship: checked })}
          />
          <div className="grid gap-4 sm:grid-cols-[2fr_1fr_1fr]">
            <TextField label="Minimum salary" value={salary} onChange={setSalary} placeholder="Optional" inputMode="numeric" maxLength={12} />
            <SelectField
              label="Currency"
              value={draft.salary_currency}
              onChange={(value) => set({ salary_currency: value })}
              options={presets.currencies.map((c) => ({ key: c, label: c }))}
              empty="-"
            />
            <SelectField label="Per" value={draft.salary_period} onChange={(value) => set({ salary_period: value })} options={presets.salary_periods} />
          </div>
        </Section>

        <Section title="Skills and languages">
          <TagInput
            label="Skills"
            values={draft.skills}
            onChange={(values) => set({ skills: values })}
            suggestions={industry?.skills ?? []}
            placeholder="Add a skill"
          />
          <Languages values={draft.languages} onChange={(values) => set({ languages: values })} levels={presets.language_levels} />
        </Section>

        {state.error && <ErrorBanner message={state.error} />}
        <div className="flex items-center gap-3 border-t border-hairline pt-5">
          <button
            type="submit"
            disabled={state.saving}
            className="h-10 rounded-xl bg-foreground px-5 text-sm font-medium text-background hover:opacity-90 disabled:opacity-50"
          >
            {state.saving ? "Saving..." : "Save profile"}
          </button>
          <p role="status" className="text-sm text-ink-secondary">
            {state.saved && `Saved at ${state.saved}.`}
          </p>
        </div>
      </form>
    </Card>
  );
}
