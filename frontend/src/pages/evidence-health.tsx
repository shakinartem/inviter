import { useState } from "react";
import { Activity, AlertTriangle, History, RefreshCw, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useEvidenceHealth, type EvidenceHealth, type EvidenceWindowEstimate } from "@/hooks/use-evidence-health";

function formatEstimate(value: number | null, data: EvidenceHealth) {
  if (value == null) return "—";
  if (data.objective === "incremental_business_value") {
    return `${value >= 0 ? "+" : ""}${value.toLocaleString(undefined, { maximumFractionDigits: 2 })} ${data.value_unit ?? ""}`.trim();
  }
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)} pp`;
}

function WindowCard({ title, window, data }: { title: string; window: EvidenceWindowEstimate; data: EvidenceHealth }) {
  return (
    <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted">{title}</span>
        <span className="rounded-full bg-stone-100 px-2 py-0.5 text-[10px] text-muted">{window.experiments} experiments</span>
      </div>
      <p className="mt-3 text-2xl font-semibold text-ink">{formatEstimate(window.estimate, data)}</p>
      <p className="mt-1 text-xs text-muted">
        95% CI {formatEstimate(window.confidence_low, data)} → {formatEstimate(window.confidence_high, data)}
      </p>
      <p className="mt-2 text-xs text-muted">I² {window.i_squared_percent == null ? "—" : `${window.i_squared_percent.toFixed(1)}%`}</p>
    </div>
  );
}

export default function EvidenceHealthPage() {
  const health = useEvidenceHealth();
  const [form, setForm] = useState({
    objective: "incremental_outcomes" as "incremental_outcomes" | "incremental_business_value",
    stage: "business" as "engagement" | "business",
    eventType: "converted",
    valueUnit: "RUB",
    valueAggregation: "sum" as "sum" | "max",
    horizonHours: 168,
    recentWindowDays: 45,
    maxEvidenceAgeDays: 120,
  });
  const data = health.data;

  const run = async () => {
    try {
      const isValue = form.objective === "incremental_business_value";
      await health.mutateAsync({
        objective: form.objective,
        stage: isValue ? "business" : form.stage,
        event_type: form.eventType.trim(),
        value_unit: isValue ? form.valueUnit.trim().toUpperCase() : null,
        value_aggregation: isValue ? form.valueAggregation : null,
        horizon_hours: form.horizonHours,
        recent_window_days: form.recentWindowDays,
        max_evidence_age_days: form.maxEvidenceAgeDays,
      });
    } catch {
      toast.error("Could not evaluate causal evidence health.");
    }
  };

  const healthy = data?.status === "stable";
  const severe = data?.status === "stale" || data?.status === "drift_negative" || data?.status === "drift_positive";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">Causal Evidence Health</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">
          Compare recent mature randomized effects with older evidence. Decision-grade causal priors should be re-tested when they become stale, heterogeneous or materially shift.
        </p>
      </div>

      <section className="space-y-4 rounded-xl border border-black/5 bg-white p-5 shadow-sm">
        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-7">
          <label className="space-y-1 text-xs font-medium text-muted">Objective<select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={form.objective} onChange={(event) => setForm({ ...form, objective: event.target.value as typeof form.objective, eventType: event.target.value === "incremental_business_value" ? "payment_received" : "converted" })}><option value="incremental_outcomes">Incremental outcomes</option><option value="incremental_business_value">Business value</option></select></label>
          {form.objective === "incremental_outcomes" && <label className="space-y-1 text-xs font-medium text-muted">Stage<select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={form.stage} onChange={(event) => setForm({ ...form, stage: event.target.value as typeof form.stage })}><option value="business">Business</option><option value="engagement">Engagement</option></select></label>}
          <label className="space-y-1 text-xs font-medium text-muted">Outcome<input className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm" value={form.eventType} onChange={(event) => setForm({ ...form, eventType: event.target.value })} /></label>
          {form.objective === "incremental_business_value" && <><label className="space-y-1 text-xs font-medium text-muted">Value unit<input className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm uppercase" maxLength={16} value={form.valueUnit} onChange={(event) => setForm({ ...form, valueUnit: event.target.value.toUpperCase() })} /></label><label className="space-y-1 text-xs font-medium text-muted">Aggregation<select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={form.valueAggregation} onChange={(event) => setForm({ ...form, valueAggregation: event.target.value as typeof form.valueAggregation })}><option value="sum">Sum</option><option value="max">Maximum</option></select></label></>}
          <label className="space-y-1 text-xs font-medium text-muted">Outcome horizon<select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={form.horizonHours} onChange={(event) => setForm({ ...form, horizonHours: Number(event.target.value) })}><option value={24}>24h</option><option value={72}>3d</option><option value={168}>7d</option><option value={336}>14d</option><option value={720}>30d</option></select></label>
          <label className="space-y-1 text-xs font-medium text-muted">Recent window<input type="number" min={7} max={365} className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm" value={form.recentWindowDays} onChange={(event) => setForm({ ...form, recentWindowDays: Number(event.target.value) })} /></label>
          <label className="space-y-1 text-xs font-medium text-muted">Max evidence age<input type="number" min={14} max={730} className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm" value={form.maxEvidenceAgeDays} onChange={(event) => setForm({ ...form, maxEvidenceAgeDays: Number(event.target.value) })} /></label>
        </div>
        <div className="flex justify-end"><Button onClick={run} disabled={health.isPending || !form.eventType.trim()}>{health.isPending ? "Evaluating…" : "Evaluate evidence"}</Button></div>
      </section>

      {data && (
        <>
          <section className={`rounded-xl border p-5 ${healthy ? "border-emerald-200 bg-emerald-50" : severe ? "border-red-200 bg-red-50" : "border-amber-200 bg-amber-50"}`}>
            <div className="flex items-start gap-3">
              {healthy ? <ShieldCheck className="mt-0.5 h-5 w-5 text-emerald-700" /> : <AlertTriangle className={`mt-0.5 h-5 w-5 ${severe ? "text-red-700" : "text-amber-700"}`} />}
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold uppercase tracking-wide">Evidence status</p>
                <h2 className="mt-1 text-xl font-semibold capitalize text-ink">{data.status.replace(/_/g, " ")}</h2>
                <p className="mt-1 text-sm text-muted">
                  {data.recommend_reexperiment ? "Fresh randomized evidence is recommended before this prior continues to drive high-stakes allocation." : "Recent randomized evidence is consistent with the historical causal prior."}
                </p>
              </div>
              {data.recommend_reexperiment && <RefreshCw className="h-5 w-5 shrink-0 text-muted" />}
            </div>
          </section>

          <div className="grid gap-3 md:grid-cols-2">
            <WindowCard title={`Recent ${data.recent_window_days}d mature evidence`} window={data.recent} data={data} />
            <WindowCard title="Historical randomized baseline" window={data.historical} data={data} />
          </div>

          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><Activity className="h-4 w-4" /> Drift difference</div><p className="mt-3 text-2xl font-semibold text-ink">{formatEstimate(data.drift_difference, data)}</p><p className="mt-1 text-xs text-muted">CI {formatEstimate(data.drift_confidence_low, data)} → {formatEstimate(data.drift_confidence_high, data)}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="text-xs uppercase tracking-wide text-muted">Drift z-score</div><p className="mt-3 text-2xl font-semibold text-ink">{data.drift_z_score == null ? "—" : data.drift_z_score.toFixed(2)}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><History className="h-4 w-4" /> Evidence age</div><p className="mt-3 text-2xl font-semibold text-ink">{data.evidence_age_days == null ? "—" : `${data.evidence_age_days.toFixed(1)}d`}</p><p className="mt-1 text-xs text-muted">max {data.max_evidence_age_days}d</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="text-xs uppercase tracking-wide text-muted">Latest mature assignment</div><p className="mt-3 text-sm font-semibold text-ink">{data.latest_mature_assignment_at ? new Date(data.latest_mature_assignment_at).toLocaleString() : "—"}</p></div>
          </div>

          <div className="flex items-start gap-2 rounded-lg bg-stone-50 p-3 text-xs text-muted"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><span>{data.warnings.length ? data.warnings.map((warning) => warning.replace(/_/g, " ")).join(" · ") : "No evidence-health warnings."}</span></div>
        </>
      )}
    </div>
  );
}
