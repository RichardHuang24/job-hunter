"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import Card from "@/components/Card";
import { ErrorBanner } from "@/components/Feedback";
import { INPUT, TagInput } from "@/components/Fields";
import { api } from "@/lib/api";
import type { Target, TargetWrite } from "@/lib/types";
import { useIndustry } from "@/lib/usePreset";

const MAX = 12;

function toWrite(target: Target): TargetWrite {
  return { label: target.label, titles: target.titles, exclude: target.exclude, search: target.search, preset_role: target.preset_role };
}

export default function TargetsEditor({ initial, industryKey }: { initial: Target[]; industryKey: string }) {
  const router = useRouter();
  const [targets, setTargets] = useState<TargetWrite[]>(() => initial.map(toWrite));
  const [open, setOpen] = useState<number | null>(initial.length ? null : 0);
  const [state, setState] = useState<{ saving: boolean; saved: boolean; error: string | null }>({ saving: false, saved: false, error: null });
  const industry = useIndustry(industryKey);
  const unused = industry?.roles.filter((role) => !targets.some((t) => t.preset_role === `${industry.key}/${role.key}`)) ?? [];

  const update = (index: number, change: Partial<TargetWrite>) => {
    setTargets(targets.map((t, i) => (i === index ? { ...t, ...change } : t)));
    setState((s) => ({ ...s, saved: false }));
  };

  function addPreset(key: string) {
    const role = industry?.roles.find((r) => r.key === key);
    if (!role || !industry) return;
    setTargets([...targets, { label: role.label, titles: role.titles, exclude: role.exclude, search: role.search, preset_role: `${industry.key}/${role.key}` }]);
    setOpen(null);
  }

  async function save() {
    const incomplete = targets.findIndex((t) => !t.label.trim() || !t.titles.length);
    if (incomplete !== -1) {
      setOpen(incomplete);
      return setState({ saving: false, saved: false, error: "Each role needs a name and at least one job title." });
    }
    setState({ saving: true, saved: false, error: null });
    try {
      const saved = await api<Target[]>("/me/targets", { method: "PUT", body: JSON.stringify(targets) });
      setTargets(saved.map(toWrite));
      setState({ saving: false, saved: true, error: null });
      router.refresh();
    } catch (error) {
      setState({ saving: false, saved: false, error: error instanceof Error ? error.message : "Couldn't save." });
    }
  }

  return (
    <Card title="Target roles" subtitle="A job counts as one of these when its title contains one of the role’s titles.">
      <div className="flex flex-col gap-2">
        {targets.length === 0 && <p className="text-sm text-ink-secondary">No roles yet. Add one below.</p>}
        {targets.map((target, index) => (
          <div key={index} className="rounded-lg border border-edge">
            <div className="flex items-center gap-2 px-3 py-2">
              <button
                type="button"
                onClick={() => setOpen(open === index ? null : index)}
                aria-expanded={open === index}
                className="flex min-w-0 flex-1 items-center gap-2 text-left"
              >
                <span aria-hidden className={`text-ink-muted transition-transform ${open === index ? "rotate-90" : ""}`}>
                  ›
                </span>
                <span className="truncate text-[15px] font-medium">{target.label || "New role"}</span>
                <span className="shrink-0 text-xs text-ink-muted">
                  {target.titles.length} {target.titles.length === 1 ? "title" : "titles"}
                </span>
              </button>
              <button
                type="button"
                onClick={() => {
                  setTargets(targets.filter((_, i) => i !== index));
                  setOpen(null);
                }}
                className="rounded-md px-2 py-1 text-sm text-ink-muted hover:bg-ink/[0.05] hover:text-ink"
              >
                Remove
              </button>
            </div>
            {open === index && (
              <div className="flex flex-col gap-4 border-t border-hairline p-3">
                <div>
                  <label htmlFor={`target-${index}-label`} className="text-sm font-medium text-ink-secondary">
                    Role name
                  </label>
                  <input
                    id={`target-${index}-label`}
                    value={target.label}
                    onChange={(event) => update(index, { label: event.target.value })}
                    maxLength={80}
                    className={`mt-1 ${INPUT}`}
                  />
                </div>
                <TagInput label="Job titles that count" values={target.titles} onChange={(titles) => update(index, { titles })} max={20} />
                <TagInput
                  label="Unless the title contains"
                  values={target.exclude}
                  onChange={(exclude) => update(index, { exclude })}
                  max={20}
                  hint="Optional, e.g. “student” or “assistant”."
                />
                <TagInput label="Search for" values={target.search} onChange={(search) => update(index, { search })} max={10} hint="What job search will type into job boards." />
              </div>
            )}
          </div>
        ))}
      </div>

      {targets.length < MAX && (
        <div className="mt-3 flex flex-wrap gap-2">
          {unused.length > 0 && (
            <select aria-label="Add a role from your industry" value="" onChange={(event) => addPreset(event.target.value)} className={`${INPUT} w-auto max-w-full`}>
              <option value="">Add a role from {industry?.label}...</option>
              {unused.map((role) => (
                <option key={role.key} value={role.key}>
                  {role.label}
                </option>
              ))}
            </select>
          )}
          <button
            type="button"
            onClick={() => {
              setTargets([...targets, { label: "", titles: [], exclude: [], search: [], preset_role: "" }]);
              setOpen(targets.length);
            }}
            className="h-10 rounded-lg border border-edge px-3 text-sm hover:bg-ink/[0.04]"
          >
            Add your own
          </button>
        </div>
      )}

      {state.error && (
        <div className="mt-3">
          <ErrorBanner message={state.error} />
        </div>
      )}
      <div className="mt-4 flex items-center gap-3">
        <button
          type="button"
          onClick={save}
          disabled={state.saving}
          className="h-10 rounded-xl bg-foreground px-5 text-sm font-medium text-background hover:opacity-90 disabled:opacity-50"
        >
          {state.saving ? "Saving..." : "Save roles"}
        </button>
        <p role="status" className="text-sm text-ink-secondary">
          {state.saved && "Saved."}
        </p>
      </div>
    </Card>
  );
}
