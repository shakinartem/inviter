import { useState } from "react";
import { AlertTriangle, CheckCircle2, Layers3, ShieldCheck } from "lucide-react";

import { useOpportunityPortfolio } from "@/hooks/use-opportunity-portfolio";

function number(value: number) {
  return value.toFixed(1);
}

function pct(value: number) {
  return `${value.toFixed(1)}%`;
}

export default function OpportunityPortfolioPage() {
  const [stage, setStage] = useState("business");
  const [eventType, setEventType] = useState("converted");
  const [horizonHours, setHorizonHours] = useState(168);
  const [budget, setBudget] = useState(1000);
  const [platform, setPlatform] = useState("telegram");

  const { data, isLoading, error } = useOpportunityPortfolio({
    stage,
    event_type: eventType,
    horizon_hours: horizonHours,
    action_budget: budget,
    platform,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">Opportunity Portfolio</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">
          Compare materialized Opportunities under the same action budget. Ranking uses a quality-adjusted conservative outcome bound, not the most optimistic mean.
        </p>
      </div>

      <section className="grid gap-3 rounded-xl border border-black/5 bg-white p-4 shadow-sm md:grid-cols-5">
        <label className="space-y-1 text-xs font-medium text-muted">Platform<select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={platform} onChange={(event) => setPlatform(event.target.value)}><option value="telegram">Telegram</option><option value="discord">Discord</option></select></label>
        <label className="space-y-1 text-xs font-medium text-muted">Stage<select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={stage} onChange={(event) => setStage(event.target.value)}><option value="business">Business</option><option value="engagement">Engagement</option></select></label>
        <label className="space-y-1 text-xs font-medium text-muted">Event<input className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm" value={eventType} onChange={(event) => setEventType(event.target.value)} /></label>
        <label className="space-y-1 text-xs font-medium text-muted">Horizon<select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={horizonHours} onChange={(event) => setHorizonHours(Number(event.target.value))}><option value={24}>24 hours</option><option value={72}>3 days</option><option value={168}>7 days</option><option value={336}>14 days</option><option value={720}>30 days</option></select></label>
        <label className="space-y-1 text-xs font-medium text-muted">Common action budget<input type="number" min={1} max={50000} className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm" value={budget} onChange={(event) => setBudget(Math.max(1, Number(event.target.value) || 1))} /></label>
      </section>

      {isLoading ? (
        <div className="rounded-xl border border-black/5 bg-white p-6 text-sm text-muted">Comparing mature evidence across Opportunities…</div>
      ) : error || !data ? (
        <div className="rounded-xl border border-red-100 bg-red-50 p-5 text-sm text-red-700">Portfolio forecast could not be calculated.</div>
      ) : (
        <>
          {data.recommendation_segment_id ? (
            <section className="rounded-xl border border-emerald-200 bg-emerald-50 p-5">
              <div className="flex items-start gap-3"><CheckCircle2 className="mt-0.5 h-5 w-5 text-emerald-700" /><div><p className="text-xs font-semibold uppercase tracking-wide text-emerald-700">Best supported allocation candidate</p><h2 className="mt-1 text-xl font-semibold text-ink">{data.recommendation_name}</h2><p className="mt-1 text-xs text-muted">Recommendation requires ready evidence quality, positive conservative yield and at least 70% contextual evidence coverage.</p></div></div>
            </section>
          ) : (
            <section className="rounded-xl border border-amber-200 bg-amber-50 p-5">
              <div className="flex items-start gap-3"><AlertTriangle className="mt-0.5 h-5 w-5 text-amber-700" /><div><h2 className="text-sm font-semibold text-ink">No high-confidence winner yet</h2><p className="mt-1 text-xs text-muted">Do not force allocation from a weak ranking. Collect more mature verified outcomes or narrow Opportunities until contextual evidence improves.</p></div></div>
            </section>
          )}

          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><Layers3 className="h-4 w-4" /> Compared Opportunities</div><p className="mt-3 text-2xl font-semibold text-ink">{data.rows.length}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><ShieldCheck className="h-4 w-4" /> Ready evidence</div><p className="mt-3 text-2xl font-semibold text-ink">{data.rows.filter((row) => row.quality_status === "ready").length}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="text-xs uppercase tracking-wide text-muted">Allocation basis</div><p className="mt-3 text-sm font-semibold text-ink">Conservative yield × evidence quality</p></div>
          </div>

          <section className="overflow-hidden rounded-xl border border-black/5 bg-white shadow-sm">
            <div className="border-b border-black/5 p-4"><h2 className="text-sm font-semibold text-ink">Ranked Opportunities</h2><p className="mt-1 text-xs text-muted">All rows use the same requested action budget. Smaller Opportunities are naturally capped by their available members.</p></div>
            <div className="overflow-auto"><table className="w-full min-w-[980px] text-left text-sm"><thead className="bg-stone-50 text-xs text-muted"><tr><th className="px-3 py-2">#</th><th className="px-3 py-2">Opportunity</th><th className="px-3 py-2">Evaluated</th><th className="px-3 py-2">Conservative</th><th className="px-3 py-2">Expected</th><th className="px-3 py-2">Upside</th><th className="px-3 py-2">Conservative rate</th><th className="px-3 py-2">Context coverage</th><th className="px-3 py-2">Frozen history</th><th className="px-3 py-2">Quality</th></tr></thead><tbody>{data.rows.map((row) => <tr key={row.segment_id} className="border-t border-black/5"><td className="px-3 py-2 font-semibold text-muted">{row.rank}</td><td className="px-3 py-2"><p className="font-medium text-ink">{row.segment_name}</p><p className="text-[10px] text-muted">{row.matched_count.toLocaleString()} materialized</p></td><td className="px-3 py-2">{row.evaluated_members.toLocaleString()}</td><td className="px-3 py-2 font-semibold text-ink">{number(row.conservative_outcomes)}</td><td className="px-3 py-2">{number(row.expected_outcomes)}</td><td className="px-3 py-2 text-muted">{number(row.upside_outcomes)}</td><td className="px-3 py-2">{pct(row.conservative_rate)}</td><td className="px-3 py-2">{pct(row.contextual_coverage)}</td><td className="px-3 py-2">{pct(row.frozen_history_ratio)}</td><td className="px-3 py-2"><span className={`rounded-full px-2 py-1 text-[10px] ${row.quality_status === "ready" ? "bg-emerald-50 text-emerald-700" : row.quality_status === "limited" ? "bg-amber-50 text-amber-700" : "bg-stone-100 text-muted"}`}>{row.quality_status}</span></td></tr>)}</tbody></table></div>
            {data.rows.length === 0 && <div className="p-5 text-sm text-muted">No materialized Opportunities match this platform.</div>}
          </section>

          <div className="flex items-start gap-2 rounded-lg bg-stone-50 p-3 text-xs text-muted"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><span>{data.warnings.map((warning) => warning.replace(/_/g, " ")).join(" · ")}. Audience overlap between Opportunities is not deduplicated yet, so this screen ranks alternatives rather than constructing a simultaneous multi-Opportunity allocation.</span></div>
        </>
      )}
    </div>
  );
}
