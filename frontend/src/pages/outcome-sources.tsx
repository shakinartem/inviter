import { useState } from "react";
import { Copy, KeyRound, PlugZap, RotateCw, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  useCreateOutcomeSource,
  useOutcomeSources,
  useRotateOutcomeSourceSecret,
  useUpdateOutcomeSource,
  type OutcomeSourceSecret,
} from "@/hooks/use-outcome-sources";

export default function OutcomeSourcesPage() {
  const { data: sources, isLoading } = useOutcomeSources();
  const createSource = useCreateOutcomeSource();
  const updateSource = useUpdateOutcomeSource();
  const rotateSecret = useRotateOutcomeSourceSecret();
  const [showCreate, setShowCreate] = useState(false);
  const [revealed, setRevealed] = useState<OutcomeSourceSecret | null>(null);
  const [name, setName] = useState("CRM / Integrator");
  const [eventTypes, setEventTypes] = useState("converted,payment_received,appointment_booked");

  const copy = async (value: string, label: string) => {
    await navigator.clipboard.writeText(value);
    toast.success(`${label} copied`);
  };

  const handleCreate = async () => {
    if (!name.trim()) return;
    try {
      const result = await createSource.mutateAsync({
        name: name.trim(),
        allowed_event_types: eventTypes.split(",").map((value) => value.trim()).filter(Boolean),
      });
      setRevealed(result);
      setShowCreate(false);
      toast.success("Outcome source created. Save the signing secret now.");
    } catch {
      toast.error("Could not create outcome source. Check APP_SECRET and source settings.");
    }
  };

  const handleRotate = async (id: string) => {
    try {
      const result = await rotateSecret.mutateAsync(id);
      setRevealed(result);
      toast.success("Signing secret rotated. The old secret is invalid now.");
    } catch {
      toast.error("Could not rotate signing secret");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Outcome Sources</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted">
            Connect CRM, Integrator or other downstream systems that can verify what happened after an action.
            Signed outcomes become calibration data; transport success is never accepted through this channel.
          </p>
        </div>
        <Button size="sm" onClick={() => setShowCreate((value) => !value)}>
          <PlugZap className="mr-1 h-4 w-4" /> New source
        </Button>
      </div>

      {revealed && (
        <section className="rounded-xl border border-amber-200 bg-amber-50 p-5">
          <div className="flex items-start gap-3">
            <KeyRound className="mt-0.5 h-5 w-5 text-amber-700" />
            <div className="min-w-0 flex-1">
              <h2 className="text-sm font-semibold text-ink">Save this signing secret now</h2>
              <p className="mt-1 text-xs text-muted">
                It is returned only after create/rotate and is stored encrypted on the server. A later GET never exposes it.
              </p>
              <div className="mt-3 grid gap-2 lg:grid-cols-2">
                <div className="rounded-lg border border-amber-200 bg-white p-3">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-muted">Webhook path</p>
                  <div className="mt-1 flex items-center gap-2">
                    <code className="min-w-0 flex-1 overflow-hidden text-ellipsis text-xs">{revealed.webhook_path}</code>
                    <Button size="sm" variant="ghost" onClick={() => copy(revealed.webhook_path, "Webhook path")}><Copy className="h-3.5 w-3.5" /></Button>
                  </div>
                </div>
                <div className="rounded-lg border border-amber-200 bg-white p-3">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-muted">Signing secret</p>
                  <div className="mt-1 flex items-center gap-2">
                    <code className="min-w-0 flex-1 overflow-hidden text-ellipsis text-xs">{revealed.signing_secret}</code>
                    <Button size="sm" variant="ghost" onClick={() => copy(revealed.signing_secret, "Signing secret")}><Copy className="h-3.5 w-3.5" /></Button>
                  </div>
                </div>
              </div>
              <div className="mt-3 rounded-lg bg-white/70 p-3 text-xs text-muted">
                Sign exactly <code>timestamp + "." + raw_body</code> with HMAC-SHA256. Send headers
                <code> X-Qualive-Timestamp</code> and <code> X-Qualive-Signature: sha256=&lt;hex&gt;</code>.
                Every payload needs a stable <code>event_id</code> and exactly one attribution key:
                <code> action_job_id</code> for an executed action or <code> experiment_assignment_id</code> for a randomized treatment/holdout unit.
              </div>
              <Button className="mt-3" size="sm" variant="outline" onClick={() => setRevealed(null)}>I saved the secret</Button>
            </div>
          </div>
        </section>
      )}

      {showCreate && (
        <section className="space-y-4 rounded-xl border border-black/5 bg-white p-5 shadow-sm">
          <div>
            <h2 className="text-sm font-semibold text-ink">Create signed source</h2>
            <p className="mt-1 text-xs text-muted">An empty event-type list means any business event type is accepted. Prefer an explicit allowlist in production.</p>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="space-y-1 text-xs font-medium text-muted">
              Source name
              <input className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm text-ink" value={name} onChange={(event) => setName(event.target.value)} />
            </label>
            <label className="space-y-1 text-xs font-medium text-muted">
              Allowed business event types
              <input className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm text-ink" value={eventTypes} onChange={(event) => setEventTypes(event.target.value)} placeholder="converted,payment_received" />
            </label>
          </div>
          <div className="flex justify-end gap-2">
            <Button size="sm" variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button size="sm" disabled={!name.trim() || createSource.isPending} onClick={handleCreate}>{createSource.isPending ? "Creating…" : "Create source"}</Button>
          </div>
        </section>
      )}

      <section className="rounded-xl border border-black/5 bg-white shadow-sm">
        <div className="border-b border-black/5 p-4">
          <div className="flex items-center gap-2"><ShieldCheck className="h-4 w-4" /><h2 className="text-sm font-semibold text-ink">Signed integrations</h2></div>
          <p className="mt-1 text-xs text-muted">Health counters include accepted duplicates because safe retry delivery is expected.</p>
        </div>
        {isLoading ? (
          <div className="p-5 text-sm text-muted">Loading sources…</div>
        ) : (sources?.length ?? 0) === 0 ? (
          <div className="p-5 text-sm text-muted">No downstream outcome source connected yet.</div>
        ) : (
          <div className="divide-y divide-black/5">
            {(sources ?? []).map((source) => {
              const acceptance = source.delivery_count ? (source.accepted_count / source.delivery_count) * 100 : 0;
              return (
                <div key={source.id} className="grid gap-3 p-4 lg:grid-cols-[1.2fr_1fr_1fr_1.2fr] lg:items-center">
                  <div>
                    <div className="flex items-center gap-2"><span className="font-medium text-ink">{source.name}</span><span className={`rounded-full px-2 py-0.5 text-[10px] ${source.is_active ? "bg-emerald-50 text-emerald-700" : "bg-stone-100 text-muted"}`}>{source.is_active ? "active" : "disabled"}</span></div>
                    <p className="mt-1 text-xs text-muted">{source.slug} · {source.allowed_event_types.length ? source.allowed_event_types.join(", ") : "all business event types"}</p>
                  </div>
                  <div className="text-xs"><span className="text-muted">Deliveries</span><p className="font-semibold text-ink">{source.delivery_count.toLocaleString()}</p><p className="text-[10px] text-muted">{acceptance.toFixed(1)}% accepted</p></div>
                  <div className="text-xs"><span className="text-muted">Last accepted</span><p className="mt-0.5 text-ink">{source.last_accepted_at ? new Date(source.last_accepted_at).toLocaleString() : "Never"}</p>{source.last_error && <p className="mt-1 line-clamp-1 text-[10px] text-red-600">{source.last_error}</p>}</div>
                  <div className="flex flex-wrap justify-start gap-1 lg:justify-end">
                    <Button size="sm" variant="outline" disabled={updateSource.isPending} onClick={() => updateSource.mutate({ id: source.id, payload: { is_active: !source.is_active } })}>{source.is_active ? "Disable" : "Enable"}</Button>
                    <Button size="sm" variant="outline" disabled={rotateSecret.isPending} onClick={() => handleRotate(source.id)}><RotateCw className="mr-1 h-3.5 w-3.5" /> Rotate</Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}