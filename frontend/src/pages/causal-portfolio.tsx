import { useState } from "react";
import { AlertTriangle, CheckCircle2, GitCompareArrows, ShieldCheck } from "lucide-react";

import { useCausalPortfolio } from "@/hooks/use-causal-portfolio";

function signed(value: number) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}`;
}

function pct(value: number) {
  return `${value.toFixed(1)}%`;
}

export default function CausalPortfolioPage() {
  const [stage, setStage] = useState("business");
  const [eventType, setEventType] = useState("converted");
  const [horizonHours, setHorizonHours] = useState(168);
  const [budget, setBudget] = useState(1000);
  const { data, isLoading, error } = useCausalPortfolio({
    stage,
    event_type: eventType,
    horizon_hours: horizonHours,
    action_budget: budget,
    platform: "telegram",
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">Causal Portfolio</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">
          Allocate the same action budget across Opportunities using randomized incremental yield. Replicated contextual evidence can change allocation; exploratory subgroup effects cannot.
        </p>
      </div>

      <section className="grid gap-3 rounded-xl border border-black/5 bg-white p-4 shadow-sm md:grid-cols-4">
        <label className="space-y-1 text-xs font-medium text-muted">Stage<select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={stage} onChange={(event) => setStage(event.target.value)}><option value="business">Business</option><option value="engagement">Engagement</option></select></label>
        <label className="space-y-1 text-xs font-medium text-muted">Outcome<input className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm" value={eventType} onChange={(event) => setEventType(event.target.value)} /></label>
        <label className="space-y-1 text-xs font-medium text-muted">Horizon<select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={horizonHours} onChange={(event) => setHorizonHours(Number(event.target.value))}><option value={24}>24h</option><option value={72}>3d</option><option value={168}>7d</option><option value={336}>14d</option><option value={720}>30d</option></select></label>
        <label className="space-y-1 text-xs font-medium text-muted">Common action budget<input type="number" min={1} max={50000} className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm" value={budget} onChange={(event) => setBudget(Math.max(1, Number(event.target.value) || 1))} /></label>
      </section>

      {isLoading ? (
        <div className="rounded-xl border border-black/5 bg-white p-6 text-sm text-muted">Mapping current Opportunities to randomized causal contexts…</div>
      ) : error || !data ? (
        <div className="rounded-xl border border-amber-100 bg-amber-50 p-5 text-sm text-amber-800">Causal allocation cannot be calculated yet.</div>
      ) : (
        <>
          {data.recommendation_segment_id ? (
            <section className="rounded-xl border border-emerald-200 bg-emerald-50 p-5">
              <div className="flex items-start gap-3"><CheckCircle2 className="mt-0.5 h-5 w-5 text-emerald-700" /><div><p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Decision-grade causal allocation</p><h2 className="mt-1 text-xl font-semibold text-ink">{data.recommendation_name}</h2><p className="mt-1 text-xs text-muted">Selected only when ≥70% of evaluated units map to replicated contextual randomized evidence and the conservative incremental outcome bound remains positive.</p></div></div>
            </section>
          ) : (
            <section className="rounded-xl border border-amber-200 bg-amber-50 p-5">
              <div className="flex items-start gap-3"><AlertTriangle className="mt-0.5 h-5 w-5 text-amber-700" /><div><h2 className="text-sm font-semibold text-ink">No decision-grade causal winner yet</h2><p className="mt-1 text-xs text-muted">Keep observational Portfolio as a labeled fallback, but do not claim causal allocation until randomized contextual coverage matures.</p></div></div>
            </section>
          )}

          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><GitCompareArrows className="h-4 w-4" /> Global causal prior</div><p className="mt-3 text-2xl font-semibold text-ink">{data.global_prior_lift_percentage_points >= 0 ? "+" : ""}{data.global_prior_lift_percentage_points.toFixed(2)} pp</p><p className="text-xs text-muted">{data.global_prior_status.replace(/_/g, " ")} · I² {data.global_prior_i_squared_percent.toFixed(1)}%</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><ShieldCheck className="h-4 w-4" /> Ready Opportunities</div><p className="mt-3 text-2xl font-semibold text-ink">{data.rows.filter((row) => row.evidence_status === "ready").length}</p><p className="text-xs text-muted">of {data.rows.length} compared</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="text-xs uppercase tracking-wide text-muted">Ranking basis</div><p className="mt-3 text-sm font-semibold text-ink">Conservative contextual incremental outcomes</p><p className="mt-1 text-xs text-muted">same action budget across rows</p></div>
          </div>

          <section className="overflow-hidden rounded-xl border border-black/5 bg-white shadow-sm">
            <div className="border-b border-black/5 p-4"><h2 className="text-sm font-semibold text-ink">Causal allocation candidates</h2><p className="mt-1 text-xs text-muted">Exploratory contextual rows fall back to the global randomized prior until replicated.</p></div>
            <div className="overflow-auto"><table className="w-full min-w-[1180px] text-left text-sm"><thead className="bg-stone-50 text-xs text-muted"><tr><th className="px-3 py-2">#</th><th className="px-3 py-2">Opportunity</th><th className="px-3 py-2">Evaluated</th><th className="px-3 py-2">Conservative incremental</th><th className="px-3 py-2">Expected incremental</th><th className="px-3 py-2">Upside</th><th className="px-3 py-2">Conservative rate</th><th className="px-3 py-2">Replicated context</th><th className="px-3 py-2">Exploratory context</th><th className="px-3 py-2">Global fallback</th><th className="px-3 py-2">Evidence</th></tr></thead><tbody>{data.rows.map((row) => <tr key={row.segment_id} className="border-t border-black/5"><td className="px-3 py-2 font-semibold text-muted">{row.rank}</td><td className="px-3 py-2"><p className="font-medium text-ink">{row.segment_name}</p><p className="text-[10px] text-muted">{row.matched_count.toLocaleString()} materialized</p></td><td className="px-3 py-2">{row.evaluated_members.toLocaleString()}</td><td className="px-3 py-2 font-semibold text-ink">{signed(row.conservative_incremental_outcomes)}</td><td className="px-3 py-2">{signed(row.expected_incremental_outcomes)}</td><td className="px-3 py-2 text-muted">{signed(row.upside_incremental_outcomes)}</td><td className="px-3 py-2">{row.conservative_incremental_rate >= 0 ? "+" : ""}{row.conservative_incremental_rate.toFixed(2)}%</td><td className="px-3 py-2">{pct(row.replicated_context_coverage)}</td><td className="px-3 py-2">{pct(row.exploratory_context_coverage)}</td><td className="px-3 py-2">{pct(row.global_fallback_coverage)}</td><td className="px-3 py-2"><span className={`rounded-full px-2 py-1 text-[10px] ${row.evidence_status === "ready" ? "bg-emerald-50 text-emerald-700" : row.evidence_status === "limited" ? "bg-amber-50 text-amber-700" : "bg-stone-100 text-muted"}`}>{row.evidence_status}</span></td></tr>)}</tbody></table></div>
          </section>

          <div className="flex items-start gap-2 rounded-lg bg-stone-50 p-3 text-xs text-muted"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><span>{data.warnings.map((warning) => warning.replace(/_/g, " ")).join(" · ")}. This screen ranks alternative uses of the same capacity; overlapping Opportunities are not yet jointly optimized.</span></div>
        </>
      )}
    </div>
  );
}
