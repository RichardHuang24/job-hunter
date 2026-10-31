import Card from "@/components/Card";
import type { AiStatus } from "@/lib/types";

/** Who scores jobs, and this month's allowance. */
export default function AiCard({ ai }: { ai: AiStatus }) {
  const share = ai.scores_limit ? Math.min(1, ai.scores_used / ai.scores_limit) : 0;
  return (
    <Card
      title="AI scoring"
      subtitle={ai.provider === "anthropic" ? `Claude (${ai.model}, ${ai.effort} effort)` : "Simulated - no Anthropic API key is set"}
    >
      {ai.provider === "simulated" && (
        <p className="mb-3 text-sm text-ink-secondary">
          Scores are rough placeholders that only count skills and read your deal-breakers. Add an Anthropic API key to get Claude’s
          assessment - see <span className="font-medium text-ink">docs/ai-scoring.md</span>.
        </p>
      )}
      <div className="flex items-baseline justify-between text-sm">
        <span>
          <strong className="font-semibold tabular-nums">{ai.scores_used}</strong> of {ai.scores_limit} scores this month
        </span>
        {ai.queued > 0 && <span className="text-ink-muted">{ai.queued} in progress</span>}
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-hairline" role="progressbar" aria-valuemin={0} aria-valuemax={ai.scores_limit} aria-valuenow={ai.scores_used} aria-label="Scores used this month">
        <div className="h-full rounded-full bg-foreground" style={{ width: `${share * 100}%` }} />
      </div>
      <p className="mt-2 text-xs text-ink-muted">
        ${ai.cost_usd.toFixed(2)} of ${ai.budget_usd.toFixed(2)} spent · {ai.auto_score ? "new matches are scored after each search" : "scores only when you ask"}
      </p>
    </Card>
  );
}
