"use client";

import { useEffect, useState, type ReactNode } from "react";
import Card from "@/components/Card";
import { ErrorBanner } from "@/components/Feedback";
import { TagInput, TextArea, TextField } from "@/components/Fields";
import { api, ApiError } from "@/lib/api";
import { describeDocument, emptyEducation, emptyExperience, forSaving, linesToBullets, MAX_BULLETS, moveItem, sameCv } from "@/lib/cv";
import { since } from "@/lib/jobs";
import type { Cv, CvContent, CvDocument, Education, Experience, Presets } from "@/lib/types";
import { Languages } from "../settings/ProfileForm";

const POLL_MS = 1500;

function Section({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <fieldset className="flex flex-col gap-4 border-t border-hairline pt-5 first:border-t-0 first:pt-0">
      <legend className="float-left mb-1 w-full">
        <span className="text-[15px] font-semibold">{title}</span>
        {hint && <span className="mt-0.5 block text-sm text-ink-secondary">{hint}</span>}
      </legend>
      {children}
    </fieldset>
  );
}

function EntryTools({ label, index, count, onMove, onRemove }: { label: string; index: number; count: number; onMove: (by: -1 | 1) => void; onRemove: () => void }) {
  const tool = "h-8 rounded-lg px-2.5 text-sm text-ink-secondary hover:bg-ink/[0.05] hover:text-ink disabled:opacity-40";
  return (
    <div className="flex items-center justify-between gap-2">
      <p className="text-sm font-medium text-ink-secondary">{label}</p>
      <div className="flex gap-1">
        <button type="button" onClick={() => onMove(-1)} disabled={index === 0} aria-label={`Move ${label} up`} className={tool}>
          ↑
        </button>
        <button type="button" onClick={() => onMove(1)} disabled={index === count - 1} aria-label={`Move ${label} down`} className={tool}>
          ↓
        </button>
        <button type="button" onClick={onRemove} className={tool}>
          Remove
        </button>
      </div>
    </div>
  );
}

function Dates({ start, end, onChange }: { start: string; end: string; onChange: (change: { start?: string; end?: string }) => void }) {
  return (
    <div className="grid grid-cols-2 gap-3">
      <TextField label="From" value={start} onChange={(value) => onChange({ start: value })} placeholder="e.g. Mar 2022" maxLength={30} />
      <TextField label="To" value={end} onChange={(value) => onChange({ end: value })} placeholder="Empty for present" maxLength={30} />
    </div>
  );
}

function ExperienceEntry({ job, index, count, onChange, onMove, onRemove }: {
  job: Experience; index: number; count: number; onChange: (job: Experience) => void; onMove: (by: -1 | 1) => void; onRemove: () => void;
}) {
  // The bullets box keeps what's typed (blank lines too) until it's saved.
  const [bullets, setBullets] = useState(job.bullets.join("\n"));
  const set = (change: Partial<Experience>) => onChange({ ...job, ...change });
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-edge p-4">
      <EntryTools label={job.title || `Job ${index + 1}`} index={index} count={count} onMove={onMove} onRemove={onRemove} />
      <div className="grid gap-3 sm:grid-cols-2">
        <TextField label="Job title" value={job.title} onChange={(title) => set({ title })} maxLength={120} />
        <TextField label="Employer" value={job.employer} onChange={(employer) => set({ employer })} maxLength={120} />
      </div>
      <div className="grid gap-3 sm:grid-cols-[1fr_2fr]">
        <TextField label="Place" value={job.location} onChange={(location) => set({ location })} maxLength={80} />
        <Dates start={job.start} end={job.end} onChange={set} />
      </div>
      <TextArea
        label="What you did"
        value={bullets}
        onChange={(text) => {
          setBullets(text);
          set({ bullets: linesToBullets(text) });
        }}
        hint={`One achievement per line, up to ${MAX_BULLETS}. Numbers help: “Cut waiting times by 20%”.`}
        maxLength={MAX_BULLETS * 300}
      />
    </div>
  );
}

function EducationEntry({ school, index, count, onChange, onMove, onRemove }: {
  school: Education; index: number; count: number; onChange: (school: Education) => void; onMove: (by: -1 | 1) => void; onRemove: () => void;
}) {
  const set = (change: Partial<Education>) => onChange({ ...school, ...change });
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-edge p-4">
      <EntryTools label={school.qualification || `Qualification ${index + 1}`} index={index} count={count} onMove={onMove} onRemove={onRemove} />
      <div className="grid gap-3 sm:grid-cols-2">
        <TextField label="Qualification" value={school.qualification} onChange={(qualification) => set({ qualification })} placeholder="e.g. BSc Adult Nursing" maxLength={160} />
        <TextField label="Where you studied" value={school.institution} onChange={(institution) => set({ institution })} maxLength={120} />
      </div>
      <div className="grid gap-3 sm:grid-cols-[1fr_2fr]">
        <TextField label="Place" value={school.location} onChange={(location) => set({ location })} maxLength={80} />
        <Dates start={school.start} end={school.end} onChange={set} />
      </div>
      <TextField label="Details (optional)" value={school.details} onChange={(details) => set({ details })} placeholder="e.g. First-class honours" maxLength={300} />
    </div>
  );
}

function DocumentRow({ doc, onDelete }: { doc: CvDocument; onDelete: () => void }) {
  return (
    <li className="flex items-start justify-between gap-3 py-3 first:pt-0 last:pb-0">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">{doc.filename}</p>
        <p className={`text-sm ${doc.status === "failed" ? "text-red-700 dark:text-red-400" : "text-ink-secondary"}`}>{describeDocument(doc)}</p>
        <p className="text-xs text-ink-muted" suppressHydrationWarning>
          Made {since(doc.finished_at ?? doc.requested_at)}
        </p>
      </div>
      <div className="flex shrink-0 gap-1.5">
        {doc.status === "done" && (
          <a href={`/api/backend/documents/${doc.id}/file`} download={doc.filename} className="h-8 rounded-lg border border-edge px-3 text-sm leading-8 hover:bg-ink/[0.04]">
            Download
          </a>
        )}
        {doc.status !== "queued" && (
          <button type="button" onClick={onDelete} aria-label={`Delete ${doc.filename}`} className="h-8 rounded-lg px-2.5 text-sm text-ink-secondary hover:bg-ink/[0.05] hover:text-ink">
            Delete
          </button>
        )}
      </div>
    </li>
  );
}

export default function CvEditor({ initial, levels }: { initial: Cv; levels: Presets["language_levels"] }) {
  const [draft, setDraft] = useState<CvContent>(initial.content);
  const [savedContent, setSavedContent] = useState<CvContent>(initial.content);
  const [saved, setSaved] = useState(initial.saved);
  const [documents, setDocuments] = useState<CvDocument[]>(initial.documents);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const changed = !saved || !sameCv(draft, savedContent);
  const building = documents.some((d) => d.status === "queued");
  const set = (change: Partial<CvContent>) => setDraft((cv) => ({ ...cv, ...change }));

  // A PDF is made in the background: check back until it's done.
  useEffect(() => {
    if (!building) return;
    const timer = setInterval(async () => {
      try {
        setDocuments((await api<Cv>("/cv")).documents);
      } catch {
        // try again next tick
      }
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [building]);

  async function save(): Promise<boolean> {
    setError(null);
    try {
      const result = await api<Cv>("/cv", { method: "PUT", body: JSON.stringify(forSaving(draft)) });
      setSavedContent(result.content);
      setSaved(true);
      return true;
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Couldn't save your CV.");
      return false;
    }
  }

  async function onSave() {
    setBusy(true);
    setNote(null);
    if (await save()) setNote("Saved.");
    setBusy(false);
  }

  async function makePdf() {
    setBusy(true);
    setNote(null);
    try {
      if (changed && !(await save())) return;
      const doc = await api<CvDocument>("/cv/pdf", { method: "POST" });
      setDocuments((all) => [doc, ...all]);
    } catch (failure) {
      const message = failure instanceof ApiError && failure.status === 409 ? "A PDF is already being made." : failure instanceof Error ? failure.message : "Couldn't start the PDF.";
      setError(message);
    } finally {
      setBusy(false);
    }
  }

  async function remove(doc: CvDocument) {
    setError(null);
    try {
      await api(`/documents/${doc.id}`, { method: "DELETE" });
      setDocuments((all) => all.filter((d) => d.id !== doc.id));
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Couldn't delete that PDF.");
    }
  }

  const button = "h-10 rounded-xl px-5 text-sm font-medium disabled:opacity-50";
  return (
    <div className="grid items-start gap-6 lg:grid-cols-[3fr_2fr]">
      <Card title="Your CV" subtitle={saved ? "Saved. Changes here don't touch your profile." : "Started from your profile - save it to keep it."}>
        <div className="flex flex-col gap-6">
          <Section title="About you">
            <div className="grid gap-3 sm:grid-cols-2">
              <TextField label="Name" value={draft.name} onChange={(name) => set({ name })} maxLength={120} />
              <TextField label="Headline" value={draft.headline} onChange={(headline) => set({ headline })} placeholder="e.g. Registered nurse" maxLength={160} />
              <TextField label="Email" value={draft.email} onChange={(email) => set({ email })} maxLength={200} />
              <TextField label="Phone" value={draft.phone} onChange={(phone) => set({ phone })} maxLength={40} />
              <TextField label="Where you live" value={draft.location} onChange={(location) => set({ location })} placeholder="e.g. Manchester, UK" maxLength={80} />
            </div>
            <TagInput label="Links" values={draft.links} onChange={(links) => set({ links })} max={4} split={false} placeholder="https://..." hint="Up to four: LinkedIn, a portfolio, a professional page." />
          </Section>
          <Section title="Profile" hint="Two or three sentences at the top of your CV.">
            <TextArea label="Summary" value={draft.summary} onChange={(summary) => set({ summary })} maxLength={1200} />
          </Section>
          <Section title="Experience" hint="Most recent first.">
            {draft.experience.map((job, index) => (
              <ExperienceEntry
                key={index}
                job={job}
                index={index}
                count={draft.experience.length}
                onChange={(next) => set({ experience: draft.experience.map((j, i) => (i === index ? next : j)) })}
                onMove={(by) => set({ experience: moveItem(draft.experience, index, by) })}
                onRemove={() => set({ experience: draft.experience.filter((_, i) => i !== index) })}
              />
            ))}
            {draft.experience.length < 15 && (
              <button type="button" onClick={() => set({ experience: [...draft.experience, emptyExperience()] })} className="self-start rounded-lg border border-edge px-3 py-1.5 text-sm hover:bg-ink/[0.04]">
                + Add a job
              </button>
            )}
          </Section>
          <Section title="Education">
            {draft.education.map((school, index) => (
              <EducationEntry
                key={index}
                school={school}
                index={index}
                count={draft.education.length}
                onChange={(next) => set({ education: draft.education.map((s, i) => (i === index ? next : s)) })}
                onMove={(by) => set({ education: moveItem(draft.education, index, by) })}
                onRemove={() => set({ education: draft.education.filter((_, i) => i !== index) })}
              />
            ))}
            {draft.education.length < 8 && (
              <button type="button" onClick={() => set({ education: [...draft.education, emptyEducation()] })} className="self-start rounded-lg border border-edge px-3 py-1.5 text-sm hover:bg-ink/[0.04]">
                + Add a qualification
              </button>
            )}
          </Section>
          <Section title="Skills and languages">
            <TagInput label="Skills" values={draft.skills} onChange={(skills) => set({ skills })} max={40} />
            <Languages values={draft.languages} onChange={(languages) => set({ languages })} levels={levels} />
          </Section>
          {error && <ErrorBanner message={error} />}
          <div className="flex flex-wrap items-center gap-2 border-t border-hairline pt-4">
            <button type="button" onClick={onSave} disabled={busy || !changed} className={`${button} bg-foreground text-background hover:opacity-90`}>
              Save
            </button>
            {note && <p className="text-sm text-ink-secondary">{note}</p>}
            {changed && saved && <p className="text-sm text-ink-muted">Unsaved changes</p>}
          </div>
        </div>
      </Card>
      <Card
        title="PDF"
        subtitle="A clean one- or two-page CV, made from what's saved here."
        className="order-first lg:sticky lg:top-20 lg:order-none"
        action={
          <button type="button" onClick={makePdf} disabled={busy || building} className={`${button} shrink-0 bg-foreground text-background hover:opacity-90`}>
            {building ? "Making..." : changed ? "Save and make PDF" : "Make PDF"}
          </button>
        }
      >
        {documents.length === 0 ? (
          <p className="text-sm text-ink-secondary">No PDFs yet. The newest ten are kept.</p>
        ) : (
          <ul className="flex flex-col divide-y divide-hairline">
            {documents.map((doc) => (
              <DocumentRow key={doc.id} doc={doc} onDelete={() => remove(doc)} />
            ))}
          </ul>
        )}
        <p className="mt-4 text-xs text-ink-muted">
          Latin, Greek and Cyrillic text prints as typed; Chinese, Japanese, Korean and right-to-left scripts aren&apos;t supported yet.
        </p>
      </Card>
    </div>
  );
}
