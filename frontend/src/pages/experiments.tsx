import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, FlaskConical, Gauge, Scale, Target } from "lucide-react";

import { useCampaigns } from "@/hooks/use-campaigns";
import { useCampaignCausalLift, useExperiments } from "@/hooks/use-experiments";

function pct(value: number) {
  return `${value.toFixed(1)}%`;
}

export default function ExperimentsPage() {
  const { data: experiments } = useExperiments();
  const { data: campaigns } = useCampaigns({ skip: 0, limit: 500 });
  const assigned = useMemo(() => (experiments ?? []).filter((item) => item.status === "assigned"), [experiments]);
  const campaignTitle = useMemo(
    () => new Map((campaigns ?? []).map((campaign) => [campaign.id, campaign.title])),
    [campaigns],
  );
  const [campaignId, setCampaignId] = useState<string | null>(null);
  const [stage, setStage] = useState("business");
  const [eventType, setEventType] = useState("converted");
  const [horizonHours, setHorizonHours] = useState(168);

  useEffect(() => {
    if (!campaignId && assigned.length) setCampaignId(assigned[0].campaign_id);
  }, [assigned, campaignId]);

  const { data: lift, isLoading, error } = useCampaignCausalLift(campaignId, {
    stage,
    event_type: eventType,
    horizon_hours: horizonHours,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">Experiments</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">
          Measure incremental action lift from randomized treatment and holdout. Denominators are intention-to-treat from assignment time; transport success is diagnostic, never a post-treatment filter.
        </p>
      </div>

      <section className="grid gap-3 rounded-xl border border-black/5 bg-white p-4 shadow-sm md:grid-cols-4">
        <label className="space-y-1 text-xs font-medium text-muted">Randomized campaign<select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={campaignId ?? ""} onChange={(event) => setCampaignId(event.target.value || null)}><option value="">Select campaign</option>{assigned.map((experiment) => <option key={experiment.id} value={experiment.campaign_id}>{campaignTitle.get(experiment.campaign_id) ?? experiment.campaign_id} · {experiment.treatment_count}/{experiment.holdout_count}</option>)}</select></label>
        <label className="space-y-1 text-xs font-medium text-muted">Stage<select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={stage} onChange={(event) => setStage(event.target.value)}><option value="business">Business</option><option value="engagement">Engagement</option></select></label>
        <label className="space-y-1 text-xs font-medium text-muted">Outcome<input className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm" value={eventType} onChange={(event) => setEventType(event.target.value)} /></label>
        <label className="space-y-1 text-xs font-medium text-muted">Observation horizon<select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={horizonHours} onChange={(event) => setHorizonHours(Number(event.target.value))}><option value={24}>24 hours</option><option value={72}>3 days</option><option value={168}>7 days</option><option value={336}>14 days</option><option value={720}>30 days</option></select></label>
      </section>

      {!campaignId ? (
        <div className="rounded-xl border border-dashed border-black/10 bg-white p-6 text-sm text-muted">Start a campaign with causal holdout first. Assignment appears here after first Start.</div>
      ) : isLoading ? (
        <div className="rounded-xl border border-black/5 bg-white p-6 text-sm text-muted">Building randomized intention-to-treat cohort…</div>
      ) : error || !lift ? (
        <div className="rounded-xl border border-amber-100 bg-amber-50 p-5 text-sm text-amber-800">This experiment cannot be analyzed yet. It may not be assigned or may not have valid randomized units.</div>
      ) : (
        <>
          <section className={`rounded-xl border p-5 ${lift.status === "positive" ? "border-emerald-200 bg-emerald-50" : lift.status === "negative" ? "border-red-200 bg-red-50" : "border-amber-200 bg-amber-50"}`}>
            <div className="flex items-start gap-3"><FlaskConical className="mt-0.5 h-5 w-5" /><div><p className="text-xs font-semibold uppercase tracking-wide">{lift.status}</p><h2 className="mt-1 text-xl font-semibold text-ink">{lift.campaign_title}</h2><p className="mt-1 text-sm text-muted">Incremental lift {lift.lift_percentage_points >= 0 ? "+" : ""}{lift.lift_percentage_points.toFixed(2)} pp · conservative interval {lift.confidence_low_percentage_points.toFixed(2)} to {lift.confidence_high_percentage_points.toFixed(2)} pp</p>{!lift.mature && <p className="mt-2 text-xs text-amber-800">Full observation horizon has not elapsed · ~{lift.hours_until_mature.toFixed(1)} hours remaining.</p>}</div></div>
          </section>

          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><Target className="h-4 w-4" /> Incremental / 1,000</div><p className="mt-3 text-2xl font-semibold text-ink">{lift.incremental_outcomes_per_1000 >= 0 ? "+" : ""}{lift.incremental_outcomes_per_1000.toFixed(1)}</p><p className="mt-1 text-xs text-muted">estimated extra outcomes caused by assignment to treatment</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="text-xs uppercase tracking-wide text-muted">Treatment</div><p className="mt-3 text-2xl font-semibold text-ink">{pct(lift.treatment.rate)}</p><p className="mt-1 text-xs text-muted">{lift.treatment.positives}/{lift.treatment.units} randomized units</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="text-xs uppercase tracking-wide text-muted">Holdout baseline</div><p className="mt-3 text-2xl font-semibold text-ink">{pct(lift.holdout.rate)}</p><p className="mt-1 text-xs text-muted">{lift.holdout.positives}/{lift.holdout.units} randomized units</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><Gauge className="h-4 w-4" /> Execution</div><p className="mt-3 text-2xl font-semibold text-ink">{pct(lift.treatment_execution_rate)}</p><p className="mt-1 text-xs text-muted">transport success {pct(lift.treatment_transport_success_rate)}</p></div>
          </div>

          <section className="rounded-xl border border-black/5 bg-white p-5 shadow-sm">
            <div className="flex items-center gap-2"><Scale className="h-4 w-4" /><h2 className="text-sm font-semibold text-ink">Randomization balance</h2></div>
            <p className="mt-1 text-xs text-muted">Frozen pre-treatment scores should be similar across arms. Standardized differences above ~0.25 are flagged as a balance warning.</p>
            <div className="mt-4 grid gap-2 md:grid-cols-3">{lift.balance.map((metric) => <div key={metric.metric} className="rounded-lg bg-stone-50 p-3"><p className="text-[10px] uppercase tracking-wide text-muted">{metric.metric.replace(/_/g, " ")}</p><div className="mt-2 flex justify-between text-xs"><span>T {metric.treatment_mean?.toFixed(1) ?? "—"}</span><span>H {metric.holdout_mean?.toFixed(1) ?? "—"}</span></div><p className="mt-2 font-semibold text-ink">SMD {metric.standardized_difference?.toFixed(3) ?? "—"}</p></div>)}</div>
          </section>

          {lift.warnings.length > 0 && <div className="flex items-start gap-2 rounded-lg bg-stone-50 p-3 text-xs text-muted"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><span>{lift.warnings.map((warning) => warning.replace(/_/g, " ")).join(" · ")}</span></div>}
        </>
      )}
    </div>
  );
}
