import { useState } from "react";
import { AlertTriangle, BarChart3, FlaskConical, Users } from "lucide-react";

import { useIncrementalYield } from "@/hooks/use-incremental-yield";

export default function IncrementalYieldPage() {
  const [stage, setStage] = useState("business");
  const [eventType, setEventType] = useState("converted");
  const [horizonHours, setHorizonHours] = useState(168);
  const { data, isLoading } = useIncrementalYield({ stage, event_type: eventType, horizon_hours: horizonHours });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">Incremental Yield</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">
          Pool mature randomized experiments with a random-effects model. High heterogeneity is surfaced instead of averaging contradictory campaign effects into one confident number.
        </p>
      </div>

      <section className="grid gap-3 rounded-xl border border-black/5 bg-white p-4 shadow-sm md:grid-cols-3">
        <label className="space-y-1 text-xs font-medium text-muted">Stage<select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={stage} onChange={(event) => setStage(event.target.value)}><option value="business">Business</option><option value="engagement">Engagement</option></select></label>
        <label className="space-y-1 text-xs font-medium text-muted">Outcome<input className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm" value={eventType} onChange={(event) => setEventType(event.target.value)} /></label>
        <label className="space-y-1 text-xs font-medium text-muted">Horizon<select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={horizonHours} onChange={(event) => setHorizonHours(Number(event.target.value))}><option value={24}>24h</option><option value={72}>3d</option><option value={168}>7d</option><option value={336}>14d</option><option value={720}>30d</option></select></label>
      </section>

      {isLoading || !data ? (
        <div className="rounded-xl border border-black/5 bg-white p-6 text-sm text-muted">Pooling mature randomized experiments…</div>
      ) : (
        <>
          <section className={`rounded-xl border p-5 ${data.status === "positive" ? "border-emerald-200 bg-emerald-50" : data.status === "negative" ? "border-red-200 bg-red-50" : "border-amber-200 bg-amber-50"}`}>
            <p className="text-xs font-semibold uppercase tracking-wide">{data.status}</p>
            <h2 className="mt-1 text-xl font-semibold text-ink">Pooled lift {data.pooled_lift_percentage_points >= 0 ? "+" : ""}{data.pooled_lift_percentage_points.toFixed(2)} pp</h2>
            <p className="mt-1 text-sm text-muted">95% interval {data.confidence_low_percentage_points.toFixed(2)} to {data.confidence_high_percentage_points.toFixed(2)} pp · {data.incremental_outcomes_per_1000 >= 0 ? "+" : ""}{data.incremental_outcomes_per_1000.toFixed(1)} outcomes / 1,000 randomized units</p>
          </section>

          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><FlaskConical className="h-4 w-4" /> Experiments</div><p className="mt-3 text-2xl font-semibold text-ink">{data.experiments_included}/{data.experiments_considered}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><Users className="h-4 w-4" /> Randomized units</div><p className="mt-3 text-2xl font-semibold text-ink">{data.randomized_units.toLocaleString()}</p><p className="text-xs text-muted">{data.unique_people.toLocaleString()} unique · {data.repeated_people} repeated</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><BarChart3 className="h-4 w-4" /> Heterogeneity I²</div><p className="mt-3 text-2xl font-semibold text-ink">{data.i_squared_percent.toFixed(1)}%</p><p className="text-xs text-muted">τ² {data.tau_squared.toFixed(6)}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="text-xs uppercase tracking-wide text-muted">Q statistic</div><p className="mt-3 text-2xl font-semibold text-ink">{data.q_statistic.toFixed(2)}</p></div>
          </div>

          <section className="overflow-hidden rounded-xl border border-black/5 bg-white shadow-sm">
            <div className="border-b border-black/5 p-4"><h2 className="text-sm font-semibold text-ink">Experiment effects</h2><p className="mt-1 text-xs text-muted">Random-effects weights shrink the influence of large campaigns when between-experiment variance is material.</p></div>
            <div className="overflow-auto"><table className="w-full min-w-[850px] text-left text-sm"><thead className="bg-stone-50 text-xs text-muted"><tr><th className="px-3 py-2">Campaign</th><th className="px-3 py-2">Treatment</th><th className="px-3 py-2">Holdout</th><th className="px-3 py-2">Lift</th><th className="px-3 py-2">SE</th><th className="px-3 py-2">Weight</th></tr></thead><tbody>{data.rows.map((row) => <tr key={row.experiment_id} className="border-t border-black/5"><td className="px-3 py-2 font-medium text-ink">{row.campaign_title}</td><td className="px-3 py-2">{row.treatment_positives}/{row.treatment_units}</td><td className="px-3 py-2">{row.holdout_positives}/{row.holdout_units}</td><td className="px-3 py-2 font-semibold">{row.lift_percentage_points >= 0 ? "+" : ""}{row.lift_percentage_points.toFixed(2)} pp</td><td className="px-3 py-2">{row.standard_error_percentage_points.toFixed(2)} pp</td><td className="px-3 py-2">{row.weight_percent.toFixed(1)}%</td></tr>)}</tbody></table></div>
          </section>

          {data.warnings.length > 0 && <div className="flex items-start gap-2 rounded-lg bg-stone-50 p-3 text-xs text-muted"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><span>{data.warnings.map((warning) => warning.replace(/_/g, " ")).join(" · ")}</span></div>}
        </>
      )}
    </div>
  );
}
