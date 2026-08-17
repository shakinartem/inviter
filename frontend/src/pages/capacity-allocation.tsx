import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, GitMerge, ShieldCheck, Users } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  useAllocationAssignments,
  useAllocationPlans,
  useCreateAllocationPlan,
} from "@/hooks/use-allocations";

function signed(value: number) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}`;
}

export default function CapacityAllocationPage() {
  const { data: plans, isLoading } = useAllocationPlans();
  const createPlan = useCreateAllocationPlan();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    name: "Causal capacity allocation",
    eventType: "converted",
    horizonHours: 168,
    totalCapacity: 1000,
    allocationMode: "decision_grade" as "decision_grade" | "coverage_expansion",
  });

  useEffect(() => {
    if (!selectedId && (plans?.length ?? 0) > 0) setSelectedId(plans![0].id);
  }, [plans, selectedId]);
  const selected = (plans ?? []).find((plan) => plan.id === selectedId) ?? null;
  const { data: assignments, isLoading: assignmentsLoading } = useAllocationAssignments(selectedId, 500);
  const segmentCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const item of assignments?.items ?? []) {
      counts.set(item.segment_name_snapshot, (counts.get(item.segment_name_snapshot) ?? 0) + 1);
    }
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [assignments]);

  const handleCreate = async () => {
    if (!form.name.trim()) return;
    try {
      const plan = await createPlan.mutateAsync({
        name: form.name.trim(),
        platform: "telegram",
        stage: "business",
        event_type: form.eventType.trim(),
        horizon_hours: form.horizonHours,
        total_capacity: form.totalCapacity,
        allocation_mode: form.allocationMode,
        require_positive_conservative: true,
      });
      setSelectedId(plan.id);
      setShowCreate(false);
      toast.success(`Frozen allocation created · ${plan.allocated_count} unique people`);
    } catch {
      toast.error("Could not create causal allocation. Randomized evidence may still be insufficient.");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Capacity Allocation</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted">
            Freeze one global action plan across competing Opportunities. A person can be allocated at most once; overlap is resolved toward the Opportunity with the strongest conservative incremental value.
          </p>
        </div>
        <Button size="sm" onClick={() => setShowCreate((value) => !value)}><GitMerge className="mr-1 h-4 w-4" /> New allocation</Button>
      </div>

      {showCreate && (
        <section className="space-y-4 rounded-xl border border-black/5 bg-white p-5 shadow-sm">
          <div className="grid gap-3 md:grid-cols-5">
            <label className="space-y-1 text-xs font-medium text-muted md:col-span-2">Name<input className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} /></label>
            <label className="space-y-1 text-xs font-medium text-muted">Outcome<input className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm" value={form.eventType} onChange={(event) => setForm({ ...form, eventType: event.target.value })} /></label>
            <label className="space-y-1 text-xs font-medium text-muted">Capacity<input type="number" min={1} max={50000} className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm" value={form.totalCapacity} onChange={(event) => setForm({ ...form, totalCapacity: Math.max(1, Number(event.target.value) || 1) })} /></label>
            <label className="space-y-1 text-xs font-medium text-muted">Evidence policy<select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={form.allocationMode} onChange={(event) => setForm({ ...form, allocationMode: event.target.value as typeof form.allocationMode })}><option value="decision_grade">Decision grade</option><option value="coverage_expansion">Coverage expansion</option></select></label>
            <label className="space-y-1 text-xs font-medium text-muted">Horizon<select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm" value={form.horizonHours} onChange={(event) => setForm({ ...form, horizonHours: Number(event.target.value) })}><option value={24}>24h</option><option value={72}>3d</option><option value={168}>7d</option><option value={336}>14d</option><option value={720}>30d</option></select></label>
          </div>
          <div className="rounded-lg bg-stone-50 p-3 text-xs text-muted"><strong className="text-ink">Decision grade</strong> uses replicated context, or a stable low-heterogeneity positive global causal prior. <strong className="text-ink">Coverage expansion</strong> may use labeled global fallback and is better for learning coverage than production optimization.</div>
          <div className="flex justify-end gap-2"><Button size="sm" variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button><Button size="sm" onClick={handleCreate} disabled={!form.name.trim() || createPlan.isPending}>{createPlan.isPending ? "Freezing allocation…" : "Create frozen plan"}</Button></div>
        </section>
      )}

      <section className="grid gap-4 xl:grid-cols-[0.9fr_1.6fr]">
        <div className="space-y-2">
          {isLoading ? <div className="rounded-xl border border-black/5 bg-white p-5 text-sm text-muted">Loading plans…</div> : (plans?.length ?? 0) === 0 ? <div className="rounded-xl border border-dashed border-black/10 bg-white p-6 text-sm text-muted">No frozen capacity plan yet.</div> : (plans ?? []).map((plan) => (
            <button key={plan.id} onClick={() => setSelectedId(plan.id)} className={`w-full rounded-xl border p-4 text-left shadow-sm ${selectedId === plan.id ? "border-ink bg-white" : "border-black/5 bg-white hover:border-black/15"}`}>
              <div className="flex items-start justify-between gap-3"><div><p className="font-semibold text-ink">{plan.name}</p><p className="mt-1 text-xs text-muted">{new Date(plan.frozen_at).toLocaleString()} · {plan.allocation_mode.replace(/_/g, " ")}</p></div><span className="rounded-full bg-stone-100 px-2 py-1 text-[10px] text-muted">frozen</span></div>
              <div className="mt-3 grid grid-cols-3 gap-2 text-xs"><div><span className="text-muted">Allocated</span><p className="font-semibold text-ink">{plan.allocated_count.toLocaleString()}</p></div><div><span className="text-muted">Overlap removed</span><p className="font-semibold text-ink">{plan.duplicate_offers_removed.toLocaleString()}</p></div><div><span className="text-muted">Conservative</span><p className="font-semibold text-ink">{signed(plan.conservative_incremental_outcomes)}</p></div></div>
            </button>
          ))}
        </div>

        <div className="rounded-xl border border-black/5 bg-white shadow-sm">
          {!selected ? <div className="p-6 text-sm text-muted">Select an allocation plan.</div> : (
            <>
              <div className="border-b border-black/5 p-5">
                <div className="flex items-start justify-between gap-4"><div><h2 className="text-lg font-semibold text-ink">{selected.name}</h2><p className="mt-1 text-xs text-muted">Frozen causal allocation · one person max once across competing Opportunities.</p></div><div className="text-right"><p className="text-2xl font-semibold text-ink">{selected.allocated_count.toLocaleString()}</p><p className="text-[10px] uppercase tracking-wide text-muted">of {selected.total_capacity.toLocaleString()} capacity</p></div></div>
                <div className="mt-4 grid gap-3 md:grid-cols-4"><div className="rounded-lg bg-stone-50 p-3"><p className="text-[10px] uppercase tracking-wide text-muted">Conservative incremental</p><p className="mt-1 text-xl font-semibold text-ink">{signed(selected.conservative_incremental_outcomes)}</p></div><div className="rounded-lg bg-stone-50 p-3"><p className="text-[10px] uppercase tracking-wide text-muted">Expected</p><p className="mt-1 text-xl font-semibold text-ink">{signed(selected.expected_incremental_outcomes)}</p></div><div className="rounded-lg bg-stone-50 p-3"><p className="text-[10px] uppercase tracking-wide text-muted">Replicated context</p><p className="mt-1 text-xl font-semibold text-ink">{selected.replicated_context_coverage.toFixed(1)}%</p></div><div className="rounded-lg bg-stone-50 p-3"><p className="text-[10px] uppercase tracking-wide text-muted">Unused capacity</p><p className="mt-1 text-xl font-semibold text-ink">{selected.unallocated_capacity.toLocaleString()}</p></div></div>
              </div>

              <div className="grid gap-4 p-5 lg:grid-cols-[0.8fr_1.4fr]">
                <div>
                  <div className="flex items-center gap-2"><Users className="h-4 w-4" /><h3 className="text-sm font-semibold text-ink">Allocated by Opportunity</h3></div>
                  <div className="mt-3 space-y-2">{segmentCounts.map(([name, count]) => <div key={name} className="flex items-center justify-between rounded-lg bg-stone-50 px-3 py-2 text-sm"><span className="text-ink">{name}</span><span className="font-semibold text-ink">{count}</span></div>)}</div>
                </div>
                <div>
                  <div className="flex items-center gap-2"><ShieldCheck className="h-4 w-4" /><h3 className="text-sm font-semibold text-ink">Top unique assignments</h3></div>
                  {assignmentsLoading ? <p className="mt-3 text-sm text-muted">Loading assignments…</p> : <div className="mt-3 max-h-[460px] overflow-auto rounded-lg border border-black/5"><table className="w-full text-left text-xs"><thead className="sticky top-0 bg-stone-50 text-muted"><tr><th className="px-2 py-2">#</th><th className="px-2 py-2">Opportunity</th><th className="px-2 py-2">Ready</th><th className="px-2 py-2">Signal</th><th className="px-2 py-2">Evidence</th><th className="px-2 py-2">Conservative</th></tr></thead><tbody>{(assignments?.items ?? []).map((item) => <tr key={item.id} className="border-t border-black/5"><td className="px-2 py-2">{item.allocation_rank}</td><td className="px-2 py-2 font-medium text-ink">{item.segment_name_snapshot}</td><td className="px-2 py-2">{item.readiness_score?.toFixed(1) ?? "—"}</td><td className="px-2 py-2">{item.strongest_signal_type?.replace(/_/g, " ") ?? "—"}</td><td className="px-2 py-2">{item.evidence_source.replace(/_/g, " ")}</td><td className="px-2 py-2 font-semibold">{(item.conservative_incremental_probability * 100).toFixed(2)} pp</td></tr>)}</tbody></table></div>}
                </div>
              </div>

              {(selected.warnings?.length ?? 0) > 0 && <div className="mx-5 mb-5 flex items-start gap-2 rounded-lg bg-stone-50 p-3 text-xs text-muted"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><span>{selected.warnings?.map((warning) => warning.replace(/_/g, " ")).join(" · ")}</span></div>}
            </>
          )}
        </div>
      </section>
    </div>
  );
}
