"use client";

import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import { ErrorBanner } from "@/components/Feedback";
import { Checkbox, MultiSelect, PillGroup, SelectField, TagInput, TextArea, TextField } from "@/components/Fields";
import { api } from "@/lib/api";
import { parseAmount, toWrite } from "@/lib/profile";
import type { Me, Option, Presets, ProfileWrite } from "@/lib/types";
import { useIndustry, useMarket } from "@/lib/usePreset";

const STEPS = ["Your field", "Roles", "Where and how", "About you"];

function Cards({
  label,
  options,
  value,
  onChange,
  columns = "sm:grid-cols-2 lg:grid-cols-3",
}: {
  label: string;
  options: (Option & { description?: string })[];
  value: string;
  onChange: (key: string) => void;
  columns?: string;
}) {
  return (
    <fieldset>
      <legend className="text-sm font-medium text-ink-secondary">{label}</legend>
      <div role="radiogroup" className={`mt-2 grid gap-2 ${columns}`}>
        {options.map((option) => {
          const on = option.key === value;
          return (
            <button
              key={option.key}
              type="button"
              role="radio"
              aria-checked={on}
              onClick={() => onChange(option.key)}
              className={`rounded-xl border p-3 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-foreground ${
                on ? "border-foreground bg-ink/[0.05] ring-1 ring-foreground" : "border-edge bg-surface hover:bg-ink/[0.03]"
              }`}
            >
              <span className="block text-[15px] font-medium">{option.label}</span>
              {option.description && <span className="mt-0.5 block text-sm text-ink-secondary">{option.description}</span>}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

function Step({ title, intro, children }: { title: string; intro: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-6">
      <div>
        <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
        <p className="mt-1 text-[15px] text-ink-secondary">{intro}</p>
      </div>
      {children}
    </section>
  );
}

export default function OnboardingFlow({ me, presets }: { me: Me; presets: Presets }) {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<ProfileWrite>(() => ({ ...toWrite(me.profile), display_name: me.profile?.display_name || me.name || "" }));
  const [roles, setRoles] = useState<string[]>([]);
  const [customRoles, setCustomRoles] = useState<string[]>([]);
  const [salary, setSalary] = useState(draft.salary_min?.toString() ?? "");
  const [state, setState] = useState<{ saving: boolean; error: string | null }>({ saving: false, error: null });
  const industry = useIndustry(draft.industry);
  const market = useMarket(draft.market);
  const set = (change: Partial<ProfileWrite>) => setDraft((current) => ({ ...current, ...change }));

  function chooseIndustry(key: string) {
    if (key !== draft.industry) setRoles([]);
    set({ industry: key });
  }

  function chooseMarket(key: string) {
    const chosen = presets.markets.find((m) => m.key === key);
    set({
      market: key,
      salary_currency: chosen?.currency ?? draft.salary_currency,
      work_arrangements: key === "remote" ? ["remote"] : draft.work_arrangements,
    });
  }

  const amount = parseAmount(salary);
  const ready = [
    Boolean(draft.industry && draft.market),
    roles.length + customRoles.length > 0,
    !Number.isNaN(amount),
    true,
  ];

  async function finish() {
    setState({ saving: true, error: null });
    try {
      await api<Me>("/me/onboarding", {
        method: "POST",
        body: JSON.stringify({
          ...draft,
          salary_min: amount,
          headline: draft.headline || industry?.roles.find((r) => r.key === roles[0])?.label || customRoles[0] || "",
          roles,
          custom_roles: customRoles.map((label) => ({ label, titles: [label], exclude: [], search: [label], preset_role: "" })),
        }),
      });
      router.replace("/");
      router.refresh();
    } catch (error) {
      setState({ saving: false, error: error instanceof Error ? error.message : "Couldn't save." });
    }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-8">
      <div>
        <p className="text-sm font-medium text-ink-muted">
          Set up · step {step + 1} of {STEPS.length}
        </p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">Tell Job Hunter what you’re looking for</h1>
        <ol className="mt-4 grid grid-cols-4 gap-1.5" aria-label="Steps">
          {STEPS.map((name, index) => (
            <li key={name} aria-current={index === step ? "step" : undefined}>
              <span className={`block h-1 rounded-full ${index <= step ? "bg-foreground" : "bg-hairline"}`} />
              <span className={`mt-1.5 hidden text-xs sm:block ${index === step ? "text-ink" : "text-ink-muted"}`}>{name}</span>
            </li>
          ))}
        </ol>
      </div>

      {step === 0 && (
        <Step title="Your field and where you’re looking" intro="This picks the job titles, search terms and skills Job Hunter suggests. You can change any of it later.">
          <Cards label="Industry" options={presets.industries} value={draft.industry} onChange={chooseIndustry} />
          <Cards label="Job market" options={presets.markets} value={draft.market} onChange={chooseMarket} columns="grid-cols-2 sm:grid-cols-4" />
        </Step>
      )}

      {step === 1 && (
        <Step title="The roles you’re after" intro="Pick the roles that fit. Each one comes with the job titles it covers, which you can fine-tune in Settings.">
          <fieldset>
            <legend className="text-sm font-medium text-ink-secondary">{industry ? `Roles in ${industry.label}` : "Loading roles..."}</legend>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {industry?.roles.map((role) => {
                const on = roles.includes(role.key);
                return (
                  <label
                    key={role.key}
                    className={`flex cursor-pointer gap-3 rounded-xl border p-3 transition-colors ${on ? "border-foreground bg-ink/[0.05]" : "border-edge bg-surface hover:bg-ink/[0.03]"}`}
                  >
                    <input
                      type="checkbox"
                      checked={on}
                      onChange={() => setRoles(on ? roles.filter((k) => k !== role.key) : [...roles, role.key])}
                      className="mt-1 size-4 shrink-0 accent-foreground"
                    />
                    <span>
                      <span className="block text-[15px] font-medium">{role.label}</span>
                      <span className="mt-0.5 block text-sm text-ink-secondary">{role.titles.slice(0, 4).join(", ")}</span>
                    </span>
                  </label>
                );
              })}
            </div>
          </fieldset>
          <TagInput
            label="Other roles, in your own words"
            values={customRoles}
            onChange={setCustomRoles}
            placeholder="e.g. Clinical research nurse"
            max={12 - roles.length}
            split
          />
          <PillGroup
            label="Levels you’re after"
            options={presets.levels}
            values={draft.seniority_levels}
            onChange={(values) => set({ seniority_levels: values })}
            hint="Leave them all off to see every level."
          />
          <div className="max-w-48">
            <TextField
              label="Years of experience"
              value={draft.years_experience?.toString() ?? ""}
              onChange={(value) => set({ years_experience: /^\d{1,2}$/.test(value) ? Number(value) : null })}
              inputMode="numeric"
              maxLength={2}
            />
          </div>
        </Step>
      )}

      {step === 2 && (
        <Step title="Where and how you want to work" intro="Jobs that break these are left out or flagged, so be as open as you really are.">
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
            hint="Countries where you already have the right to work."
          />
          <Checkbox
            label="I’m open to jobs elsewhere that sponsor a visa"
            checked={draft.open_to_sponsorship}
            onChange={(checked) => set({ open_to_sponsorship: checked })}
          />
          <div className="grid gap-4 sm:grid-cols-[2fr_1fr_1fr]">
            <TextField
              label="Minimum salary (optional)"
              value={salary}
              onChange={setSalary}
              placeholder="e.g. 32,000"
              inputMode="numeric"
              maxLength={12}
              hint={Number.isNaN(amount) ? "Write a number, like 32000 or 32k." : undefined}
            />
            <SelectField
              label="Currency"
              value={draft.salary_currency}
              onChange={(value) => set({ salary_currency: value })}
              options={presets.currencies.map((c) => ({ key: c, label: c }))}
            />
            <SelectField label="Per" value={draft.salary_period} onChange={(value) => set({ salary_period: value })} options={presets.salary_periods} />
          </div>
        </Step>
      )}

      {step === 3 && (
        <Step title="A little about you" intro="Used to score how well each job fits. Everything here is optional.">
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField label="Your name" value={draft.display_name} onChange={(value) => set({ display_name: value })} />
            <TextField
              label="Headline"
              value={draft.headline}
              onChange={(value) => set({ headline: value })}
              placeholder={industry?.roles.find((r) => r.key === roles[0])?.label ?? "e.g. Registered nurse"}
            />
          </div>
          <TagInput
            label="Skills"
            values={draft.skills}
            onChange={(values) => set({ skills: values })}
            suggestions={industry?.skills ?? []}
            placeholder="Add a skill"
            showSuggestions={20}
          />
          <TextArea
            label="What you’re looking for, in your own words"
            value={draft.summary}
            onChange={(value) => set({ summary: value })}
            placeholder="e.g. Ward nurse with four years in acute medicine, looking to move into clinical research."
          />
        </Step>
      )}

      {state.error && <ErrorBanner message={state.error} />}

      <div className="flex items-center justify-between border-t border-hairline pt-5">
        <button
          type="button"
          onClick={() => setStep(step - 1)}
          disabled={step === 0}
          className="h-10 rounded-xl px-4 text-sm font-medium text-ink-secondary hover:bg-ink/[0.04] disabled:invisible"
        >
          Back
        </button>
        {step < STEPS.length - 1 ? (
          <button
            type="button"
            onClick={() => setStep(step + 1)}
            disabled={!ready[step]}
            className="h-10 rounded-xl bg-foreground px-5 text-sm font-medium text-background hover:opacity-90 disabled:opacity-40"
          >
            Continue
          </button>
        ) : (
          <button
            type="button"
            onClick={finish}
            disabled={state.saving || !ready.every(Boolean)}
            className="h-10 rounded-xl bg-foreground px-5 text-sm font-medium text-background hover:opacity-90 disabled:opacity-40"
          >
            {state.saving ? "Saving..." : "Finish"}
          </button>
        )}
      </div>
    </div>
  );
}
