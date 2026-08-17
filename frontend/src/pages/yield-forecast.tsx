import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, BarChart3, ShieldQuestion, Target } from "lucide-react";

import { useSegments } from "@/hooks/use-segments";
import { useYieldForecast } from "@/hooks/use-yield-forecast";

function pct(value: number) {
  return `${value.toFixed(1)}%`;
}

export default function YieldForecastPage() {
  const { data: segments } = useSegments({ active_only: true });
  const active = useMemo(
    () => (segments ?? []).filter((segment) => segment.last_refreshed_at && segment.matched_count > 0),
    [segments],
  );
  const [segmentId, setSegmentId] = useState<string | null>(null);
  const [stage, setStage] = useState("business");
  const [eventType, setEventType] = useState("converted");
  const [horizonHours, setHorizonHours] = useState(168);
  const [budget, setBudget] = useState(1000);

  useEffect(() => {
    if (!segmentId && active.length) setSegmentId(active[0].id);
  }, [active, segmentId]);

  const { data: forecast, isLoading, error } = useYieldForecast(segmentId, {
    stage,
    event_type: eventType,
    horizon_hours: horizonHours,
    budget,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">Expected Yield</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">
          Estimate how many verified downstream outcomes a materialized Opportunity may produce under a fixed action budget.
          This is observational forecasting, not incremental causal lift.
        </p>
      </div>

      <section className="grid gap-3 rounded-xl border border-black/5 bg-white p-4 shadow-sm md:grid-cols-4">
        <label className="space-y-1 text-xs font-medium text-muted">
          Opportunity
          <select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm text-ink" value={segmentId ?? ""} onChange={(event) => setSegmentId(event.target.value || null)}>
            <option value="">Select Opportunity</option>
            {active.map((segment) => <option key={segment.id} value={segment.id}>{segment.name} · {segment.matched_count.toLocaleString()}</option>)}
          </select>
        </label>
        <label className="space-y-1 text-xs font-medium text-muted">
          Outcome
          <div className="flex gap-2"><select className="w-28 rounded-lg border border-black/10 bg-white px-2 py-2 text-sm" value={stage} onChange={(event) => setStage(event.target.value)}><option value="business">Business</option><option value="engagement">Engagement</option></select><input className="min-w-0 flex-1 rounded-lg border border-black/10 px-3 py-2 text-sm" value={eventType} onChange={(event) => setEventType(event.target.value)} placeholder="converted" /></div>
        </label>
        <label className="space-y-1 text-xs font-medium text-muted">
          Observation horizon
          <select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={horizonHours} onChange={(event) => setHorizonHours(Number(event.target.value))}><option value={24}>24 hours</option><option value={72}>3 days</option><option value={168}>7 days</option><option value={336}>14 days</option><option value={720}>30 days</option></select>
        </label>
        <label className="space-y-1 text-xs font-medium text-muted">
          Action budget
          <input type="number" min={1} max={50000} className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm" value={budget} onChange={(event) => setBudget(Math.max(1, Number(event.target.value) || 1))} />
        </label>
      </section>

      {!segmentId ? (
        <div className="rounded-xl border border-dashed border-black/10 bg-white p-6 text-sm text-muted">Materialize an Opportunity first.</div>
      ) : isLoading ? (
        <div className="rounded-xl border border-black/5 bg-white p-6 text-sm text-muted">Building mature historical cohorts…</div>
      ) : error || !forecast ? (
        <div className="rounded-xl border border-red-100 bg-red-50 p-5 text-sm text-red-700">Forecast could not be calculated for this Opportunity.</div>
      ) : (
        <>
          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted"><Target className="h-4 w-4" /> Expected outcomes</div><p className="mt-3 text-2xl font-semibold text-ink">{forecast.expected_outcomes.toFixed(1)}</p><p className="mt-1 text-xs text-muted">{forecast.confidence_low_outcomes.toFixed(1)}–{forecast.confidence_high_outcomes.toFixed(1)} uncertainty range</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted"><BarChart3 className="h-4 w-4" /> Expected rate</div><p className="mt-3 text-2xl font-semibold text-ink">{pct(forecast.expected_rate)}</p><p className="mt-1 text-xs text-muted">historical baseline {pct(forecast.historical_observed_rate)}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted"><ShieldQuestion className="h-4 w-4" /> Evidence quality</div><p className="mt-3 text-2xl font-semibold capitalize text-ink">{forecast.quality_status}</p><p className="mt-1 text-xs text-muted">{forecast.historical_samples.toLocaleString()} mature actions</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="text-xs font-medium uppercase tracking-wide text-muted">True frozen history</div><p className="mt-3 text-2xl font-semibold text-ink">{pct(forecast.frozen_history_ratio)}</p><p className="mt-1 text-xs text-muted">decision snapshots captured from frozen cohorts</p></div>
          </div>

          <section className="rounded-xl border border-black/5 bg-white p-5 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-4"><div><h2 className="text-sm font-semibold text-ink">Evidence coverage</h2><p className="mt-1 max-w-2xl text-xs text-muted">Exact readiness × signal history is preferred; sparse groups shrink toward readiness, signal or owner baseline instead of overfitting.</p></div><p className="text-xs text-muted">Evaluating {forecast.evaluated_members.toLocaleString()} people</p></div>
            <div className="mt-4 grid gap-2 sm:grid-cols-4">{["exact", "readiness", "signal", "global"].map((key) => <div key={key} className="rounded-lg bg-stone-50 p-3"><p className="text-[10px] uppercase tracking-wide text-muted">{key}</p><p className="mt-1 text-xl font-semibold text-ink">{pct(forecast.evidence_coverage[key] ?? 0)}</p></div>)}</div>
            {forecast.warnings.length > 0 && <div className="mt-4 flex items-start gap-2 rounded-lg bg-amber-50 p-3 text-xs text-amber-800"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><span>{forecast.warnings.map((warning) => warning.replace(/_/g, " ")).join(" · ")}</span></div>}
          </section>

          <section className="overflow-hidden rounded-xl border border-black/5 bg-white shadow-sm">
            <div className="border-b border-black/5 p-4"><h2 className="text-sm font-semibold text-ink">Evidence strata</h2><p className="mt-1 text-xs text-muted">Posterior rates are partially pooled toward the owner baseline when history is sparse.</p></div>
            <div className="overflow-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead className="bg-stone-50 text-xs text-muted"><tr><th className="px-3 py-2">Stratum</th><th className="px-3 py-2">Level</th><th className="px-3 py-2">Current</th><th className="px-3 py-2">History</th><th className="px-3 py-2">Observed</th><th className="px-3 py-2">Posterior</th><th className="px-3 py-2">95% approx.</th></tr></thead><tbody>{forecast.evidence_rows.map((row) => <tr key={`${row.evidence_level}:${row.label}`} className="border-t border-black/5"><td className="px-3 py-2 font-medium text-ink">{row.label.replace(/_/g, " ")}</td><td className="px-3 py-2 capitalize text-muted">{row.evidence_level}</td><td className="px-3 py-2">{row.current_members}</td><td className="px-3 py-2">{row.historical_samples}</td><td className="px-3 py-2">{pct(row.observed_rate)}</td><td className="px-3 py-2 font-semibold">{pct(row.posterior_rate)}</td><td className="px-3 py-2 text-muted">{pct(row.confidence_low)}–{pct(row.confidence_high)}</td></tr>)}</tbody></table></div>
          </section>
        </>
      )}
    </div>
  );
}
