import { useMemo, useState } from "react";
import { Activity, CheckCircle2, RefreshCw, Target, TriangleAlert } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useCampaigns } from "@/hooks/use-campaigns";
import {
  useExecutionSLACalibration,
  useExecutionSLAContinuityCalibration,
  useExecutionSLALabels,
  useFinalizeExecutionSLA,
} from "@/hooks/use-execution-sla";

function pct(value: number | null) {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
}

function statusClass(status: string) {
  if (status === "usable") return "text-emerald-700";
  if (status === "miscalibrated") return "text-red-700";
  return "text-amber-700";
}

export default function ExecutionSLACalibrationPage() {
  const { data: campaigns } = useCampaigns({ skip: 0, limit: 500 });
  const [campaignId, setCampaignId] = useState<string | null>(null);
  const completion = useExecutionSLACalibration(campaignId);
  const continuity = useExecutionSLAContinuityCalibration(campaignId);
  const labels = useExecutionSLALabels(campaignId, 50);
  const finalize = useFinalizeExecutionSLA();
  const campaignOptions = useMemo(() => campaigns ?? [], [campaigns]);

  const finalizeNow = async () => {
    try {
      const result = await finalize.mutateAsync(500);
      toast.success(`Finalized ${result.labeled} labels · ${result.ineligible_queue} queue-excluded · ${result.intervened} intervention-excluded`);
    } catch {
      toast.error("Could not finalize mature SLA labels.");
    }
  };

  const completionData = completion.data;
  const continuityData = continuity.data;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-ink">SLA Calibration</h1>
          <p className="mt-1 max-w-4xl text-sm text-muted">
            Two factual targets: fixed-workload completion by deadline and schedule continuity across forecast-relative 24h delivery windows. Both use only prediction-time jobs and exclude operator intervention.
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

      {completionData && (
        <section className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-ink">Fixed-workload completion</h2>
            <p className="mt-1 text-xs text-muted">Did prediction-time jobs complete the requested remaining workload before the forecast deadline?</p>
          </div>
          <div className="grid gap-3 md:grid-cols-5">
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><Target className="h-4 w-4" /> Labeled</div><p className="mt-3 text-2xl font-semibold text-ink">{completionData.labeled_samples}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><Activity className="h-4 w-4" /> Brier</div><p className="mt-3 text-2xl font-semibold text-ink">{completionData.brier_score == null ? "—" : completionData.brier_score.toFixed(3)}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="text-xs uppercase tracking-wide text-muted">ECE</div><p className="mt-3 text-2xl font-semibold text-ink">{completionData.expected_calibration_error == null ? "—" : completionData.expected_calibration_error.toFixed(3)}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="text-xs uppercase tracking-wide text-muted">Predicted / observed</div><p className="mt-3 text-lg font-semibold text-ink">{pct(completionData.mean_prediction)} / {pct(completionData.observed_completion_rate)}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="text-xs uppercase tracking-wide text-muted">Model health</div><p className={`mt-3 text-lg font-semibold ${statusClass(completionData.status)}`}>{completionData.status}</p></div>
          </div>
          <section className={`rounded-xl border p-4 ${completionData.status === "usable" ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50"}`}>
            <div className="flex items-start gap-2">
              {completionData.status === "usable" ? <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-700" /> : <TriangleAlert className="mt-0.5 h-4 w-4 text-amber-700" />}
              <div className="text-sm"><p className="font-medium text-ink">Completion bias {completionData.calibration_bias == null ? "—" : `${completionData.calibration_bias >= 0 ? "+" : ""}${(completionData.calibration_bias * 100).toFixed(1)} pp`}</p><p className="mt-1 text-xs text-muted">Positive bias means the raw point model predicts completion more often than reality delivers. Governed calibrator quality is monitored separately in SLA Governance.</p></div>
            </div>
          </section>
          <section className="overflow-hidden rounded-xl border border-black/5 bg-white shadow-sm">
            <div className="border-b border-black/5 p-4"><h3 className="text-sm font-semibold text-ink">Completion reliability buckets</h3></div>
            <div className="overflow-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead className="bg-stone-50 text-xs text-muted"><tr><th className="px-3 py-2">Band</th><th className="px-3 py-2">Samples</th><th className="px-3 py-2">Mean prediction</th><th className="px-3 py-2">Observed</th><th className="px-3 py-2">Brier</th></tr></thead><tbody>{completionData.buckets.map((bucket) => <tr key={`${bucket.lower_bound}-${bucket.upper_bound}`} className="border-t border-black/5"><td className="px-3 py-3">{Math.round(bucket.lower_bound * 100)}–{Math.round(bucket.upper_bound * 100)}%</td><td className="px-3 py-3">{bucket.samples}</td><td className="px-3 py-3">{pct(bucket.mean_prediction)}</td><td className="px-3 py-3">{pct(bucket.observed_completion_rate)}</td><td className="px-3 py-3">{bucket.brier_score == null ? "—" : bucket.brier_score.toFixed(3)}</td></tr>)}</tbody></table></div>
          </section>
        </section>
      )}

      {continuityData && (
        <section className="space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-ink">Schedule continuity</h2>
            <p className="mt-1 text-xs text-muted">Did every forecast-relative 24h window deliver the committed normal rate? Late catch-up never erases an earlier miss.</p>
          </div>
          <div className="grid gap-3 md:grid-cols-5">
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="text-xs uppercase tracking-wide text-muted">Labeled</div><p className="mt-3 text-2xl font-semibold text-ink">{continuityData.labeled_samples}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="text-xs uppercase tracking-wide text-muted">Brier</div><p className="mt-3 text-2xl font-semibold text-ink">{continuityData.brier_score == null ? "—" : continuityData.brier_score.toFixed(3)}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="text-xs uppercase tracking-wide text-muted">ECE</div><p className="mt-3 text-2xl font-semibold text-ink">{continuityData.expected_calibration_error == null ? "—" : continuityData.expected_calibration_error.toFixed(3)}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="text-xs uppercase tracking-wide text-muted">Predicted / observed</div><p className="mt-3 text-lg font-semibold text-ink">{pct(continuityData.mean_prediction)} / {pct(continuityData.observed_continuity_rate)}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="text-xs uppercase tracking-wide text-muted">Model health</div><p className={`mt-3 text-lg font-semibold ${statusClass(continuityData.status)}`}>{continuityData.status}</p></div>
          </div>
          <section className="overflow-hidden rounded-xl border border-black/5 bg-white shadow-sm">
            <div className="border-b border-black/5 p-4"><h3 className="text-sm font-semibold text-ink">Continuity reliability buckets</h3></div>
            <div className="overflow-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead className="bg-stone-50 text-xs text-muted"><tr><th className="px-3 py-2">Band</th><th className="px-3 py-2">Samples</th><th className="px-3 py-2">Mean prediction</th><th className="px-3 py-2">Observed continuity</th><th className="px-3 py-2">Brier</th></tr></thead><tbody>{continuityData.buckets.map((bucket) => <tr key={`${bucket.lower_bound}-${bucket.upper_bound}`} className="border-t border-black/5"><td className="px-3 py-3">{Math.round(bucket.lower_bound * 100)}–{Math.round(bucket.upper_bound * 100)}%</td><td className="px-3 py-3">{bucket.samples}</td><td className="px-3 py-3">{pct(bucket.mean_prediction)}</td><td className="px-3 py-3">{pct(bucket.observed_continuity_rate)}</td><td className="px-3 py-3">{bucket.brier_score == null ? "—" : bucket.brier_score.toFixed(3)}</td></tr>)}</tbody></table></div>
          </section>
          <div className="space-y-1 rounded-xl border border-black/5 bg-white p-4 text-xs text-muted shadow-sm">{continuityData.warnings.map((warning) => <p key={warning}>• {warning}</p>)}</div>
        </section>
      )}

      <section className="overflow-hidden rounded-xl border border-black/5 bg-white shadow-sm">
        <div className="border-b border-black/5 p-4"><h2 className="text-sm font-semibold text-ink">Label audit</h2><p className="mt-1 text-xs text-muted">Completion and continuity share the same prediction-time job cohort and intervention-clean eligibility.</p></div>
        <div className="overflow-auto">
          <table className="w-full min-w-[1350px] text-left text-sm">
            <thead className="bg-stone-50 text-xs text-muted"><tr><th className="px-3 py-2">Forecast</th><th className="px-3 py-2">Completion pred</th><th className="px-3 py-2">Continuity pred</th><th className="px-3 py-2">Required</th><th className="px-3 py-2">Actual success</th><th className="px-3 py-2">Completion</th><th className="px-3 py-2">Continuity</th><th className="px-3 py-2">Windows</th><th className="px-3 py-2">Status</th></tr></thead>
            <tbody>{(labels.data ?? []).map((item) => <tr key={item.id} className="border-t border-black/5"><td className="px-3 py-3 text-xs text-muted">{new Date(item.forecast_created_at).toLocaleString()}</td><td className="px-3 py-3">{pct(item.predicted_completion_probability)}</td><td className="px-3 py-3">{pct(item.predicted_continuity_probability)}</td><td className="px-3 py-3">{item.remaining_actions}</td><td className="px-3 py-3">{item.actual_successful_actions ?? "—"}</td><td className="px-3 py-3">{item.actual_met_sla == null ? "—" : item.actual_met_sla ? <span className="text-emerald-700">met</span> : <span className="text-red-700">missed</span>}</td><td className="px-3 py-3">{item.actual_met_continuity == null ? "—" : item.actual_met_continuity ? <span className="text-emerald-700">met</span> : <span className="text-red-700">missed</span>}</td><td className="px-3 py-3">{item.continuity_windows_total == null ? "—" : `${item.continuity_windows_met ?? 0}/${item.continuity_windows_total} · ${pct(item.actual_continuity_rate)}`}</td><td className="px-3 py-3 text-xs text-muted">{item.label_status.replace(/_/g, " ")}</td></tr>)}</tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
