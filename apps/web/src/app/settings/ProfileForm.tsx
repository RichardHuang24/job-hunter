"use client";

import { useState, type FormEvent } from "react";
import Card from "@/components/Card";
import { ErrorBanner } from "@/components/Feedback";
import { api } from "@/lib/api";
import type { Preset, Presets, Profile } from "@/lib/types";

const FIELD = "h-10 rounded-lg border border-edge bg-surface px-3 text-[15px] text-ink";

function Choice({ name, label, options, value }: { name: string; label: string; options: Preset[]; value: string }) {
  return (
    <label className="flex flex-col gap-1 text-sm font-medium text-ink-secondary">
      {label}
      <select name={name} defaultValue={value} className={FIELD}>
        <option value="">Not set</option>
        {options.map((option) => (
          <option key={option.key} value={option.key}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

export default function ProfileForm({ initial, presets }: { initial: Profile | null; presets: Presets }) {
  const [state, setState] = useState<{ saving: boolean; saved: string | null; error: string | null }>({
    saving: false,
    saved: null,
    error: null,
  });

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const body = Object.fromEntries(["display_name", "headline", "industry", "market"].map((key) => [key, String(form.get(key) ?? "")]));
    setState({ saving: true, saved: null, error: null });
    try {
      const profile = await api<Profile>("/me/profile", { method: "PUT", body: JSON.stringify(body) });
      setState({ saving: false, saved: new Date(profile.updated_at).toLocaleTimeString(), error: null });
    } catch (error) {
      setState({ saving: false, saved: null, error: error instanceof Error ? error.message : "Couldn't save." });
    }
  }

  return (
    <Card title="Profile" subtitle="What you're looking for. Job search and scoring will read this.">
      <form onSubmit={save} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-sm font-medium text-ink-secondary">
          Display name
          <input name="display_name" defaultValue={initial?.display_name ?? ""} maxLength={255} className={FIELD} />
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium text-ink-secondary">
          Headline
          <input
            name="headline"
            defaultValue={initial?.headline ?? ""}
            maxLength={255}
            placeholder="e.g. Registered nurse moving into clinical research"
            className={FIELD}
          />
        </label>
        <div className="grid gap-4 sm:grid-cols-2">
          <Choice name="industry" label="Industry" options={presets.industries} value={initial?.industry ?? ""} />
          <Choice name="market" label="Where you want to work" options={presets.markets} value={initial?.market ?? ""} />
        </div>
        {state.error && <ErrorBanner message={state.error} />}
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={state.saving}
            className="h-10 rounded-xl bg-foreground px-5 text-sm font-medium text-background hover:opacity-90 disabled:opacity-50"
          >
            {state.saving ? "Saving..." : "Save"}
          </button>
          <p role="status" className="text-sm text-ink-secondary">
            {state.saved && `Saved at ${state.saved}.`}
          </p>
        </div>
      </form>
    </Card>
  );
}
