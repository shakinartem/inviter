import { useState } from "react";
import { AlertTriangle, Filter, GitCompareArrows, ShieldQuestion } from "lucide-react";

import { useContextualYield } from "@/hooks/use-contextual-yield";

function signed(value: number, suffix = " pp") {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}${suffix}`;
}

export default function ContextualYieldPage() {
  const [stage, setStage] = useState("business");
  const [eventType, setEventType] = useState("converted");
  const [horizonHours, setHorizonHours] = useState(168);
  const { data, isLoading, error } = useContextualYield({
    stage,
    event_type: eventType,
    horizon_hours: horizonHours,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">Contextual Incremental Yield</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">
          Learn where an action creates additional behavior across frozen readiness × intent-signal contexts. Every contrast is randomized within a campaign first; sparse strata are partially pooled toward the global causal prior.
        </p>
      </div>

      <section className="grid gap-3 rounded-xl border border-black/5 bg-white p-4 shadow-sm md:grid-cols-3">
        <label className="space-y-1 text-xs font-medium text-muted">
          Stage
          <select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={stage} onChange={(event) => setStage(event.target.value)}>
            <option value="business">Business</option>
            <option value="engagement">Engagement</option>
          </select>
        </label>
        <label className="space-y-1 text-xs font-medium text-muted">
          Outcome
          <input className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm" value={eventType} onChange={(event) => setEventType(event.target.value)} />
        </label>
        <label className="space-y-1 text-xs font-medium text-muted">
          Horizon
          <select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={horizonHours} onChange={(event) => setHorizonHours(Number(event.target.value))}>
            <option value={24}>24 hours</option>
            <option value={72}>3 days</option>
            <option value={168}>7 days</option>
            <option value={336}>14 days</option>
            <option value={720}>30 days</option>
          </select>
        </label>
      </section>

      {isLoading ? (
        <div className="rounded-xl border border-black/5 bg-white p-6 text-sm text-muted">Pooling randomized contexts…</div>
      ) : error || !data ? (
        <div className="rounded-xl border border-amber-100 bg-amber-50 p-5 text-sm text-amber-800">Contextual causal evidence is not available yet.</div>
      ) : (
        <>
          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm">
              <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted"><GitCompareArrows className="h-4 w-4" /> Global causal prior</div>
              <p className="mt-3 text-2xl font-semibold text-ink">{signed(data.global_prior_lift_percentage_points)}</p>
              <p className="mt-1 text-xs text-muted">{data.global_prior_status.replace(/_/g, " ")}</p>
            </div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm">
              <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted"><Filter className="h-4 w-4" /> Context strata</div>
              <p className="mt-3 text-2xl font-semibold text-ink">{data.strata_evaluated}</p>
              <p className="mt-1 text-xs text-muted">{data.strata_replicated} replicated</p>
            </div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm">
              <div className="text-xs font-medium uppercase tracking-wide text-muted">Global heterogeneity I²</div>
              <p className="mt-3 text-2xl font-semibold text-ink">{data.global_prior_i_squared_percent.toFixed(1)}%</p>
              <p className="mt-1 text-xs text-muted">higher means context likely matters more</p>
            </div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm">
              <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted"><ShieldQuestion className="h-4 w-4" /> Replication gate</div>
              <p className="mt-3 text-2xl font-semibold text-ink">2+ experiments</p>
              <p className="mt-1 text-xs text-muted">30+ units in each arm before directional claims</p>
            </div>
          </div>

          <section className="overflow-hidden rounded-xl border border-black/5 bg-white shadow-sm">
            <div className="border-b border-black/5 p-4">
              <h2 className="text-sm font-semibold text-ink">Randomized contextual effects</h2>
              <p className="mt-1 max-w-3xl text-xs text-muted">
                Raw lift is the within-context randomized estimate. Shrunk lift is the decision-grade estimate after partial pooling to the global causal prior. Exploratory rows are evidence to test again, not automatic targeting rules.
              </p>
            </div>
            <div className="overflow-auto">
              <table className="w-full min-w-[1180px] text-left text-sm">
                <thead className="bg-stone-50 text-xs text-muted">
                  <tr>
                    <th className="px-3 py-2">Readiness</th>
                    <th className="px-3 py-2">Intent signal</th>
                    <th className="px-3 py-2">Experiments</th>
                    <th className="px-3 py-2">Treatment</th>
                    <th className="px-3 py-2">Holdout</th>
                    <th className="px-3 py-2">Raw lift</th>
                    <th className="px-3 py-2">Shrunk lift</th>
                    <th className="px-3 py-2">Interval</th>
                    <th className="px-3 py-2">Data weight</th>
                    <th className="px-3 py-2">Incremental / 1k</th>
                    <th className="px-3 py-2">Evidence</th>
                    <th className="px-3 py-2">Direction</th>
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((row) => (
                    <tr key={`${row.readiness_bucket}:${row.strongest_signal_type}`} className="border-t border-black/5">
                      <td className="px-3 py-2 font-medium text-ink">{row.readiness_bucket}</td>
                      <td className="px-3 py-2 text-ink">{row.strongest_signal_type.replace(/_/g, " ")}</td>
                      <td className="px-3 py-2">{row.experiments}</td>
                      <td className="px-3 py-2">{row.treatment_positives}/{row.treatment_units}</td>
                      <td className="px-3 py-2">{row.holdout_positives}/{row.holdout_units}</td>
                      <td className="px-3 py-2">{signed(row.raw_lift_percentage_points)}</td>
                      <td className="px-3 py-2 font-semibold text-ink">{signed(row.shrunk_lift_percentage_points)}</td>
                      <td className="px-3 py-2 text-muted">{row.confidence_low_percentage_points.toFixed(2)} to {row.confidence_high_percentage_points.toFixed(2)} pp</td>
                      <td className="px-3 py-2">{row.data_weight_percent.toFixed(1)}%</td>
                      <td className="px-3 py-2 font-medium">{row.incremental_outcomes_per_1000 >= 0 ? "+" : ""}{row.incremental_outcomes_per_1000.toFixed(1)}</td>
                      <td className="px-3 py-2"><span className={`rounded-full px-2 py-1 text-[10px] ${row.evidence_status === "replicated" ? "bg-emerald-50 text-emerald-700" : "bg-stone-100 text-muted"}`}>{row.evidence_status}</span></td>
                      <td className="px-3 py-2"><span className={`rounded-full px-2 py-1 text-[10px] ${row.direction === "positive" ? "bg-emerald-50 text-emerald-700" : row.direction === "negative" ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-700"}`}>{row.direction}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {data.rows.length === 0 && <div className="p-5 text-sm text-muted">No frozen readiness × signal stratum has both randomized arms yet.</div>}
          </section>

          {data.warnings.length > 0 && (
            <div className="flex items-start gap-2 rounded-lg bg-stone-50 p-3 text-xs text-muted">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{data.warnings.map((warning) => warning.replace(/_/g, " ")).join(" · ")}. Context rows should be promoted into product policy only after replicated randomized evidence.</span>
            </div>
          )}
        </>
      )}
    </div>
  );
}
