import { useMemo, useState } from "react";
import { ArrowRightLeft, RefreshCw, ShieldAlert, Workflow } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useAccountCapacityRefresh } from "@/hooks/use-account-capacity";
import {
  useAdaptiveEvents,
  useAdaptivePreview,
  useAdaptiveRebalance,
} from "@/hooks/use-adaptive-execution";

export default function AdaptiveExecutionPage() {
  const capacity = useAccountCapacityRefresh();
  const preview = useAdaptivePreview();
  const rebalance = useAdaptiveRebalance();
  const events = useAdaptiveEvents(50);
  const [dailyLimit, setDailyLimit] = useState(30);
  const [sourceAccountId, setSourceAccountId] = useState("");
  const [maxJobs, setMaxJobs] = useState(500);

  const accounts = useMemo(
    () => [...(capacity.data?.assessments ?? [])].sort((a, b) => b.risk_score - a.risk_score),
    [capacity.data],
  );
  const selected = accounts.find((item) => item.account_id === sourceAccountId) ?? null;
  const plan = rebalance.data ?? preview.data;

  const assess = async () => {
    try {
      const data = await capacity.mutateAsync({
        campaign_daily_limit: dailyLimit,
        persist_snapshots: true,
      });
      if (!sourceAccountId) {
        const firstRisky = data.assessments.find((item) => !item.eligible || item.risk_score > 0);
        if (firstRisky) setSourceAccountId(firstRisky.account_id);
      }
    } catch {
      toast.error("Could not assess account pool.");
    }
  };

  const runPreview = async () => {
    if (!sourceAccountId) return toast.error("Select a source account first.");
    try {
      await preview.mutateAsync({
        source_account_id: sourceAccountId,
        max_jobs: maxJobs,
        reason: "manual_preview",
      });
    } catch {
      toast.error("Could not build failover preview.");
    }
  };

  const execute = async () => {
    if (!sourceAccountId) return toast.error("Select a source account first.");
    try {
      const result = await rebalance.mutateAsync({
        source_account_id: sourceAccountId,
        max_jobs: maxJobs,
        reason: "manual_rebalance",
      });
      toast.success(`Reassigned ${result.moved_jobs} untouched jobs.`);
      await events.refetch();
    } catch {
      toast.error("Adaptive rebalance failed.");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">Adaptive Execution</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">
          Self-healing failover for planned Telegram actions. Only jobs with zero attempts can move;
          retry/started work stays pinned to avoid ambiguous duplicate actions.
        </p>
      </div>

      <section className="rounded-xl border border-black/5 bg-white p-5 shadow-sm">
        <div className="grid gap-4 lg:grid-cols-4">
          <label className="space-y-1 text-xs font-medium text-muted">
            Campaign daily cap / account
            <input
              type="number"
              min={1}
              max={1000}
              value={dailyLimit}
              onChange={(event) => setDailyLimit(Math.max(1, Number(event.target.value) || 1))}
              className="block w-full rounded-lg border border-black/10 px-3 py-2 text-sm text-ink"
            />
          </label>
          <label className="space-y-1 text-xs font-medium text-muted lg:col-span-2">
            Source account to drain
            <select
              value={sourceAccountId}
              onChange={(event) => setSourceAccountId(event.target.value)}
              className="block w-full rounded-lg border border-black/10 px-3 py-2 text-sm text-ink"
            >
              <option value="">Select account…</option>
              {accounts.map((item) => (
                <option key={item.account_id} value={item.account_id}>
                  {item.label} · risk {item.risk_score.toFixed(0)} · {item.eligible ? "eligible" : "quarantined"}
                </option>
              ))}
            </select>
          </label>
          <label className="space-y-1 text-xs font-medium text-muted">
            Max jobs per rebalance
            <input
              type="number"
              min={1}
              max={2000}
              value={maxJobs}
              onChange={(event) => setMaxJobs(Math.min(2000, Math.max(1, Number(event.target.value) || 1)))}
              className="block w-full rounded-lg border border-black/10 px-3 py-2 text-sm text-ink"
            />
          </label>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button onClick={assess} disabled={capacity.isPending}>
            <RefreshCw className="mr-2 h-4 w-4" /> Assess pool
          </Button>
          <Button variant="outline" onClick={runPreview} disabled={!sourceAccountId || preview.isPending}>
            Preview failover
          </Button>
          <Button onClick={execute} disabled={!sourceAccountId || rebalance.isPending}>
            <ArrowRightLeft className="mr-2 h-4 w-4" /> Rebalance untouched jobs
          </Button>
        </div>
        {selected && (
          <p className="mt-3 text-xs text-muted">
            Selected: <span className="font-medium text-ink">{selected.label}</span> · health {selected.health_score.toFixed(1)} · risk {selected.risk_score.toFixed(1)} · safe/day {selected.suggested_daily_capacity}
          </p>
        )}
      </section>

      {plan && (
        <>
          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm">
              <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><Workflow className="h-4 w-4" /> Movable</div>
              <p className="mt-3 text-2xl font-semibold text-ink">{plan.movable_jobs}</p>
            </div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm">
              <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><ArrowRightLeft className="h-4 w-4" /> Reassigned</div>
              <p className="mt-3 text-2xl font-semibold text-ink">{plan.moved_jobs}</p>
            </div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm">
              <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><ShieldAlert className="h-4 w-4" /> Pinned</div>
              <p className="mt-3 text-2xl font-semibold text-ink">{plan.untouched_started_or_retry_jobs}</p>
            </div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm">
              <div className="text-xs uppercase tracking-wide text-muted">No safe target</div>
              <p className="mt-3 text-2xl font-semibold text-ink">{plan.no_safe_target_jobs}</p>
            </div>
          </div>

          <section className="overflow-hidden rounded-xl border border-black/5 bg-white shadow-sm">
            <div className="border-b border-black/5 p-4">
              <h2 className="text-sm font-semibold text-ink">Failover plan</h2>
              <p className="mt-1 text-xs text-muted">
                New schedules are never earlier than the original schedule and stay under risk-adjusted daily capacity.
              </p>
            </div>
            <div className="overflow-auto">
              <table className="w-full min-w-[1000px] text-left text-sm">
                <thead className="bg-stone-50 text-xs text-muted">
                  <tr><th className="px-3 py-2">From</th><th className="px-3 py-2">To</th><th className="px-3 py-2">Old schedule</th><th className="px-3 py-2">New schedule</th><th className="px-3 py-2">Target health</th><th className="px-3 py-2">Safe/day</th></tr>
                </thead>
                <tbody>
                  {plan.moves.slice(0, 200).map((move) => (
                    <tr key={move.job_id} className="border-t border-black/5">
                      <td className="px-3 py-3">{move.from_account_label}</td>
                      <td className="px-3 py-3 font-medium text-ink">{move.to_account_label}</td>
                      <td className="px-3 py-3 text-xs text-muted">{new Date(move.previous_scheduled_at).toLocaleString()}</td>
                      <td className="px-3 py-3 text-xs text-muted">{new Date(move.new_scheduled_at).toLocaleString()}</td>
                      <td className="px-3 py-3">{move.target_health_score.toFixed(1)}</td>
                      <td className="px-3 py-3">{move.target_daily_capacity}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      <section className="overflow-hidden rounded-xl border border-black/5 bg-white shadow-sm">
        <div className="border-b border-black/5 p-4">
          <h2 className="text-sm font-semibold text-ink">Recent assignment events</h2>
          <p className="mt-1 text-xs text-muted">Immutable audit trail of pre-execution account changes.</p>
        </div>
        <div className="overflow-auto">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead className="bg-stone-50 text-xs text-muted"><tr><th className="px-3 py-2">Time</th><th className="px-3 py-2">Reason</th><th className="px-3 py-2">From account</th><th className="px-3 py-2">To account</th><th className="px-3 py-2">Schedule shift</th></tr></thead>
            <tbody>
              {(events.data ?? []).map((event) => (
                <tr key={event.id} className="border-t border-black/5">
                  <td className="px-3 py-3 text-xs text-muted">{new Date(event.created_at).toLocaleString()}</td>
                  <td className="px-3 py-3">{event.reason.replace(/_/g, " ")}</td>
                  <td className="px-3 py-3 font-mono text-xs">{event.from_account_id.slice(0, 8)}</td>
                  <td className="px-3 py-3 font-mono text-xs">{event.to_account_id.slice(0, 8)}</td>
                  <td className="px-3 py-3 text-xs text-muted">{new Date(event.previous_scheduled_at).toLocaleString()} → {new Date(event.new_scheduled_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
