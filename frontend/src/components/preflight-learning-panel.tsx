import { RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  useFinalizePreflightDecisions,
  usePreflightDecisionHistory,
  usePreflightDecisionPerformance,
} from "@/hooks/use-campaign-preflight";

function pct(value: number | null) {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
}

export function PreflightLearningPanel() {
  const performance = usePreflightDecisionPerformance();
  const history = usePreflightDecisionHistory(null, 25);
  const finalize = useFinalizePreflightDecisions();
  const data = performance.data;

  const finalizeNow = async () => {
    try {
      const result = await finalize.mutateAsync(500);
      toast.success(`Finalized ${result.labeled} launch outcomes · ${result.ineligible} excluded`);
    } catch {
      toast.error("Could not finalize mature preflight launch outcomes.");
    }
  };

  return (
    <section className="space-y-4 rounded-xl border border-black/5 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-ink">Launch decision learning</h2>
          <p className="mt-1 max-w-3xl text-xs text-muted">
            Factual outcomes for real launches only. This is observational evidence about the current preflight policy, not a causal estimate of what would have happened under a different decision.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={finalizeNow} disabled={finalize.isPending}>
          <RefreshCw className="mr-1 h-3.5 w-3.5" /> {finalize.isPending ? "Finalizing…" : "Finalize mature launches"}
        </Button>
      </div>

      {data && (
        <>
          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-lg bg-stone-50 p-3"><p className="text-[10px] uppercase tracking-wide text-muted">Labeled launches</p><p className="mt-1 text-xl font-semibold text-ink">{data.labeled_launches}</p></div>
            <div className="rounded-lg bg-stone-50 p-3"><p className="text-[10px] uppercase tracking-wide text-muted">Policy evidence</p><p className="mt-1 text-lg font-semibold text-ink">{data.status}</p></div>
            <div className="rounded-lg bg-stone-50 p-3"><p className="text-[10px] uppercase tracking-wide text-muted">Excluded</p><p className="mt-1 text-xl font-semibold text-ink">{data.ineligible_launches}</p></div>
            <div className="rounded-lg bg-stone-50 p-3"><p className="text-[10px] uppercase tracking-wide text-muted">Mature pending</p><p className="mt-1 text-xl font-semibold text-ink">{data.pending_mature_launches}</p></div>
          </div>

          <div className="overflow-auto rounded-lg border border-black/5">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="bg-stone-50 text-xs text-muted"><tr><th className="px-3 py-2">Decision</th><th className="px-3 py-2">Launches</th><th className="px-3 py-2">Mean completion</th><th className="px-3 py-2">All jobs by deadline</th><th className="px-3 py-2">Mean normal/day</th><th className="px-3 py-2">N-1 coverage</th></tr></thead>
              <tbody>{data.by_decision.map((row) => <tr key={row.decision} className="border-t border-black/5"><td className="px-3 py-3 font-medium text-ink">{row.decision.replace(/_/g, " ")}</td><td className="px-3 py-3">{row.labeled_launches}</td><td className="px-3 py-3">{pct(row.mean_completion_rate)}</td><td className="px-3 py-3">{pct(row.plan_success_rate)}</td><td className="px-3 py-3">{row.mean_normal_daily_capacity?.toFixed(1) ?? "—"}</td><td className="px-3 py-3">{pct(row.n_minus_one_coverage_rate)}</td></tr>)}</tbody>
            </table>
          </div>
          <div className="space-y-1 text-xs text-muted">{data.warnings.map((warning) => <p key={warning}>• {warning}</p>)}</div>
        </>
      )}

      <div className="overflow-auto rounded-lg border border-black/5">
        <table className="w-full min-w-[1050px] text-left text-sm">
          <thead className="bg-stone-50 text-xs text-muted"><tr><th className="px-3 py-2">Launched</th><th className="px-3 py-2">Decision</th><th className="px-3 py-2">Tracked jobs</th><th className="px-3 py-2">Required/day</th><th className="px-3 py-2">Normal/day</th><th className="px-3 py-2">Outcome</th><th className="px-3 py-2">Completion</th><th className="px-3 py-2">Deadline</th></tr></thead>
          <tbody>{(history.data ?? []).map((item) => <tr key={item.id} className="border-t border-black/5"><td className="px-3 py-3 text-xs text-muted">{new Date(item.launched_at).toLocaleString()}</td><td className="px-3 py-3">{item.decision.replace(/_/g, " ")}</td><td className="px-3 py-3">{item.tracked_jobs}</td><td className="px-3 py-3">{item.required_daily_rate}</td><td className="px-3 py-3">{item.normal_daily_capacity}</td><td className="px-3 py-3">{item.label_status === "labeled" ? (item.actual_met_execution_plan ? <span className="text-emerald-700">met plan</span> : <span className="text-red-700">missed plan</span>) : <span className="text-muted">{item.label_status.replace(/_/g, " ")}</span>}</td><td className="px-3 py-3">{pct(item.actual_completion_rate)}</td><td className="px-3 py-3 text-xs text-muted">{new Date(item.deadline_at).toLocaleString()}</td></tr>)}</tbody>
        </table>
      </div>
    </section>
  );
}
