import { useMemo, useState } from "react";
import { AlertTriangle, BadgeDollarSign, Gauge, TrendingDown } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useCapacityFrontier, type CapacityFrontier } from "@/hooks/use-capacity-frontier";

function formatValue(value: number, frontier: CapacityFrontier) {
  if (frontier.objective === "incremental_business_value") {
    return `${value >= 0 ? "+" : ""}${value.toLocaleString(undefined, { maximumFractionDigits: 2 })} ${frontier.value_unit ?? ""}`.trim();
  }
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)} outcomes`;
}

export default function CapacityEconomicsPage() {
  const frontier = useCapacityFrontier();
  const [form, setForm] = useState({
    objective: "incremental_business_value" as "incremental_outcomes" | "incremental_business_value",
    eventType: "payment_received",
    valueUnit: "RUB",
    valueAggregation: "sum" as "sum" | "max",
    horizonHours: 168,
    allocationMode: "decision_grade" as "decision_grade" | "coverage_expansion",
    capacities: "100,250,500,1000,2000,5000",
    costPerAction: "",
  });
  const data = frontier.data;
  const capacities = useMemo(
    () => form.capacities.split(",").map((value) => Number(value.trim())).filter((value) => Number.isFinite(value) && value > 0),
    [form.capacities],
  );

  const calculate = async () => {
    if (!capacities.length) return;
    try {
      const isValue = form.objective === "incremental_business_value";
      await frontier.mutateAsync({
        platform: "telegram",
        stage: "business",
        event_type: form.eventType.trim(),
        horizon_hours: form.horizonHours,
        objective: form.objective,
        value_unit: isValue ? form.valueUnit.trim().toUpperCase() : null,
        value_aggregation: isValue ? form.valueAggregation : null,
        allocation_mode: form.allocationMode,
        capacities,
        cost_per_action: isValue && form.costPerAction ? Number(form.costPerAction) : null,
      });
    } catch {
      toast.error("Could not calculate the capacity frontier. Causal evidence may still be insufficient.");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">Capacity Economics</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">
          Estimate diminishing causal returns as action capacity expands. When action cost is supplied, find the largest tested capacity block whose conservative marginal business value still exceeds its cost.
        </p>
      </div>

      <section className="space-y-4 rounded-xl border border-black/5 bg-white p-5 shadow-sm">
        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
          <label className="space-y-1 text-xs font-medium text-muted">Objective<select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={form.objective} onChange={(event) => setForm({ ...form, objective: event.target.value as typeof form.objective, eventType: event.target.value === "incremental_business_value" ? "payment_received" : "converted" })}><option value="incremental_business_value">Business value</option><option value="incremental_outcomes">Outcome count</option></select></label>
          <label className="space-y-1 text-xs font-medium text-muted">Outcome<input className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm" value={form.eventType} onChange={(event) => setForm({ ...form, eventType: event.target.value })} /></label>
          <label className="space-y-1 text-xs font-medium text-muted">Horizon<select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={form.horizonHours} onChange={(event) => setForm({ ...form, horizonHours: Number(event.target.value) })}><option value={24}>24h</option><option value={72}>3d</option><option value={168}>7d</option><option value={336}>14d</option><option value={720}>30d</option></select></label>
          <label className="space-y-1 text-xs font-medium text-muted">Evidence policy<select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={form.allocationMode} onChange={(event) => setForm({ ...form, allocationMode: event.target.value as typeof form.allocationMode })}><option value="decision_grade">Decision grade</option><option value="coverage_expansion">Coverage expansion</option></select></label>
          {form.objective === "incremental_business_value" && <><label className="space-y-1 text-xs font-medium text-muted">Value unit<input className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm uppercase" maxLength={16} value={form.valueUnit} onChange={(event) => setForm({ ...form, valueUnit: event.target.value.toUpperCase() })} /></label><label className="space-y-1 text-xs font-medium text-muted">Value aggregation<select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={form.valueAggregation} onChange={(event) => setForm({ ...form, valueAggregation: event.target.value as typeof form.valueAggregation })}><option value="sum">Sum</option><option value="max">Maximum</option></select></label></>}
        </div>
        <div className="grid gap-3 md:grid-cols-[1.5fr_1fr_auto]">
          <label className="space-y-1 text-xs font-medium text-muted">Capacity checkpoints<input className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm" value={form.capacities} onChange={(event) => setForm({ ...form, capacities: event.target.value })} placeholder="100,250,500,1000,2000" /></label>
          {form.objective === "incremental_business_value" ? <label className="space-y-1 text-xs font-medium text-muted">Cost / action ({form.valueUnit || "unit"})<input type="number" min={0} className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm" value={form.costPerAction} onChange={(event) => setForm({ ...form, costPerAction: event.target.value })} placeholder="optional" /></label> : <div />}
          <div className="flex items-end"><Button onClick={calculate} disabled={frontier.isPending || !capacities.length}>{frontier.isPending ? "Calculating…" : "Calculate frontier"}</Button></div>
        </div>
      </section>

      {data && (
        <>
          <section className={`rounded-xl border p-5 ${data.recommended_capacity ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50"}`}>
            <div className="flex items-start gap-3">
              <Gauge className={`mt-0.5 h-5 w-5 ${data.recommended_capacity ? "text-emerald-700" : "text-amber-700"}`} />
              <div><p className="text-xs font-semibold uppercase tracking-wide">Economic capacity recommendation</p><h2 className="mt-1 text-xl font-semibold text-ink">{data.recommended_capacity ? `${data.recommended_capacity.toLocaleString()} actions` : "Cost threshold not established"}</h2><p className="mt-1 text-sm text-muted">{data.recommendation_reason}</p></div>
            </div>
          </section>

          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><BadgeDollarSign className="h-4 w-4" /> Positive unique supply</div><p className="mt-3 text-2xl font-semibold text-ink">{data.unique_positive_candidates.toLocaleString()}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="text-xs uppercase tracking-wide text-muted">Overlap removed</div><p className="mt-3 text-2xl font-semibold text-ink">{data.overlap_removed.toLocaleString()}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><TrendingDown className="h-4 w-4" /> Prior I²</div><p className="mt-3 text-2xl font-semibold text-ink">{data.global_prior_i_squared.toFixed(1)}%</p><p className="text-xs text-muted">{data.global_prior_status.replace(/_/g, " ")}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="text-xs uppercase tracking-wide text-muted">Action cost</div><p className="mt-3 text-2xl font-semibold text-ink">{data.cost_per_action == null ? "—" : `${data.cost_per_action.toLocaleString()} ${data.value_unit ?? ""}`}</p></div>
          </div>

          <section className="overflow-hidden rounded-xl border border-black/5 bg-white shadow-sm">
            <div className="border-b border-black/5 p-4"><h2 className="text-sm font-semibold text-ink">Marginal capacity frontier</h2><p className="mt-1 text-xs text-muted">Each row adds the newest capacity block after all higher-conservative-value unique people have already been selected.</p></div>
            <div className="overflow-auto"><table className="w-full min-w-[1150px] text-left text-sm"><thead className="bg-stone-50 text-xs text-muted"><tr><th className="px-3 py-2">Requested</th><th className="px-3 py-2">Allocated</th><th className="px-3 py-2">Cumulative conservative</th><th className="px-3 py-2">Cumulative expected</th><th className="px-3 py-2">Marginal block</th><th className="px-3 py-2">Marginal conservative</th><th className="px-3 py-2">Marginal / action</th><th className="px-3 py-2">Marginal cost</th><th className="px-3 py-2">Marginal conservative net</th></tr></thead><tbody>{data.points.map((point) => <tr key={point.requested_capacity} className="border-t border-black/5"><td className="px-3 py-2 font-medium text-ink">{point.requested_capacity.toLocaleString()}</td><td className="px-3 py-2">{point.allocated_count.toLocaleString()}</td><td className="px-3 py-2 font-semibold">{formatValue(point.cumulative_conservative, data)}</td><td className="px-3 py-2">{formatValue(point.cumulative_expected, data)}</td><td className="px-3 py-2">+{point.marginal_count.toLocaleString()}</td><td className="px-3 py-2">{formatValue(point.marginal_conservative, data)}</td><td className="px-3 py-2">{point.marginal_conservative_per_action == null ? "—" : formatValue(point.marginal_conservative_per_action, data)}</td><td className="px-3 py-2">{point.marginal_cost == null ? "—" : `${point.marginal_cost.toLocaleString()} ${data.value_unit ?? ""}`}</td><td className={`px-3 py-2 font-semibold ${point.marginal_conservative_net != null && point.marginal_conservative_net > 0 ? "text-emerald-700" : "text-ink"}`}>{point.marginal_conservative_net == null ? "—" : formatValue(point.marginal_conservative_net, data)}</td></tr>)}</tbody></table></div>
          </section>

          <div className="flex items-start gap-2 rounded-lg bg-stone-50 p-3 text-xs text-muted"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><span>{data.warnings.map((warning) => warning.replace(/_/g, " ")).join(" · ")}. Capacity checkpoints are a causal lower-bound frontier when the candidate pool cap is reached.</span></div>
        </>
      )}
    </div>
  );
}
