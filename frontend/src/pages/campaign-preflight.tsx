import { useMemo, useState } from "react";
import { CheckCircle2, Play, RefreshCw, ShieldAlert, TriangleAlert } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useCampaignPreflight, useStartWithFreshPreflight } from "@/hooks/use-campaign-preflight";
import { useCampaigns } from "@/hooks/use-campaigns";
import { useExperiments } from "@/hooks/use-experiments";

function decisionClasses(decision: string) {
  if (decision === "go") return "border-emerald-200 bg-emerald-50 text-emerald-800";
  if (decision === "block") return "border-red-200 bg-red-50 text-red-800";
  return "border-amber-200 bg-amber-50 text-amber-800";
}

export default function CampaignPreflightPage() {
  const { data: campaigns } = useCampaigns({ skip: 0, limit: 500 });
  const { data: experiments } = useExperiments();
  const preflight = useCampaignPreflight();
  const launch = useStartWithFreshPreflight();
  const [campaignId, setCampaignId] = useState("");
  const [actionBudget, setActionBudget] = useState(1000);
  const [deadlineDays, setDeadlineDays] = useState(7);

  const availableCampaigns = useMemo(
    () => (campaigns ?? []).filter((campaign) => ["draft", "paused"].includes(campaign.status)),
    [campaigns],
  );
  const experiment = useMemo(
    () => (experiments ?? []).find((item) => item.campaign_id === campaignId) ?? null,
    [experiments, campaignId],
  );
  const currentBudget = experiment?.action_budget ?? actionBudget;

  const runPreflight = async () => {
    if (!campaignId) return toast.error("Select a campaign first.");
    try {
      const result = await preflight.mutateAsync({
        campaign_id: campaignId,
        action_budget: currentBudget,
        deadline_days: deadlineDays,
      });
      if (result.decision === "go") toast.success("Preflight: GO");
      else if (result.decision === "block") toast.error("Preflight blocked launch. Resolve blocking checks first.");
      else toast.warning("Preflight: GO with guards. Review warnings before launch.");
    } catch {
      toast.error("Could not run execution preflight.");
    }
  };

  const startWithFreshPreflight = async () => {
    const preview = preflight.data;
    if (!preview || preview.decision === "block") return;
    try {
      const result = await launch.mutateAsync({
        campaign_id: preview.campaign_id,
        action_budget: currentBudget,
        deadline_days: deadlineDays,
      });
      toast.success(
        `Fresh preflight ${result.preflight.decision.toUpperCase()} · campaign started · ${result.plan.planned} actions`,
      );
      preflight.reset();
    } catch {
      toast.error("Fresh server-side preflight blocked or launch state changed. Review and run preflight again.");
    }
  };

  const data = preflight.data;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">Campaign Execution Preflight</h1>
        <p className="mt-1 max-w-4xl text-sm text-muted">
          One launch decision over the frozen Opportunity, causal holdout, destination, risk-adjusted account pool, deadline capacity, N-1 resilience and production model health. Start re-runs preflight server-side immediately before planning.
        </p>
      </div>

      <section className="rounded-xl border border-black/5 bg-white p-5 shadow-sm">
        <div className="grid gap-4 lg:grid-cols-3">
          <label className="space-y-1 text-xs font-medium text-muted">
            Campaign
            <select value={campaignId} onChange={(event) => { setCampaignId(event.target.value); preflight.reset(); }} className="block w-full rounded-lg border border-black/10 px-3 py-2 text-sm text-ink">
              <option value="">Select draft/paused campaign…</option>
              {availableCampaigns.map((campaign) => <option key={campaign.id} value={campaign.id}>{campaign.title} · {campaign.status}</option>)}
            </select>
          </label>
          <label className="space-y-1 text-xs font-medium text-muted">
            Treatment action budget
            <input type="number" min={1} max={50000} value={currentBudget} disabled={experiment?.status === "assigned"} onChange={(event) => setActionBudget(Math.max(1, Number(event.target.value) || 1))} className="block w-full rounded-lg border border-black/10 px-3 py-2 text-sm text-ink disabled:bg-stone-50" />
            {experiment?.status === "assigned" && <span className="text-[10px] text-muted">Frozen by causal assignment.</span>}
          </label>
          <label className="space-y-1 text-xs font-medium text-muted">
            Execution deadline, days
            <input type="number" min={1} max={90} value={deadlineDays} onChange={(event) => setDeadlineDays(Math.min(90, Math.max(1, Number(event.target.value) || 1)))} className="block w-full rounded-lg border border-black/10 px-3 py-2 text-sm text-ink" />
          </label>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button onClick={runPreflight} disabled={!campaignId || preflight.isPending}>
            <RefreshCw className="mr-2 h-4 w-4" /> {preflight.isPending ? "Evaluating…" : "Run preflight"}
          </Button>
          {data && data.decision !== "block" && (
            <Button variant="outline" onClick={startWithFreshPreflight} disabled={launch.isPending}>
              <Play className="mr-2 h-4 w-4" /> {launch.isPending ? "Rechecking & starting…" : "Fresh preflight & Start"}
            </Button>
          )}
        </div>
      </section>

      {data && (
        <>
          <section className={`rounded-xl border p-5 shadow-sm ${decisionClasses(data.decision)}`}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.18em]">Launch decision</p>
                <h2 className="mt-2 text-3xl font-semibold">{data.decision.replace(/_/g, " ").toUpperCase()}</h2>
                <p className="mt-2 text-sm opacity-80">{data.campaign_title} → {data.destination_title ?? "destination"}</p>
              </div>
              {data.decision === "go" ? <CheckCircle2 className="h-7 w-7" /> : data.decision === "block" ? <ShieldAlert className="h-7 w-7" /> : <TriangleAlert className="h-7 w-7" />}
            </div>
          </section>

          <div className="grid gap-3 md:grid-cols-4 lg:grid-cols-6">
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><p className="text-[10px] uppercase tracking-wide text-muted">Executable actions</p><p className="mt-2 text-2xl font-semibold text-ink">{data.action_budget_executable}</p><p className="text-xs text-muted">requested {data.action_budget_requested}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><p className="text-[10px] uppercase tracking-wide text-muted">Required/day</p><p className="mt-2 text-2xl font-semibold text-ink">{data.required_daily_rate}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><p className="text-[10px] uppercase tracking-wide text-muted">Normal/day</p><p className="mt-2 text-2xl font-semibold text-ink">{data.normal_daily_capacity}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><p className="text-[10px] uppercase tracking-wide text-muted">Failover headroom</p><p className="mt-2 text-2xl font-semibold text-ink">{data.reserved_failover_headroom}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><p className="text-[10px] uppercase tracking-wide text-muted">N-1 surviving/day</p><p className="mt-2 text-2xl font-semibold text-ink">{data.n_minus_one_surviving_capacity}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><p className="text-[10px] uppercase tracking-wide text-muted">Eligible accounts</p><p className="mt-2 text-2xl font-semibold text-ink">{data.eligible_accounts}</p><p className="text-xs text-muted">{data.quarantined_accounts} excluded</p></div>
          </div>

          <section className="rounded-xl border border-black/5 bg-white p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-ink">Launch checks</h2>
            <div className="mt-4 space-y-2">
              {data.checks.map((check) => (
                <div key={check.key} className="flex items-start gap-3 rounded-lg border border-black/5 p-3">
                  <span className={`mt-0.5 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${check.status === "pass" ? "bg-emerald-100 text-emerald-800" : check.status === "block" ? "bg-red-100 text-red-800" : "bg-amber-100 text-amber-800"}`}>{check.status}</span>
                  <div><p className="text-sm font-medium text-ink">{check.title}</p><p className="mt-0.5 text-xs text-muted">{check.message}</p></div>
                </div>
              ))}
            </div>
          </section>

          <section className="overflow-hidden rounded-xl border border-black/5 bg-white shadow-sm">
            <div className="border-b border-black/5 p-4"><h2 className="text-sm font-semibold text-ink">Evaluated account pool</h2><p className="mt-1 text-xs text-muted">Launch re-runs the same policy immediately before Start and passes the freshly evaluated account IDs into the planner.</p></div>
            <div className="overflow-auto"><table className="w-full min-w-[900px] text-left text-sm"><thead className="bg-stone-50 text-xs text-muted"><tr><th className="px-3 py-2">Account</th><th className="px-3 py-2">Health</th><th className="px-3 py-2">Risk</th><th className="px-3 py-2">Normal/day</th><th className="px-3 py-2">Emergency/day</th><th className="px-3 py-2">Queued</th><th className="px-3 py-2">Signals</th></tr></thead><tbody>{data.accounts.map((account) => <tr key={account.account_id} className="border-t border-black/5"><td className="px-3 py-3 font-medium text-ink">{account.label}</td><td className="px-3 py-3">{account.health_score.toFixed(1)}</td><td className="px-3 py-3">{account.risk_score.toFixed(1)}</td><td className="px-3 py-3">{account.normal_daily_capacity}</td><td className="px-3 py-3">{account.emergency_daily_capacity}</td><td className="px-3 py-3">{account.queued_jobs}</td><td className="px-3 py-3 text-xs text-muted">{account.reasons.slice(0, 2).join(", ")}</td></tr>)}</tbody></table></div>
          </section>

          <div className="space-y-1 rounded-xl border border-black/5 bg-white p-4 text-xs text-muted shadow-sm">
            <p>Frozen cohort {data.frozen_cohort_size} · eligible candidate pool {data.eligible_candidate_pool}/{data.required_candidate_pool} · holdout {data.holdout_percentage.toFixed(1)}%</p>
            <p>Estimated normal completion {data.estimated_completion_days == null ? "—" : `${data.estimated_completion_days.toFixed(2)} days`} · model health {data.model_health_status}{data.active_calibrator_version ? ` · ${data.active_calibrator_version}` : ""}</p>
            {data.warnings.map((warning) => <p key={warning}>• {warning}</p>)}
          </div>
        </>
      )}
    </div>
  );
}
