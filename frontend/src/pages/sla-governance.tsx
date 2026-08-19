import { useMemo } from "react";
import { CheckCircle2, FlaskConical, Power, ShieldCheck, TriangleAlert } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  useActivateSLACalibrator,
  useRetireSLACalibrator,
  useSLACalibrators,
  useTrainSLACalibrator,
} from "@/hooks/use-sla-governance";

function delta(before: number, after: number) {
  const value = after - before;
  return `${value >= 0 ? "+" : ""}${value.toFixed(3)}`;
}

export default function SLAGovernancePage() {
  const calibrators = useSLACalibrators();
  const train = useTrainSLACalibrator();
  const activate = useActivateSLACalibrator();
  const retire = useRetireSLACalibrator();

  const items = useMemo(() => calibrators.data ?? [], [calibrators.data]);
  const active = items.find((item) => item.status === "active") ?? null;

  const trainNow = async () => {
    try {
      const result = await train.mutateAsync();
      if (!result.calibrator) {
        toast.warning(`Need ${result.minimum_required} clean labels; currently ${result.eligible_samples}.`);
      } else if (result.calibrator.activation_eligible) {
        toast.success("Candidate passed chronological holdout governance.");
      } else {
        toast.warning("Candidate was trained but failed holdout governance; activation is blocked.");
      }
    } catch {
      toast.error("Could not train SLA calibrator.");
    }
  };

  const activateModel = async (id: string) => {
    try {
      await activate.mutateAsync(id);
      toast.success("Calibrator activated. Raw model remains stored for audit/rollback.");
    } catch {
      toast.error("Activation blocked or failed.");
    }
  };

  const retireModel = async (id: string) => {
    try {
      await retire.mutateAsync(id);
      toast.success("Calibrator retired; forecasts fall back to raw execution-sla-v1 point probability.");
    } catch {
      toast.error("Could not retire calibrator.");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-ink">SLA Model Governance</h1>
          <p className="mt-1 max-w-4xl text-sm text-muted">
            Versioned probability calibration with chronological holdout validation. Candidates cannot activate on small samples or in-sample improvement alone.
          </p>
        </div>
        <Button onClick={trainNow} disabled={train.isPending}>
          <FlaskConical className="mr-2 h-4 w-4" /> {train.isPending ? "Training…" : "Train candidate"}
        </Button>
      </div>

      <section className="grid gap-3 md:grid-cols-3">
        <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm">
          <p className="text-xs uppercase tracking-wide text-muted">Production point forecast</p>
          <p className="mt-3 text-lg font-semibold text-ink">{active?.calibrator_version ?? "raw execution-sla-v1"}</p>
          <p className="mt-1 text-xs text-muted">Safety bounds and reserve recommendations never use this calibration layer.</p>
        </div>
        <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm">
          <p className="text-xs uppercase tracking-wide text-muted">Activation floor</p>
          <p className="mt-3 text-2xl font-semibold text-ink">100 clean labels</p>
          <p className="mt-1 text-xs text-muted">Newest 20% are held out chronologically.</p>
        </div>
        <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm">
          <p className="text-xs uppercase tracking-wide text-muted">Governance rule</p>
          <div className="mt-3 flex items-center gap-2 text-sm font-semibold text-ink"><ShieldCheck className="h-4 w-4" /> No worse holdout quality</div>
          <p className="mt-1 text-xs text-muted">Brier, ECE and absolute bias must stay within strict tolerances.</p>
        </div>
      </section>

      <section className="overflow-hidden rounded-xl border border-black/5 bg-white shadow-sm">
        <div className="border-b border-black/5 p-4">
          <h2 className="text-sm font-semibold text-ink">Calibrator versions</h2>
          <p className="mt-1 text-xs text-muted">Training uses only mature `labeled` forecasts; intervened, invalid-queue and pending snapshots never enter fitting.</p>
        </div>
        <div className="overflow-auto">
          <table className="w-full min-w-[1280px] text-left text-sm">
            <thead className="bg-stone-50 text-xs text-muted"><tr><th className="px-3 py-2">Version</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">Train / test</th><th className="px-3 py-2">Brier raw → cal</th><th className="px-3 py-2">ECE raw → cal</th><th className="px-3 py-2">Bias raw → cal</th><th className="px-3 py-2">Holdout</th><th className="px-3 py-2">Action</th></tr></thead>
            <tbody>{items.map((item) => <tr key={item.id} className="border-t border-black/5 align-top"><td className="px-3 py-3"><div className="font-medium text-ink">{item.calibrator_version}</div><div className="text-[10px] text-muted">trained {new Date(item.trained_at).toLocaleString()}</div></td><td className="px-3 py-3"><span className={item.status === "active" ? "text-emerald-700" : item.status === "retired" ? "text-muted" : "text-amber-700"}>{item.status}</span></td><td className="px-3 py-3">{item.train_count} / {item.test_count}<div className="text-[10px] text-muted">total {item.sample_count}</div></td><td className="px-3 py-3">{item.raw_brier_test.toFixed(3)} → {item.calibrated_brier_test.toFixed(3)}<div className={`text-[10px] ${item.calibrated_brier_test <= item.raw_brier_test ? "text-emerald-700" : "text-red-700"}`}>{delta(item.raw_brier_test, item.calibrated_brier_test)}</div></td><td className="px-3 py-3">{item.raw_ece_test.toFixed(3)} → {item.calibrated_ece_test.toFixed(3)}<div className={`text-[10px] ${item.calibrated_ece_test <= item.raw_ece_test ? "text-emerald-700" : "text-red-700"}`}>{delta(item.raw_ece_test, item.calibrated_ece_test)}</div></td><td className="px-3 py-3">{item.raw_bias_test.toFixed(3)} → {item.calibrated_bias_test.toFixed(3)}</td><td className="px-3 py-3">{item.activation_eligible ? <span className="inline-flex items-center gap-1 text-emerald-700"><CheckCircle2 className="h-3.5 w-3.5" /> eligible</span> : <span className="inline-flex items-center gap-1 text-amber-700"><TriangleAlert className="h-3.5 w-3.5" /> blocked</span>}</td><td className="px-3 py-3">{item.status === "active" ? <Button size="sm" variant="outline" onClick={() => retireModel(item.id)} disabled={retire.isPending}>Retire</Button> : item.status === "candidate" && item.activation_eligible ? <Button size="sm" onClick={() => activateModel(item.id)} disabled={activate.isPending}><Power className="mr-1 h-3.5 w-3.5" /> Activate</Button> : "—"}</td></tr>)}</tbody>
          </table>
        </div>
        {items.length === 0 && <p className="p-6 text-sm text-muted">No calibrators yet. Training remains blocked until at least 100 intervention-clean mature forecasts exist.</p>}
      </section>

      {items[0]?.mapping?.length ? (
        <section className="overflow-hidden rounded-xl border border-black/5 bg-white shadow-sm">
          <div className="border-b border-black/5 p-4"><h2 className="text-sm font-semibold text-ink">Latest monotonic mapping</h2><p className="mt-1 text-xs text-muted">Sparse bins are shrunk toward identity before monotonic pooling.</p></div>
          <div className="overflow-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead className="bg-stone-50 text-xs text-muted"><tr><th className="px-3 py-2">Raw band</th><th className="px-3 py-2">Samples</th><th className="px-3 py-2">Mean raw</th><th className="px-3 py-2">Observed train</th><th className="px-3 py-2">Calibrated</th></tr></thead><tbody>{items[0].mapping.map((bin) => <tr key={`${bin.lower_bound}-${bin.upper_bound}`} className="border-t border-black/5"><td className="px-3 py-3">{Math.round(bin.lower_bound * 100)}–{Math.round(bin.upper_bound * 100)}%</td><td className="px-3 py-3">{bin.samples}</td><td className="px-3 py-3">{(bin.mean_raw_prediction * 100).toFixed(1)}%</td><td className="px-3 py-3">{bin.observed_rate == null ? "—" : `${(bin.observed_rate * 100).toFixed(1)}%`}</td><td className="px-3 py-3 font-medium text-ink">{(bin.calibrated_probability * 100).toFixed(1)}%</td></tr>)}</tbody></table></div>
        </section>
      ) : null}
    </div>
  );
}
