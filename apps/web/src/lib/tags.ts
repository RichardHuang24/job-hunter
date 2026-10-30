// Lists the user types into one entry at a time (skills, locations, job
// titles). Pure - tested in tags.test.mts.

/**
 * Adds what was typed: one entry, or with `split`, several separated by
 * commas or semicolons. Blanks and repeats (ignoring case) are skipped, and
 * nothing is added past `max`.
 */
export function addTags(values: string[], typed: string, { split = true, max = Infinity } = {}): string[] {
  const out = [...values];
  const seen = new Set(values.map((value) => value.toLocaleLowerCase()));
  for (const part of split ? typed.split(/[,;\n]/) : [typed]) {
    const value = part.replace(/\s+/g, " ").trim();
    if (!value || seen.has(value.toLocaleLowerCase()) || out.length >= max) continue;
    seen.add(value.toLocaleLowerCase());
    out.push(value);
  }
  return out;
}

export function removeAt<T>(values: T[], index: number): T[] {
  return values.filter((_, i) => i !== index);
}

/** The suggestions not chosen yet, ignoring case. */
export function remaining(suggestions: string[], values: string[]): string[] {
  const chosen = new Set(values.map((value) => value.toLocaleLowerCase()));
  return suggestions.filter((suggestion) => !chosen.has(suggestion.toLocaleLowerCase()));
}
