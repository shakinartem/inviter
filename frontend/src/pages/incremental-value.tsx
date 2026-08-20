import { useState } from "react";
import { AlertTriangle, BadgeDollarSign, BarChart3, FlaskConical } from "lucide-react";

import { useIncrementalBusinessValue } from "@/hooks/use-incremental-value";

function signed(value: number, unit: string) {
  return `${value >= 0 ? "+" : ""}${value.toLocaleString(undefined, { maximumFractionDigits: 2 })} ${unit}`;
}

export default function IncrementalValuePage() {
  const [eventType, setEventType] = useState("payment_received");
  const [valueUnit, setValueUnit] = useState("RUB");
  const [horizonHours, setHorizonHours] = useState(168);
  const [aggregation, setAggregation] = useState<"sum" | "max">("sum");
  const { data, isLoading, error } = useIncrementalBusinessValue({
    event_type: eventType,
    value_unit: valueUnit.trim().toUpperCase(),
    horizon_hours: horizonHours,
    aggregation,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">Incremental Business Value</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">
          Measure how much verified economic value randomized treatment creates above holdout. Units are never mixed: RUB, USD or another business unit are analyzed separately.
        </p>
      </div>

      <section className="grid gap-3 rounded-xl border border-black/5 bg-white p-4 shadow-sm md:grid-cols-4">
        <label className="space-y-1 text-xs font-medium text-muted">
          Business outcome
          <input className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm" value={eventType} onChange={(event) => setEventType(event.target.value)} placeholder="payment_received" />
        </label>
        <label className="space-y-1 text-xs font-medium text-muted">
          Value unit
          <input className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm uppercase" value={valueUnit} onChange={(event) => setValueUnit(event.target.value.toUpperCase())} placeholder="RUB" maxLength={16} />
        </label>
        <label className="space-y-1 text-xs font-medium text-muted">
          Observation horizon
          <select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={horizonHours} onChange={(event) => setHorizonHours(Number(event.target.value))}>
            <option value={24}>24 hours</option>
            <option value={72}>3 days</option>
            <option value={168}>7 days</option>
            <option value={336}>14 days</option>
            <option value={720}>30 days</option>
          </select>
        </label>
        <label className="space-y-1 text-xs font-medium text-muted">
          Value aggregation per person
          <select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={aggregation} onChange={(event) => setAggregation(event.target.value as "sum" | "max")}>
            <option value="sum">Sum verified values</option>
            <option value="max">Maximum verified value</option>
          </select>
        </label>
      </section>

      {isLoading ? (
        <div className="rounded-xl border border-black/5 bg-white p-6 text-sm text-muted">Pooling randomized business value…</div>
      ) : error || !data ? (
        <div className="rounded-xl border border-amber-100 bg-amber-50 p-5 text-sm text-amber-800">No analyzable randomized business-value cohort yet for this event and unit.</div>
      ) : (
        <>
          <section className={`rounded-xl border p-5 ${data.status === "positive" ? "border-emerald-200 bg-emerald-50" : data.status === "negative" ? "border-red-200 bg-red-50" : "border-amber-200 bg-amber-50"}`}>
            <p className="text-xs font-semibold uppercase tracking-wide">{data.status}</p>
            <h2 className="mt-1 text-xl font-semibold text-ink">
              Incremental value {signed(data.pooled_incremental_value_per_unit, data.value_unit)} / randomized unit
            </h2>
            <p className="mt-1 text-sm text-muted">
              95% interval {signed(data.confidence_low_per_unit, data.value_unit)} to {signed(data.confidence_high_per_unit, data.value_unit)} · {signed(data.incremental_value_per_1000, data.value_unit)} per 1,000 randomized units
            </p>
            {data.status === "heterogeneous" && (
              <p className="mt-2 text-xs text-amber-800">Campaign value effects conflict materially. Do not use the pooled mean as a universal economic rule.</p>
            )}
          </section>

          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm">
              <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><BadgeDollarSign className="h-4 w-4" /> Value / unit</div>
              <p className="mt-3 text-2xl font-semibold text-ink">{signed(data.pooled_incremental_value_per_unit, data.value_unit)}</p>
            </div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm">
              <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><FlaskConical className="h-4 w-4" /> Experiments</div>
              <p className="mt-3 text-2xl font-semibold text-ink">{data.experiments_included}/{data.experiments_considered}</p>
              <p className="text-xs text-muted">{data.randomized_units.toLocaleString()} randomized units</p>
            </div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm">
              <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><BarChart3 className="h-4 w-4" /> Heterogeneity I²</div>
              <p className="mt-3 text-2xl font-semibold text-ink">{data.i_squared_percent.toFixed(1)}%</p>
              <p className="text-xs text-muted">τ² {data.tau_squared.toLocaleString()}</p>
            </div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm">
              <div className="text-xs uppercase tracking-wide text-muted">Aggregation</div>
              <p className="mt-3 text-2xl font-semibold capitalize text-ink">{data.aggregation}</p>
              <p className="text-xs text-muted">per randomized person inside horizon</p>
            </div>
          </div>

          <section className="overflow-hidden rounded-xl border border-black/5 bg-white shadow-sm">
            <div className="border-b border-black/5 p-4">
              <h2 className="text-sm font-semibold text-ink">Randomized value effects by campaign</h2>
              <p className="mt-1 text-xs text-muted">People with no matching verified value event remain zero in the treatment/holdout denominator. This preserves intention-to-treat economics.</p>
            </div>
            <div className="overflow-auto">
              <table className="w-full min-w-[980px] text-left text-sm">
                <thead className="bg-stone-50 text-xs text-muted"><tr><th className="px-3 py-2">Campaign</th><th className="px-3 py-2">Treatment units</th><th className="px-3 py-2">Holdout units</th><th className="px-3 py-2">Treatment mean</th><th className="px-3 py-2">Holdout mean</th><th className="px-3 py-2">Incremental / unit</th><th className="px-3 py-2">SE</th><th className="px-3 py-2">Weight</th></tr></thead>
                <tbody>{data.rows.map((row) => <tr key={row.experiment_id} className="border-t border-black/5"><td className="px-3 py-2 font-medium text-ink">{row.campaign_title}</td><td className="px-3 py-2">{row.treatment_units}</td><td className="px-3 py-2">{row.holdout_units}</td><td className="px-3 py-2">{row.treatment_mean_value.toLocaleString()} {data.value_unit}</td><td className="px-3 py-2">{row.holdout_mean_value.toLocaleString()} {data.value_unit}</td><td className="px-3 py-2 font-semibold">{signed(row.incremental_value_per_unit, data.value_unit)}</td><td className="px-3 py-2">{row.standard_error.toLocaleString()}</td><td className="px-3 py-2">{row.weight_percent.toFixed(1)}%</td></tr>)}</tbody>
              </table>
            </div>
          </section>

          <div className="flex items-start gap-2 rounded-lg bg-stone-50 p-3 text-xs text-muted">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>Only signed webhook business outcomes with numeric <code>value</code> and the exact same <code>value_unit</code> are included. Cross-currency/unit mixing is prohibited. {data.warnings.map((warning) => warning.replace(/_/g, " ")).join(" · ")}</span>
          </div>
        </>
      )}
    </div>
  );
}
