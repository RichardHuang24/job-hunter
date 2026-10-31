import type { ScoreBrief } from "@/lib/types";

/** A job's fit score at a glance: the number, or that it's on its way. */
export default function FitBadge({ score, size = "md" }: { score: ScoreBrief | null; size?: "sm" | "md" }) {
  const box = size === "sm" ? "h-7 min-w-9 text-sm" : "h-10 min-w-11 text-[15px]";
  if (!score) return <span aria-hidden className={`${box} inline-grid shrink-0 place-items-center rounded-lg border border-dashed border-edge text-ink-muted`}>–</span>;
  if (score.status === "queued")
    return (
      <span className={`${box} inline-grid shrink-0 place-items-center rounded-lg border border-edge`} title="Scoring">
        <span aria-hidden className="size-3.5 animate-spin rounded-full border-2 border-ink/20 border-t-ink/70" />
        <span className="sr-only">Scoring</span>
      </span>
    );
  if (score.status === "failed" || score.overall === null)
    return <span className={`${box} inline-grid shrink-0 place-items-center rounded-lg border border-edge text-ink-muted`} title="Couldn't score">!</span>;
  const strong = score.overall >= 75;
  const good = score.overall >= 60;
  const tone = strong ? "bg-foreground text-background border-foreground" : good ? "bg-ink/[0.08] text-ink border-transparent" : "bg-transparent text-ink-secondary border-edge";
  return (
    <span
      className={`${box} inline-grid shrink-0 place-items-center rounded-lg border font-semibold tabular-nums ${tone} ${score.simulated ? "border-dashed" : ""} ${score.stale ? "opacity-60" : ""}`}
      title={`${score.band}${score.simulated ? " (simulated)" : ""}${score.stale ? " - out of date" : ""}`}
    >
      {score.overall}
      <span className="sr-only">
        {" "}
        out of 100, {score.band}
        {score.simulated ? ", simulated" : ""}
        {score.stale ? ", out of date" : ""}
      </span>
    </span>
  );
}
