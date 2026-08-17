import { useState } from "react";
import { AlertTriangle, BadgeDollarSign, Filter, ShieldQuestion } from "lucide-react";

import { useContextualBusinessValue } from "@/hooks/use-contextual-value";

function money(value: number, unit: string) {
  return `${value >= 0 ? "+" : ""}${value.toLocaleString(undefined, { maximumFractionDigits: 2 })} ${unit}`;
}

export default function ContextualValuePage() {
  const [eventType, setEventType] = useState("payment_received");
  const [valueUnit, setValueUnit] = useState("RUB");
  const [horizonHours, setHorizonHours] = useState(168);
  const [aggregation, setAggregation] = useState<"sum" | "max">("sum");
  const { data, isLoading, error } = useContextualBusinessValue({
    event_type: eventType,
    value_unit: valueUnit.trim().toUpperCase(),
    horizon_hours: horizonHours,
    aggregation,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">Contextual Incremental Value</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">
          Learn which frozen readiness × intent-signal contexts create additional verified business value, not just additional outcomes. Sparse economic strata are partially pooled toward the global randomized value prior.
        </p>
      </div>

      <section className="grid gap-3 rounded-xl border border-black/5 bg-white p-4 shadow-sm md:grid-cols-4">
        <label className="space-y-1 text-xs font-medium text-muted">Business outcome<input className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm" value={eventType} onChange={(event) => setEventType(event.target.value)} /></label>
        <label className="space-y-1 text-xs font-medium text-muted">Value unit<input className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm uppercase" value={valueUnit} maxLength={16} onChange={(event) => setValueUnit(event.target.value.toUpperCase())} /></label>
        <label className="space-y-1 text-xs font-medium text-muted">Horizon<select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={horizonHours} onChange={(event) => setHorizonHours(Number(event.target.value))}><option value={24}>24h</option><option value={72}>3d</option><option value={168}>7d</option><option value={336}>14d</option><option value={720}>30d</option></select></label>
        <label className="space-y-1 text-xs font-medium text-muted">Per-person aggregation<select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={aggregation} onChange={(event) => setAggregation(event.target.value as "sum" | "max")}><option value="sum">Sum</option><option value="max">Maximum</option></select></label>
      </section>

      {isLoading ? (
        <div className="rounded-xl border border-black/5 bg-white p-6 text-sm text-muted">Pooling randomized value contexts…</div>
      ) : error || !data ? (
        <div className="rounded-xl border border-amber-100 bg-amber-50 p-5 text-sm text-amber-800">Contextual randomized value evidence is not available yet.</div>
      ) : (
        <>
          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><BadgeDollarSign className="h-4 w-4" /> Global value prior</div><p className="mt-3 text-2xl font-semibold text-ink">{money(data.global_prior_value_per_unit, data.value_unit)}</p><p className="text-xs text-muted">{data.global_prior_status.replace(/_/g, " ")}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><Filter className="h-4 w-4" /> Value strata</div><p className="mt-3 text-2xl font-semibold text-ink">{data.strata_evaluated}</p><p className="text-xs text-muted">{data.strata_replicated} replicated</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="text-xs uppercase tracking-wide text-muted">Global I²</div><p className="mt-3 text-2xl font-semibold text-ink">{data.global_prior_i_squared_percent.toFixed(1)}%</p><p className="text-xs text-muted">economic effect heterogeneity</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><ShieldQuestion className="h-4 w-4" /> Replication gate</div><p className="mt-3 text-2xl font-semibold text-ink">2+ experiments</p><p className="text-xs text-muted">30+ units per arm before direction</p></div>
          </div>

          <section className="overflow-hidden rounded-xl border border-black/5 bg-white shadow-sm">
            <div className="border-b border-black/5 p-4"><h2 className="text-sm font-semibold text-ink">Randomized economic response by context</h2><p className="mt-1 text-xs text-muted">Raw value lift is the within-context randomized estimate. Shrunk value is the decision-grade estimate after partial pooling. Exploratory value contexts are hypotheses, not allocation rules.</p></div>
            <div className="overflow-auto"><table className="w-full min-w-[1320px] text-left text-sm"><thead className="bg-stone-50 text-xs text-muted"><tr><th className="px-3 py-2">Ready</th><th className="px-3 py-2">Intent signal</th><th className="px-3 py-2">Experiments</th><th className="px-3 py-2">T/H units</th><th className="px-3 py-2">Treatment mean</th><th className="px-3 py-2">Holdout mean</th><th className="px-3 py-2">Raw incremental</th><th className="px-3 py-2">Shrunk incremental</th><th className="px-3 py-2">95% interval</th><th className="px-3 py-2">Data weight</th><th className="px-3 py-2">Value / 1k</th><th className="px-3 py-2">Evidence</th><th className="px-3 py-2">Direction</th></tr></thead><tbody>{data.rows.map((row) => <tr key={`${row.readiness_bucket}:${row.strongest_signal_type}`} className="border-t border-black/5"><td className="px-3 py-2 font-medium text-ink">{row.readiness_bucket}</td><td className="px-3 py-2">{row.strongest_signal_type.replace(/_/g, " ")}</td><td className="px-3 py-2">{row.experiments}</td><td className="px-3 py-2">{row.treatment_units}/{row.holdout_units}</td><td className="px-3 py-2">{row.treatment_mean_value.toLocaleString()} {data.value_unit}</td><td className="px-3 py-2">{row.holdout_mean_value.toLocaleString()} {data.value_unit}</td><td className="px-3 py-2">{money(row.raw_incremental_value_per_unit, data.value_unit)}</td><td className="px-3 py-2 font-semibold text-ink">{money(row.shrunk_incremental_value_per_unit, data.value_unit)}</td><td className="px-3 py-2 text-muted">{row.confidence_low_per_unit.toLocaleString()} to {row.confidence_high_per_unit.toLocaleString()} {data.value_unit}</td><td className="px-3 py-2">{row.data_weight_percent.toFixed(1)}%</td><td className="px-3 py-2 font-medium">{money(row.incremental_value_per_1000, data.value_unit)}</td><td className="px-3 py-2"><span className={`rounded-full px-2 py-1 text-[10px] ${row.evidence_status === "replicated" ? "bg-emerald-50 text-emerald-700" : "bg-stone-100 text-muted"}`}>{row.evidence_status}</span></td><td className="px-3 py-2"><span className={`rounded-full px-2 py-1 text-[10px] ${row.direction === "positive" ? "bg-emerald-50 text-emerald-700" : row.direction === "negative" ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-700"}`}>{row.direction}</span></td></tr>)}</tbody></table></div>
            {data.rows.length === 0 && <div className="p-5 text-sm text-muted">No frozen context has enough treatment and holdout value evidence yet.</div>}
          </section>

          <div className="flex items-start gap-2 rounded-lg bg-stone-50 p-3 text-xs text-muted"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><span>Only signed webhook values with the exact same {data.value_unit} unit are used. No-event randomized units remain zero. {data.warnings.map((warning) => warning.replace(/_/g, " ")).join(" · ")}</span></div>
        </>
      )}
    </div>
  );
}
