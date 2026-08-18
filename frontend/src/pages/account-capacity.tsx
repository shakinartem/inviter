import { useMemo, useState } from "react";
import { Activity, AlertTriangle, Gauge, ShieldCheck, TimerReset } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useAccountCapacityRefresh, useAccountThroughputForecast } from "@/hooks/use-account-capacity";

function riskTone(risk: number) {
  if (risk >= 80) return "text-red-700";
  if (risk >= 50) return "text-amber-700";
  return "text-emerald-700";
}

export default function AccountCapacityPage() {
  const refresh = useAccountCapacityRefresh();
  const forecast = useAccountThroughputForecast();
  const [dailyLimit, setDailyLimit] = useState(30);
  const [desiredActions, setDesiredActions] = useState(1000);
  const [deadlineDays, setDeadlineDays] = useState(7);
  const data = refresh.data;
  const outlook = forecast.data;

  const sorted = useMemo(
    () => [...(data?.assessments ?? [])].sort((a, b) => b.health_score - a.health_score),
    [data],
  );

  const run = async () => {
    try {
      await refresh.mutateAsync({ campaign_daily_limit: dailyLimit, persist_snapshots: true });
    } catch {
      toast.error("Could not refresh account capacity.");
    }
  };

  const runForecast = async () => {
    try {
      await forecast.mutateAsync({ desired_actions: desiredActions, campaign_daily_limit: dailyLimit, deadline_days: deadlineDays });
    } catch {
      toast.error("Could not forecast account throughput.");
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">Account Capacity & Risk</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">
          Conservative throughput controller for connected Telegram accounts. It can only reduce configured campaign capacity or quarantine an account after transport-level risk signals; it never raises platform limits.
        </p>
      </div>

      <section className="grid gap-4 rounded-xl border border-black/5 bg-white p-5 shadow-sm lg:grid-cols-[1fr_1.4fr]">
        <div className="flex flex-wrap items-end gap-3">
          <label className="space-y-1 text-xs font-medium text-muted">Campaign daily limit / account<input type="number" min={1} max={1000} value={dailyLimit} onChange={(event) => setDailyLimit(Math.max(1, Number(event.target.value) || 1))} className="block w-52 rounded-lg border border-black/10 px-3 py-2 text-sm text-ink" /></label>
          <Button onClick={run} disabled={refresh.isPending}>{refresh.isPending ? "Assessing…" : "Refresh risk assessment"}</Button>
        </div>
        <div className="flex flex-wrap items-end gap-3 border-t border-black/5 pt-4 lg:border-l lg:border-t-0 lg:pl-5 lg:pt-0">
          <label className="space-y-1 text-xs font-medium text-muted">Desired actions<input type="number" min={1} value={desiredActions} onChange={(event) => setDesiredActions(Math.max(1, Number(event.target.value) || 1))} className="block w-40 rounded-lg border border-black/10 px-3 py-2 text-sm text-ink" /></label>
          <label className="space-y-1 text-xs font-medium text-muted">Deadline, days<input type="number" min={1} value={deadlineDays} onChange={(event) => setDeadlineDays(Math.max(1, Number(event.target.value) || 1))} className="block w-36 rounded-lg border border-black/10 px-3 py-2 text-sm text-ink" /></label>
          <Button variant="outline" onClick={runForecast} disabled={forecast.isPending}>{forecast.isPending ? "Forecasting…" : "Forecast throughput"}</Button>
        </div>
      </section>

      {outlook && (
        <section className={`rounded-xl border p-5 ${outlook.status === "ready" ? "border-emerald-200 bg-emerald-50" : "border-amber-200 bg-amber-50"}`}>
          <div className="flex items-start gap-3"><TimerReset className="mt-0.5 h-5 w-5" /><div><p className="text-xs font-semibold uppercase tracking-wide">Throughput forecast</p><h2 className="mt-1 text-xl font-semibold text-ink">{outlook.estimated_days == null ? "No safe capacity" : `${outlook.estimated_days.toFixed(2)} days estimated`}</h2><p className="mt-1 text-sm text-muted">Safe capacity: {outlook.safe_daily_capacity}/day · queued: {outlook.queued_jobs} · shortfall for {outlook.deadline_days ?? "—"}d deadline: {outlook.daily_capacity_shortfall}/day{outlook.additional_full_health_accounts_needed > 0 ? ` · ≈ ${outlook.additional_full_health_accounts_needed} additional full-health accounts at the configured cap` : ""}</p><p className="mt-2 text-xs text-muted">{outlook.warnings.map((warning) => warning.replace(/_/g, " ")).join(" · ")}</p></div></div>
        </section>
      )}

      {data && (
        <>
          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><ShieldCheck className="h-4 w-4" /> Eligible</div><p className="mt-3 text-2xl font-semibold text-ink">{data.eligible_accounts}/{data.total_accounts}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><Gauge className="h-4 w-4" /> Safe daily capacity</div><p className="mt-3 text-2xl font-semibold text-ink">{data.suggested_total_daily_capacity}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><Activity className="h-4 w-4" /> Average health</div><p className="mt-3 text-2xl font-semibold text-ink">{data.average_health_score.toFixed(1)}</p></div>
            <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted"><AlertTriangle className="h-4 w-4" /> Quarantined / queued</div><p className="mt-3 text-2xl font-semibold text-ink">{data.quarantined_accounts} / {data.queued_jobs}</p></div>
          </div>

          <section className="overflow-hidden rounded-xl border border-black/5 bg-white shadow-sm">
            <div className="border-b border-black/5 p-4"><h2 className="text-sm font-semibold text-ink">Account pool</h2><p className="mt-1 text-xs text-muted">Target/privacy errors are shown but do not poison global account health. Flood-wait, peer-flood and connector failures do.</p></div>
            <div className="overflow-auto"><table className="w-full min-w-[1200px] text-left text-sm"><thead className="bg-stone-50 text-xs text-muted"><tr><th className="px-3 py-2">Account</th><th className="px-3 py-2">Health</th><th className="px-3 py-2">Risk</th><th className="px-3 py-2">Safe/day</th><th className="px-3 py-2">Attempts 24h</th><th className="px-3 py-2">Account errors</th><th className="px-3 py-2">Target errors</th><th className="px-3 py-2">Flood waits</th><th className="px-3 py-2">Queue</th><th className="px-3 py-2">State</th><th className="px-3 py-2">Reasons</th></tr></thead><tbody>{sorted.map((item) => <tr key={item.account_id} className="border-t border-black/5 align-top"><td className="px-3 py-3"><div className="font-medium text-ink">{item.label}</div><div className="text-xs text-muted">{item.platform} · {item.status}</div></td><td className="px-3 py-3 font-semibold">{item.health_score.toFixed(1)}</td><td className={`px-3 py-3 font-semibold ${riskTone(item.risk_score)}`}>{item.risk_score.toFixed(1)}</td><td className="px-3 py-3 font-semibold">{item.suggested_daily_capacity}</td><td className="px-3 py-3">{item.attempts_24h}</td><td className="px-3 py-3">{item.account_errors_24h}</td><td className="px-3 py-3">{item.target_errors_24h}</td><td className="px-3 py-3">{item.floodwaits_24h}</td><td className="px-3 py-3">{item.queued_jobs}</td><td className="px-3 py-3">{item.eligible ? <span className="text-emerald-700">eligible</span> : <span className="text-red-700">quarantined</span>}{item.next_safe_at && <div className="mt-1 text-xs text-muted">until {new Date(item.next_safe_at).toLocaleString()}</div>}</td><td className="max-w-sm px-3 py-3 text-xs text-muted">{item.reasons.map((reason) => reason.replace(/_/g, " ")).join(" · ")}</td></tr>)}</tbody></table></div>
          </section>
        </>
      )}
    </div>
  );
}
