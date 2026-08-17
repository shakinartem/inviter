import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, Calculator, CheckCircle2, FlaskConical, Gauge } from "lucide-react";

import { useExperimentPowerPlan } from "@/hooks/use-experiment-power";
import { useSegments } from "@/hooks/use-segments";

export default function ExperimentPlannerPage() {
  const { data: segments } = useSegments({ active_only: true, platform: "telegram" });
  const opportunities = useMemo(
    () => (segments ?? []).filter((segment) => segment.last_refreshed_at && segment.matched_count > 0),
    [segments],
  );
  const [segmentId, setSegmentId] = useState<string | null>(null);
  const [holdout, setHoldout] = useState(10);
  const [budget, setBudget] = useState(1000);
  const [lift, setLift] = useState(2);
  const [baseline, setBaseline] = useState("");
  const [eventType, setEventType] = useState("converted");
  const [horizonHours, setHorizonHours] = useState(168);

  useEffect(() => {
    if (!segmentId && opportunities.length) setSegmentId(opportunities[0].id);
  }, [opportunities, segmentId]);

  const { data, isLoading } = useExperimentPowerPlan(segmentId, {
    stage: "business",
    event_type: eventType,
    horizon_hours: horizonHours,
    holdout_percentage: holdout,
    action_budget: budget,
    target_lift_percentage_points: lift,
    ...(baseline ? { baseline_rate_assumption: Number(baseline) } : {}),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">Experiment Planner</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">
          Check statistical power before trading reach for causal learning. The planner uses mature randomized holdout history when available; otherwise baseline must be an explicit assumption.
        </p>
      </div>

      <section className="grid gap-3 rounded-xl border border-black/5 bg-white p-4 shadow-sm md:grid-cols-3 xl:grid-cols-6">
        <label className="space-y-1 text-xs font-medium text-muted xl:col-span-2">Opportunity<select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={segmentId ?? ""} onChange={(event) => setSegmentId(event.target.value || null)}><option value="">Select</option>{opportunities.map((segment) => <option key={segment.id} value={segment.id}>{segment.name} · {segment.matched_count.toLocaleString()}</option>)}</select></label>
        <label className="space-y-1 text-xs font-medium text-muted">Holdout %<input type="number" min={1} max={50} className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm" value={holdout} onChange={(event) => setHoldout(Math.max(1, Math.min(50, Number(event.target.value) || 1)))} /></label>
        <label className="space-y-1 text-xs font-medium text-muted">Treatment budget<input type="number" min={1} max={50000} className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm" value={budget} onChange={(event) => setBudget(Math.max(1, Number(event.target.value) || 1))} /></label>
        <label className="space-y-1 text-xs font-medium text-muted">Target lift, pp<input type="number" min={0.1} step={0.1} className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm" value={lift} onChange={(event) => setLift(Math.max(0.1, Number(event.target.value) || 0.1))} /></label>
        <label className="space-y-1 text-xs font-medium text-muted">Baseline assumption %<input type="number" min={0.1} max={99.9} step={0.1} className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm" placeholder="auto if history" value={baseline} onChange={(event) => setBaseline(event.target.value)} /></label>
        <label className="space-y-1 text-xs font-medium text-muted">Outcome<input className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm" value={eventType} onChange={(event) => setEventType(event.target.value)} /></label>
        <label className="space-y-1 text-xs font-medium text-muted">Horizon<select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={horizonHours} onChange={(event) => setHorizonHours(Number(event.target.value))}><option value={24}>24h</option><option value={72}>3d</option><option value={168}>7d</option><option value={336}>14d</option><option value={720}>30d</option></select></label>
      </section>

      {!segmentId || isLoading || !data ? (
        <div className="rounded-xl border border-black/5 bg-white p-6 text-sm text-muted">{isLoading ? "Calculating power…" : "Select a materialized Opportunity."}</div>
      ) : (
        <>
          <section className={`rounded-xl border p-5 ${data.status === "adequately_powered" ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50"}`}>
            <div className="flex items-start gap-3">
              {data.status === "adequately_powered" ? <CheckCircle2 className="mt-0.5 h-5 w-5 text-emerald-700" /> : <AlertTriangle className="mt-0.5 h-5 w-5 text-amber-700" />}
              <div><p className="text-xs font-semibold uppercase tracking-wide">{data.status.replace(/_/g, " ")}</p><h2 className="mt-1 text-xl font-semibold text-ink">{data.segment_name}</h2><p className="mt-1 text-sm text-muted">Baseline {data.baseline_rate == null ? "required" : `${data.baseline_rate.toFixed(2)}%`} · source {data.baseline_source.replace(/_/g, " ")} · target +{data.target_lift_percentage_points.toFixed(1)} pp</p></div>
            </div>
          </section>

          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><Calculator className="h-4 w-4" /> Required total</div><p className="mt-3 text-2xl font-semibold text-ink">{data.required_total_units?.toLocaleString() ?? "—"}</p><p className="text-xs text-muted">T {data.required_treatment_units?.toLocaleString() ?? "—"} · H {data.required_holdout_units?.toLocaleString() ?? "—"}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><FlaskConical className="h-4 w-4" /> Projected pool</div><p className="mt-3 text-2xl font-semibold text-ink">{data.projected_total_units.toLocaleString()}</p><p className="text-xs text-muted">T {data.projected_treatment_units.toLocaleString()} · H {data.projected_holdout_units.toLocaleString()}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><Gauge className="h-4 w-4" /> Detectable lift</div><p className="mt-3 text-2xl font-semibold text-ink">{data.projected_mde_percentage_points == null ? "—" : `${data.projected_mde_percentage_points.toFixed(2)} pp`}</p><p className="text-xs text-muted">80% power · α 0.05</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="text-xs uppercase tracking-wide text-muted">Available audience</div><p className="mt-3 text-2xl font-semibold text-ink">{data.available_segment_units.toLocaleString()}</p><p className="text-xs text-muted">materialized Opportunity units</p></div>
          </div>

          {data.warnings.length > 0 && <div className="rounded-lg bg-stone-50 p-3 text-xs text-muted">{data.warnings.map((warning) => warning.replace(/_/g, " ")).join(" · ")}</div>}
        </>
      )}
    </div>
  );
}
