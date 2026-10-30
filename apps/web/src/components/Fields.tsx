// Form controls shared by onboarding and settings. Plain controlled inputs;
// every one has a visible label.
"use client";

import { useId, useState, type ReactNode } from "react";
import { addTags, remaining, removeAt } from "@/lib/tags";
import type { Option } from "@/lib/types";

export const INPUT =
  "h-10 w-full rounded-lg border border-edge bg-surface px-3 text-[15px] text-ink placeholder:text-ink-muted focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-foreground";
const LABEL = "text-sm font-medium text-ink-secondary";
const HINT = "mt-1 text-xs text-ink-muted";

function Hint({ children }: { children?: ReactNode }) {
  return children ? <p className={HINT}>{children}</p> : null;
}

export function TextField({
  label,
  value,
  onChange,
  hint,
  placeholder,
  maxLength = 255,
  inputMode,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  hint?: ReactNode;
  placeholder?: string;
  maxLength?: number;
  inputMode?: "numeric" | "text";
}) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className={LABEL}>
        {label}
      </label>
      <input
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        maxLength={maxLength}
        inputMode={inputMode}
        className={`mt-1 ${INPUT}`}
      />
      <Hint>{hint}</Hint>
    </div>
  );
}

export function TextArea({
  label,
  value,
  onChange,
  hint,
  placeholder,
  maxLength = 4000,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  hint?: ReactNode;
  placeholder?: string;
  maxLength?: number;
}) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className={LABEL}>
        {label}
      </label>
      <textarea
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        maxLength={maxLength}
        rows={4}
        className={`mt-1 ${INPUT} h-auto py-2 leading-relaxed`}
      />
      <Hint>{hint}</Hint>
    </div>
  );
}

export function SelectField({
  label,
  value,
  onChange,
  options,
  empty,
  hint,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: Option[];
  empty?: string;
  hint?: ReactNode;
}) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className={LABEL}>
        {label}
      </label>
      <select id={id} value={value} onChange={(event) => onChange(event.target.value)} className={`mt-1 ${INPUT}`}>
        {empty !== undefined && <option value="">{empty}</option>}
        {options.map((option) => (
          <option key={option.key} value={option.key}>
            {option.label}
          </option>
        ))}
      </select>
      <Hint>{hint}</Hint>
    </div>
  );
}

/** Several of a few options, as toggle buttons. Values stay in the options' order. */
export function PillGroup({
  label,
  options,
  values,
  onChange,
  hint,
}: {
  label: string;
  options: Option[];
  values: string[];
  onChange: (values: string[]) => void;
  hint?: ReactNode;
}) {
  const toggle = (key: string) =>
    onChange(options.map((o) => o.key).filter((k) => (k === key ? !values.includes(k) : values.includes(k))));
  return (
    <fieldset>
      <legend className={LABEL}>{label}</legend>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {options.map((option) => {
          const on = values.includes(option.key);
          return (
            <button
              key={option.key}
              type="button"
              aria-pressed={on}
              onClick={() => toggle(option.key)}
              className={`rounded-full border px-3 py-1.5 text-sm transition-colors focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-foreground ${
                on ? "border-foreground bg-foreground text-background" : "border-edge bg-surface text-ink hover:bg-ink/[0.04]"
              }`}
            >
              {option.label}
            </button>
          );
        })}
      </div>
      <Hint>{hint}</Hint>
    </fieldset>
  );
}

function Chip({ text, onRemove }: { text: string; onRemove: () => void }) {
  return (
    <span className="inline-flex max-w-full items-center gap-1 rounded-md bg-ink/[0.07] py-0.5 pr-1 pl-2 text-sm">
      <span className="truncate">{text}</span>
      <button
        type="button"
        onClick={onRemove}
        aria-label={`Remove ${text}`}
        className="grid size-5 shrink-0 place-items-center rounded text-ink-muted hover:bg-ink/[0.08] hover:text-ink"
      >
        ×
      </button>
    </span>
  );
}

/** A list typed one entry at a time (Enter, or a comma with `split`), with optional suggestions to click. */
export function TagInput({
  label,
  values,
  onChange,
  suggestions = [],
  placeholder,
  hint,
  max = 50,
  split = true,
  showSuggestions = 12,
}: {
  label: string;
  values: string[];
  onChange: (values: string[]) => void;
  suggestions?: string[];
  placeholder?: string;
  hint?: ReactNode;
  max?: number;
  split?: boolean;
  showSuggestions?: number;
}) {
  const id = useId();
  const [text, setText] = useState("");
  const add = (typed: string) => {
    onChange(addTags(values, typed, { split, max }));
    setText("");
  };
  const left = remaining(suggestions, values).slice(0, showSuggestions);
  return (
    <div>
      <label htmlFor={id} className={LABEL}>
        {label}
      </label>
      <div className="mt-1 flex min-h-10 flex-wrap items-center gap-1.5 rounded-lg border border-edge bg-surface px-2 py-1.5 focus-within:outline-2 focus-within:outline-offset-1 focus-within:outline-foreground">
        {values.map((value, index) => (
          <Chip key={value} text={value} onRemove={() => onChange(removeAt(values, index))} />
        ))}
        <input
          id={id}
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || (split && event.key === ",")) {
              event.preventDefault();
              add(text);
            } else if (event.key === "Backspace" && !text && values.length) {
              onChange(values.slice(0, -1));
            }
          }}
          onBlur={() => text.trim() && add(text)}
          placeholder={values.length ? "" : placeholder}
          disabled={values.length >= max}
          className="h-7 min-w-36 flex-1 bg-transparent px-1 text-[15px] outline-none placeholder:text-ink-muted"
        />
      </div>
      <Hint>{hint ?? (split ? "Press Enter or type a comma after each one." : "Press Enter after each one.")}</Hint>
      {left.length > 0 && values.length < max && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-ink-muted">Suggestions</span>
          {left.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => onChange(addTags(values, suggestion, { split: false, max }))}
              className="rounded-md border border-dashed border-edge px-2 py-0.5 text-sm text-ink-secondary hover:border-solid hover:bg-ink/[0.04] hover:text-ink"
            >
              + {suggestion}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/** Several of many options (countries): chosen ones as chips, a menu to add more. */
export function MultiSelect({
  label,
  options,
  values,
  onChange,
  first = [],
  addLabel,
  hint,
}: {
  label: string;
  options: Option[];
  values: string[];
  onChange: (values: string[]) => void;
  first?: string[]; // keys listed at the top of the menu
  addLabel: string;
  hint?: ReactNode;
}) {
  const id = useId();
  const byKey = new Map(options.map((option) => [option.key, option]));
  const left = options.filter((option) => !values.includes(option.key));
  const top = left.filter((option) => first.includes(option.key));
  const rest = left.filter((option) => !first.includes(option.key));
  return (
    <div>
      <label htmlFor={id} className={LABEL}>
        {label}
      </label>
      {values.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {values.map((key, index) => (
            <Chip key={key} text={byKey.get(key)?.label ?? key} onRemove={() => onChange(removeAt(values, index))} />
          ))}
        </div>
      )}
      <select
        id={id}
        value=""
        onChange={(event) => event.target.value && onChange([...values, event.target.value])}
        className={`mt-1.5 ${INPUT}`}
      >
        <option value="">{addLabel}</option>
        {top.length > 0 && (
          <optgroup label="In this market">
            {top.map((option) => (
              <option key={option.key} value={option.key}>
                {option.label}
              </option>
            ))}
          </optgroup>
        )}
        <optgroup label={top.length ? "Other countries" : "Countries"}>
          {rest.map((option) => (
            <option key={option.key} value={option.key}>
              {option.label}
            </option>
          ))}
        </optgroup>
      </select>
      <Hint>{hint}</Hint>
    </div>
  );
}

export function Checkbox({
  label,
  checked,
  onChange,
  hint,
}: {
  label: ReactNode;
  checked: boolean;
  onChange: (checked: boolean) => void;
  hint?: ReactNode;
}) {
  const id = useId();
  return (
    <div className="flex gap-2.5">
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-0.5 size-4 shrink-0 accent-foreground"
      />
      <div>
        <label htmlFor={id} className="text-[15px]">
          {label}
        </label>
        <Hint>{hint}</Hint>
      </div>
    </div>
  );
}
