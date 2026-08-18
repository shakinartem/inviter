import { useMemo, useState } from "react";
import { Activity, Gauge, ShieldCheck, TimerReset, TrendingUp } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useCampaigns } from "@/hooks/use-campaigns";
import { useExecutionSLAForecast, useExecutionSLAHistory } from "@/hooks/use-execution-sla";

function pct(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}

export default function ExecutionSLAPage() {
  const { data: campaigns } = useCampaigns({ skip: 0, limit: 500 });
  const forecast = useExecutionSLAForecast();
  const [campaignId, setCampaignId] = useState("");
  const [remainingActions, setRemainingActions] = useState(1000);
  const [deadlineDays, setDeadlineDays] = useState(7);
  const [targetSLA, setTargetSLA] = useState(90);
  const history = useExecutionSLAHistory(campaignId || null, 20);

  const availableCampaigns = useMemo(
    () => (campaigns ?? []).filter((campaign) => ["active", "paused", "draft"].includes(campaign.status)),
    [campaigns],
  );

  const run = async () => {
    if (!campaignId) return toast.error("Select a planned campaign first.");
    try {
      const result = await forecast.mutateAsync({
        campaign_id: campaignId,
        remaining_actions: remainingActions,
        deadline_days: deadlineDays,
        target_sla: targetSLA / 100,
      });
      toast.success(
        result.recommended_scenario
          ? `Recommended reserve ${result.recommended_scenario.reserve_percentage.toFixed(0)}%`
          : "No tested reserve scenario meets the requested continuity SLA.",
      );
      await history.refetch();
    } catch {
      toast.error("Could not forecast SLA. The campaign must have an assigned account pool first.");
    }
  };

  const data = forecast.data;
  const recommended = data?.recommended_scenario ?? null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">Execution SLA</h1>
        <p className="mt-1 max-w-4xl text-sm text-muted">
          Forecast whether a campaign can sustain a promised execution rate under observed account failures. Reserve is optimized for schedule continuity subject to the workload deadline; it never creates physical Telegram capacity.
        </p>
      </div>

      <section className="rounded-xl border border-black/5 bg-white p-5 shadow-sm">
        <div className="grid gap-4 lg:grid-cols-4">
          <label className="space-y-1 text-xs font-medium text-muted">
            Planned campaign
            <select value={campaignId} onChange={(event) => setCampaignId(event.target.value)} className="block w-full rounded-lg border border-black/10 px-3 py-2 text-sm text-ink">
              <option value="">Select campaign…</option>
              {availableCampaigns.map((campaign) => <option key={campaign.id} value={campaign.id}>{campaign.title} · {campaign.status}</option>)}
            </select>
          </label>
          <label className="space-y-1 text-xs font-medium text-muted">
            Remaining actions
            <input type="number" min={1} max={1000000} value={remainingActions} onChange={(event) => setRemainingActions(Math.max(1, Number(event.target.value) || 1))} className="block w-full rounded-lg border border-black/10 px-3 py-2 text-sm text-ink" />
          </label>
          <label className="space-y-1 text-xs font-medium text-muted">
            Deadline, days
            <input type="number" min={1} max={90} value={deadlineDays} onChange={(event) => setDeadlineDays(Math.min(90, Math.max(1, Number(event.target.value) || 1)))} className="block w-full rounded-lg border border-black/10 px-3 py-2 text-sm text-ink" />
          </label>
          <label className="space-y-1 text-xs font-medium text-muted">
            Continuity SLA
            <input type="number" min={50} max={99.9} step={0.1} value={targetSLA} onChange={(event) => setTargetSLA(Math.min(99.9, Math.max(50, Number(event.target.value) || 50)))} className="block w-full rounded-lg border border-black/10 px-3 py-2 text-sm text-ink" />
          </label>
        </div>
        <div className="mt-4 flex items-center gap-3">
          <Button onClick={run} disabled={!campaignId || forecast.isPending}>{forecast.isPending ? "Simulating…" : "Forecast execution SLA"}</Button>
          <p className="text-xs text-muted">Uses a deterministic Monte Carlo comparison of reserve 0/10/20/30/40/50% plus the campaign's current reserve.</p>
        </div>
      </section>

      {data && (
        <>
          <div className="grid gap-3 md:grid-cols-5">
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><TimerReset className="h-4 w-4" /> Required/day</div><p className="mt-3 text-2xl font-semibold text-ink">{data.required_daily_rate}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><Gauge className="h-4 w-4" /> Current normal/day</div><p className="mt-3 text-2xl font-semibold text-ink">{data.current_scenario.normal_daily_capacity}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><ShieldCheck className="h-4 w-4" /> Current continuity</div><p className="mt-3 text-2xl font-semibold text-ink">{pct(data.current_scenario.conservative_schedule_continuity_probability)}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><TrendingUp className="h-4 w-4" /> Recommended reserve</div><p className="mt-3 text-2xl font-semibold text-ink">{recommended ? `${recommended.reserve_percentage.toFixed(0)}%` : "—"}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><Activity className="h-4 w-4" /> Evidence</div><p className="mt-3 text-lg font-semibold text-ink">{data.evidence_quality}</p><p className="mt-1 text-xs text-muted">{data.total_exposure_days} exposure days · {data.total_hard_failure_days} hard-failure days</p></div>
          </div>

          <section className={`rounded-xl border p-5 shadow-sm ${recommended ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50"}`}>
            <h2 className="text-sm font-semibold text-ink">{data.status.replace(/_/g, " ")}</h2>
            {recommended ? (
              <p className="mt-2 text-sm text-muted">
                At {recommended.reserve_percentage.toFixed(0)}% reserve, normal commitment is {recommended.normal_daily_capacity}/day with conservative schedule continuity {pct(recommended.conservative_schedule_continuity_probability)} and conservative fixed-workload completion {pct(recommended.conservative_workload_completion_probability)} by {new Date(data.deadline_at).toLocaleDateString()}.
              </p>
            ) : (
              <p className="mt-2 text-sm text-muted">No tested reserve level simultaneously preserves the required {data.required_daily_rate}/day workload rate and reaches the requested {pct(data.target_sla)} continuity target.</p>
            )}
          </section>

          <section className="overflow-hidden rounded-xl border border-black/5 bg-white shadow-sm">
            <div className="border-b border-black/5 p-4"><h2 className="text-sm font-semibold text-ink">Reserve scenarios</h2><p className="mt-1 text-xs text-muted">Recommendation maximizes usable throughput among scenarios that satisfy both required daily rate and conservative continuity SLA.</p></div>
            <div className="overflow-auto">
              <table className="w-full min-w-[1200px] text-left text-sm">
                <thead className="bg-stone-50 text-xs text-muted"><tr><th className="px-3 py-2">Reserve</th><th className="px-3 py-2">Normal/day</th><th className="px-3 py-2">Headroom</th><th className="px-3 py-2">Rate feasible</th><th className="px-3 py-2">Conservative continuity</th><th className="px-3 py-2">Conservative completion</th><th className="px-3 py-2">Expected actions</th><th className="px-3 py-2">SLA</th></tr></thead>
                <tbody>{data.scenarios.map((scenario) => <tr key={scenario.reserve_percentage} className={`border-t border-black/5 ${recommended?.reserve_percentage === scenario.reserve_percentage ? "bg-emerald-50/50" : ""}`}><td className="px-3 py-3 font-medium text-ink">{scenario.reserve_percentage.toFixed(0)}%</td><td className="px-3 py-3">{scenario.normal_daily_capacity}</td><td className="px-3 py-3">{scenario.reserved_headroom}</td><td className="px-3 py-3">{scenario.supports_required_daily_rate ? <span className="text-emerald-700">yes</span> : <span className="text-red-700">no</span>}</td><td className="px-3 py-3 font-medium">{pct(scenario.conservative_schedule_continuity_probability)}</td><td className="px-3 py-3">{pct(scenario.conservative_workload_completion_probability)}</td><td className="px-3 py-3">{scenario.conservative_expected_actions_by_deadline.toFixed(0)}</td><td className="px-3 py-3">{scenario.meets_target_sla ? <span className="text-emerald-700">meets</span> : <span className="text-amber-700">misses</span>}</td></tr>)}</tbody>
              </table>
            </div>
          </section>

          <section className="overflow-hidden rounded-xl border border-black/5 bg-white shadow-sm">
            <div className="border-b border-black/5 p-4"><h2 className="text-sm font-semibold text-ink">Account hazard evidence</h2></div>
            <div className="overflow-auto">
              <table className="w-full min-w-[980px] text-left text-sm">
                <thead className="bg-stone-50 text-xs text-muted"><tr><th className="px-3 py-2">Account</th><th className="px-3 py-2">Health</th><th className="px-3 py-2">Emergency/day</th><th className="px-3 py-2">Exposure days</th><th className="px-3 py-2">Hard-failure days</th><th className="px-3 py-2">Posterior hazard</th><th className="px-3 py-2">Conservative hazard</th><th className="px-3 py-2">Evidence</th></tr></thead>
                <tbody>{data.accounts.map((account) => <tr key={account.account_id} className="border-t border-black/5"><td className="px-3 py-3 font-medium text-ink">{account.label}</td><td className="px-3 py-3">{account.health_score.toFixed(1)}</td><td className="px-3 py-3">{account.emergency_daily_capacity}</td><td className="px-3 py-3">{account.exposure_days}</td><td className="px-3 py-3">{account.hard_failure_days}</td><td className="px-3 py-3">{pct(account.posterior_daily_hazard)}</td><td className="px-3 py-3">{pct(account.conservative_daily_hazard)}</td><td className="px-3 py-3">{account.evidence_quality}</td></tr>)}</tbody>
              </table>
            </div>
          </section>

          <div className="space-y-1 rounded-xl border border-black/5 bg-white p-4 text-xs text-muted shadow-sm">{data.warnings.map((warning) => <p key={warning}>• {warning}</p>)}</div>
        </>
      )}

      {campaignId && (history.data?.length ?? 0) > 0 && (
        <section className="overflow-hidden rounded-xl border border-black/5 bg-white shadow-sm">
          <div className="border-b border-black/5 p-4"><h2 className="text-sm font-semibold text-ink">Forecast history</h2><p className="mt-1 text-xs text-muted">Immutable forecast-time records for future calibration against actual completion.</p></div>
          <div className="overflow-auto">
            <table className="w-full min-w-[900px] text-left text-sm"><thead className="bg-stone-50 text-xs text-muted"><tr><th className="px-3 py-2">Created</th><th className="px-3 py-2">Deadline</th><th className="px-3 py-2">Actions</th><th className="px-3 py-2">Evidence</th><th className="px-3 py-2">Current reserve</th><th className="px-3 py-2">Recommended</th><th className="px-3 py-2">Conservative SLA</th></tr></thead><tbody>{(history.data ?? []).map((item) => <tr key={item.id} className="border-t border-black/5"><td className="px-3 py-3 text-xs text-muted">{new Date(item.created_at).toLocaleString()}</td><td className="px-3 py-3">{new Date(item.deadline_at).toLocaleDateString()}</td><td className="px-3 py-3">{item.remaining_actions}</td><td className="px-3 py-3">{item.evidence_quality}</td><td className="px-3 py-3">{item.current_reserve_percentage.toFixed(0)}%</td><td className="px-3 py-3">{item.recommended_reserve_percentage == null ? "—" : `${item.recommended_reserve_percentage.toFixed(0)}%`}</td><td className="px-3 py-3">{item.recommended_conservative_continuity_probability == null ? "—" : pct(item.recommended_conservative_continuity_probability)}</td></tr>)}</tbody></table>
          </div>
        </section>
      )}
    </div>
  );
}
