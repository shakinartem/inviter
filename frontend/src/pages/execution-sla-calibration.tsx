import { useMemo, useState } from "react";
import { Activity, CheckCircle2, RefreshCw, Target, TriangleAlert } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useCampaigns } from "@/hooks/use-campaigns";
import {
  useExecutionSLACalibration,
  useExecutionSLALabels,
  useFinalizeExecutionSLA,
} from "@/hooks/use-execution-sla";

function pct(value: number | null) {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
}

export default function ExecutionSLACalibrationPage() {
  const { data: campaigns } = useCampaigns({ skip: 0, limit: 500 });
  const [campaignId, setCampaignId] = useState<string | null>(null);
  const calibration = useExecutionSLACalibration(campaignId);
  const labels = useExecutionSLALabels(campaignId, 50);
  const finalize = useFinalizeExecutionSLA();
  const campaignOptions = useMemo(() => campaigns ?? [], [campaigns]);

  const finalizeNow = async () => {
    try {
      const result = await finalize.mutateAsync(500);
      toast.success(`Finalized ${result.labeled} labels · ${result.ineligible_queue} excluded`);
    } catch {
      toast.error("Could not finalize mature SLA labels.");
    }
  };

  const data = calibration.data;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-ink">SLA Calibration</h1>
          <p className="mt-1 max-w-4xl text-sm text-muted">
            Reality check for execution probability. Mature forecast snapshots are matched only to jobs that already existed at prediction time; later jobs cannot rescue an old forecast.
          </p>
        </div>
        <Button variant="outline" onClick={finalizeNow} disabled={finalize.isPending}>
          <RefreshCw className="mr-2 h-4 w-4" /> {finalize.isPending ? "Finalizing…" : "Finalize mature labels"}
        </Button>
      </div>

      <section className="rounded-xl border border-black/5 bg-white p-5 shadow-sm">
        <label className="block max-w-lg space-y-1 text-xs font-medium text-muted">
          Calibration scope
          <select value={campaignId ?? ""} onChange={(event) => setCampaignId(event.target.value || null)} className="block w-full rounded-lg border border-black/10 px-3 py-2 text-sm text-ink">
            <option value="">All campaigns · recommended for model health</option>
            {campaignOptions.map((campaign) => <option key={campaign.id} value={campaign.id}>{campaign.title}</option>)}
          </select>
        </label>
      </section>

      {data && (
        <>
          <div className="grid gap-3 md:grid-cols-5">
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><Target className="h-4 w-4" /> Labeled</div><p className="mt-3 text-2xl font-semibold text-ink">{data.labeled_samples}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><Activity className="h-4 w-4" /> Brier</div><p className="mt-3 text-2xl font-semibold text-ink">{data.brier_score == null ? "—" : data.brier_score.toFixed(3)}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="text-xs uppercase tracking-wide text-muted">ECE</div><p className="mt-3 text-2xl font-semibold text-ink">{data.expected_calibration_error == null ? "—" : data.expected_calibration_error.toFixed(3)}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="text-xs uppercase tracking-wide text-muted">Predicted / observed</div><p className="mt-3 text-lg font-semibold text-ink">{pct(data.mean_prediction)} / {pct(data.observed_completion_rate)}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="text-xs uppercase tracking-wide text-muted">Model health</div><p className={`mt-3 text-lg font-semibold ${data.status === "usable" ? "text-emerald-700" : data.status === "miscalibrated" ? "text-red-700" : "text-amber-700"}`}>{data.status}</p></div>
          </div>

          <section className={`rounded-xl border p-4 ${data.status === "usable" ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50"}`}>
            <div className="flex items-start gap-2">
              {data.status === "usable" ? <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-700" /> : <TriangleAlert className="mt-0.5 h-4 w-4 text-amber-700" />}
              <div className="text-sm">
                <p className="font-medium text-ink">Calibration bias {data.calibration_bias == null ? "—" : `${data.calibration_bias >= 0 ? "+" : ""}${(data.calibration_bias * 100).toFixed(1)} pp`}</p>
                <p className="mt-1 text-xs text-muted">Positive bias means the model predicted completion more often than reality delivered. Conservative continuity bounds are intentionally not scored here; this calibration targets the point forecast of fixed-workload completion.</p>
              </div>
            </div>
          </section>

          <section className="overflow-hidden rounded-xl border border-black/5 bg-white shadow-sm">
            <div className="border-b border-black/5 p-4"><h2 className="text-sm font-semibold text-ink">Reliability buckets</h2><p className="mt-1 text-xs text-muted">A calibrated model should place observed completion near mean prediction inside each probability band.</p></div>
            <div className="overflow-auto">
              <table className="w-full min-w-[760px] text-left text-sm">
                <thead className="bg-stone-50 text-xs text-muted"><tr><th className="px-3 py-2">Band</th><th className="px-3 py-2">Samples</th><th className="px-3 py-2">Mean prediction</th><th className="px-3 py-2">Observed</th><th className="px-3 py-2">Brier</th></tr></thead>
                <tbody>{data.buckets.map((bucket) => <tr key={`${bucket.lower_bound}-${bucket.upper_bound}`} className="border-t border-black/5"><td className="px-3 py-3">{Math.round(bucket.lower_bound * 100)}–{Math.round(bucket.upper_bound * 100)}%</td><td className="px-3 py-3">{bucket.samples}</td><td className="px-3 py-3">{pct(bucket.mean_prediction)}</td><td className="px-3 py-3">{pct(bucket.observed_completion_rate)}</td><td className="px-3 py-3">{bucket.brier_score == null ? "—" : bucket.brier_score.toFixed(3)}</td></tr>)}</tbody>
              </table>
            </div>
          </section>

          <div className="space-y-1 rounded-xl border border-black/5 bg-white p-4 text-xs text-muted shadow-sm">{data.warnings.map((warning) => <p key={warning}>• {warning}</p>)}</div>
        </>
      )}

      <section className="overflow-hidden rounded-xl border border-black/5 bg-white shadow-sm">
        <div className="border-b border-black/5 p-4"><h2 className="text-sm font-semibold text-ink">Label audit</h2><p className="mt-1 text-xs text-muted">Prediction-time queue eligibility and actual completion labels. Ineligible rows never enter Brier/ECE.</p></div>
        <div className="overflow-auto">
          <table className="w-full min-w-[1100px] text-left text-sm">
            <thead className="bg-stone-50 text-xs text-muted"><tr><th className="px-3 py-2">Forecast</th><th className="px-3 py-2">Deadline</th><th className="px-3 py-2">Prediction</th><th className="px-3 py-2">Required</th><th className="px-3 py-2">Actual success</th><th className="px-3 py-2">Hard-failure days</th><th className="px-3 py-2">Label</th></tr></thead>
            <tbody>{(labels.data ?? []).map((item) => <tr key={item.id} className="border-t border-black/5"><td className="px-3 py-3 text-xs text-muted">{new Date(item.forecast_created_at).toLocaleString()}</td><td className="px-3 py-3">{new Date(item.deadline_at).toLocaleDateString()}</td><td className="px-3 py-3">{pct(item.predicted_completion_probability)}</td><td className="px-3 py-3">{item.remaining_actions}</td><td className="px-3 py-3">{item.actual_successful_actions ?? "—"}</td><td className="px-3 py-3">{item.actual_hard_failure_days ?? "—"}</td><td className="px-3 py-3"><span className={item.label_status === "labeled" ? (item.actual_met_sla ? "text-emerald-700" : "text-red-700") : "text-muted"}>{item.label_status === "labeled" ? (item.actual_met_sla ? "met" : "missed") : item.label_status.replace(/_/g, " ")}</span></td></tr>)}</tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
