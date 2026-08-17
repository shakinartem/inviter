import { useMemo, useState } from "react";
import { Filter, Plus, RefreshCw, Target, Trash2, Users } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  useCreateSegment,
  useDeactivateSegment,
  useRefreshSegment,
  useSegmentMembers,
  useSegments,
  type AudienceSegment,
} from "@/hooks/use-segments";

function score(value: number | null) {
  return value == null ? "—" : value.toFixed(1);
}

function criteriaSummary(segment: AudienceSegment) {
  const c = segment.criteria;
  const items: string[] = [];
  if (c.min_readiness_score != null) items.push(`Ready ≥ ${c.min_readiness_score}`);
  if (c.min_intent_score != null) items.push(`Intent ≥ ${c.min_intent_score}`);
  if (c.min_activity_score != null) items.push(`Activity ≥ ${c.min_activity_score}`);
  if (c.min_relevance_score != null) items.push(`Relevant ≥ ${c.min_relevance_score}`);
  if (c.last_activity_days != null) items.push(`Active ≤ ${c.last_activity_days}d`);
  if (c.min_communities != null) items.push(`${c.min_communities}+ communities`);
  if ((c.signal_types ?? []).length) items.push(...(c.signal_types ?? []).slice(0, 2));
  return items.slice(0, 5);
}

export default function SegmentsPage() {
  const [showCreate, setShowCreate] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { data: segments, isLoading } = useSegments({});
  const { data: members, isLoading: membersLoading } = useSegmentMembers(selectedId, 100);
  const createSegment = useCreateSegment();
  const refreshSegment = useRefreshSegment();
  const deactivateSegment = useDeactivateSegment();

  const [form, setForm] = useState({
    name: "",
    description: "",
    platform: "telegram",
    minActivity: "30",
    minIntent: "30",
    minReadiness: "40",
    minRelevance: "",
    lastActivityDays: "30",
    minCommunities: "",
    signalTypes: "",
    maxMembers: "10000",
    sortBy: "readiness" as "readiness" | "intent" | "activity",
  });

  const activeSegments = useMemo(
    () => (segments ?? []).filter((segment) => segment.is_active),
    [segments],
  );
  const selected = (segments ?? []).find((segment) => segment.id === selectedId) ?? null;

  const handleCreate = async () => {
    if (!form.name.trim()) return;
    const signalTypes = form.signalTypes
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);
    try {
      const segment = await createSegment.mutateAsync({
        name: form.name.trim(),
        description: form.description.trim() || null,
        platform: form.platform,
        criteria: {
          min_activity_score: form.minActivity ? Number(form.minActivity) : null,
          min_intent_score: form.minIntent ? Number(form.minIntent) : null,
          min_readiness_score: form.minReadiness ? Number(form.minReadiness) : null,
          min_relevance_score: form.minRelevance ? Number(form.minRelevance) : null,
          last_activity_days: form.lastActivityDays ? Number(form.lastActivityDays) : null,
          min_communities: form.minCommunities ? Number(form.minCommunities) : null,
          signal_types: signalTypes,
          signal_lookback_days: 90,
          include_bots: false,
          max_members: Number(form.maxMembers) || 10000,
          sort_by: form.sortBy,
        },
      });
      const refreshed = await refreshSegment.mutateAsync(segment.id);
      setSelectedId(segment.id);
      setShowCreate(false);
      setForm((value) => ({ ...value, name: "", description: "" }));
      toast.success(`Opportunity created · ${refreshed.matched_count} people matched`);
    } catch {
      toast.error("Could not create opportunity segment");
    }
  };

  const handleRefresh = async (segment: AudienceSegment) => {
    try {
      const result = await refreshSegment.mutateAsync(segment.id);
      toast.success(`${segment.name}: ${result.matched_count} people matched`);
    } catch {
      toast.error("Could not refresh segment");
    }
  };

  const handleDeactivate = async (segment: AudienceSegment) => {
    try {
      await deactivateSegment.mutateAsync(segment.id);
      if (selectedId === segment.id) setSelectedId(null);
      toast.success("Segment archived");
    } catch {
      toast.error("Could not archive segment");
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Opportunity Segments</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted">
            Turn readiness into explicit, reusable cohorts. Segment membership is materialized now;
            when selected for a campaign, that cohort is frozen so future rescoring cannot change who was targeted.
          </p>
        </div>
        <Button size="sm" onClick={() => setShowCreate((value) => !value)}>
          <Plus className="mr-1 h-4 w-4" /> New Opportunity
        </Button>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted">
            <Target className="h-4 w-4" /> Active opportunities
          </div>
          <p className="mt-3 text-2xl font-semibold text-ink">{activeSegments.length}</p>
        </div>
        <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted">
            <Users className="h-4 w-4" /> Materialized people
          </div>
          <p className="mt-3 text-2xl font-semibold text-ink">
            {activeSegments.reduce((sum, segment) => sum + segment.matched_count, 0).toLocaleString()}
          </p>
        </div>
        <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted">
            <Filter className="h-4 w-4" /> Refreshed opportunities
          </div>
          <p className="mt-3 text-2xl font-semibold text-ink">
            {activeSegments.filter((segment) => segment.last_refreshed_at).length}
          </p>
        </div>
      </div>

      {showCreate && (
        <section className="space-y-4 rounded-xl border border-black/5 bg-white p-5 shadow-sm">
          <div>
            <h2 className="text-sm font-semibold text-ink">Define an Opportunity</h2>
            <p className="mt-1 text-xs text-muted">
              Scores are evaluated when you refresh the segment. Keep criteria interpretable so outcome data can later tell us which thresholds actually work.
            </p>
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <label className="space-y-1 text-xs font-medium text-muted xl:col-span-2">
              Name
              <input className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm text-ink" placeholder="Hot real-estate intent" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
            </label>
            <label className="space-y-1 text-xs font-medium text-muted">
              Platform
              <select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm text-ink" value={form.platform} onChange={(event) => setForm({ ...form, platform: event.target.value })}>
                <option value="telegram">Telegram</option>
                <option value="discord">Discord</option>
              </select>
            </label>
            <label className="space-y-1 text-xs font-medium text-muted">
              Sort by
              <select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm text-ink" value={form.sortBy} onChange={(event) => setForm({ ...form, sortBy: event.target.value as typeof form.sortBy })}>
                <option value="readiness">Readiness</option>
                <option value="intent">Intent</option>
                <option value="activity">Activity</option>
              </select>
            </label>
            <label className="space-y-1 text-xs font-medium text-muted xl:col-span-4">
              Description
              <input className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm text-ink" placeholder="Who this opportunity represents and what action we expect next" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} />
            </label>
            {[
              ["Min activity", "minActivity"],
              ["Min intent", "minIntent"],
              ["Min readiness", "minReadiness"],
              ["Min relevance", "minRelevance"],
              ["Last activity ≤ days", "lastActivityDays"],
              ["Min communities", "minCommunities"],
              ["Max members", "maxMembers"],
            ].map(([label, key]) => (
              <label key={key} className="space-y-1 text-xs font-medium text-muted">
                {label}
                <input
                  type="number"
                  min={0}
                  className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm text-ink"
                  value={form[key as keyof typeof form] as string}
                  onChange={(event) => setForm({ ...form, [key]: event.target.value })}
                />
              </label>
            ))}
            <label className="space-y-1 text-xs font-medium text-muted xl:col-span-2">
              Intent signal types
              <input className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm text-ink" placeholder="transaction_intent, need_intent, urgency_intent" value={form.signalTypes} onChange={(event) => setForm({ ...form, signalTypes: event.target.value })} />
            </label>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button size="sm" disabled={!form.name.trim() || createSegment.isPending || refreshSegment.isPending} onClick={handleCreate}>
              {createSegment.isPending || refreshSegment.isPending ? "Building opportunity…" : "Create & materialize"}
            </Button>
          </div>
        </section>
      )}

      <section className="grid gap-4 xl:grid-cols-[1.1fr_1.4fr]">
        <div className="space-y-2">
          {isLoading ? (
            <div className="rounded-xl border border-black/5 bg-white p-5 text-sm text-muted">Loading opportunities…</div>
          ) : activeSegments.length ? (
            activeSegments.map((segment) => (
              <button
                key={segment.id}
                onClick={() => setSelectedId(segment.id)}
                className={`w-full rounded-xl border p-4 text-left shadow-sm transition ${selectedId === segment.id ? "border-ink bg-white" : "border-black/5 bg-white hover:border-black/15"}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold text-ink">{segment.name}</p>
                    <p className="mt-1 text-xs capitalize text-muted">{segment.platform} · {segment.criteria.sort_by ?? "readiness"} priority</p>
                  </div>
                  <div className="text-right">
                    <p className="text-xl font-semibold text-ink">{segment.matched_count.toLocaleString()}</p>
                    <p className="text-[10px] uppercase tracking-wide text-muted">people</p>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-1">
                  {criteriaSummary(segment).map((item) => (
                    <span key={item} className="rounded-full bg-stone-100 px-2 py-1 text-[10px] text-muted">{item.replace(/_/g, " ")}</span>
                  ))}
                </div>
                <div className="mt-3 flex items-center justify-between gap-2 border-t border-black/5 pt-3">
                  <p className="text-[11px] text-muted">
                    {segment.last_refreshed_at ? `Refreshed ${new Date(segment.last_refreshed_at).toLocaleString()}` : "Not refreshed"}
                  </p>
                  <div className="flex gap-1" onClick={(event) => event.stopPropagation()}>
                    <Button size="sm" variant="outline" disabled={refreshSegment.isPending} onClick={() => handleRefresh(segment)}>
                      <RefreshCw className="h-3.5 w-3.5" />
                    </Button>
                    <Button size="sm" variant="ghost" disabled={deactivateSegment.isPending} onClick={() => handleDeactivate(segment)}>
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              </button>
            ))
          ) : (
            <div className="rounded-xl border border-dashed border-black/10 bg-white p-6 text-sm text-muted">No opportunity segments yet. Create one from activity + intent + readiness.</div>
          )}
        </div>

        <div className="rounded-xl border border-black/5 bg-white shadow-sm">
          <div className="border-b border-black/5 p-4">
            <h2 className="text-sm font-semibold text-ink">{selected ? selected.name : "Opportunity members"}</h2>
            <p className="mt-1 text-xs text-muted">Materialized snapshot. A campaign will freeze a copy of these members.</p>
          </div>
          {!selected ? (
            <div className="p-6 text-sm text-muted">Select an opportunity to inspect who matched.</div>
          ) : membersLoading ? (
            <div className="p-6 text-sm text-muted">Loading matched people…</div>
          ) : (
            <div className="max-h-[640px] overflow-auto">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-stone-50 text-xs text-muted">
                  <tr><th className="px-3 py-2">Person</th><th className="px-3 py-2">Intent</th><th className="px-3 py-2">Ready</th><th className="px-3 py-2">Signal</th></tr>
                </thead>
                <tbody>
                  {(members?.items ?? []).map((member) => {
                    const name = [member.first_name, member.last_name].filter(Boolean).join(" ") || member.username || member.audience_member_id;
                    return (
                      <tr key={member.segment_member_id} className="border-t border-black/5">
                        <td className="px-3 py-2"><p className="font-medium text-ink">{name}</p>{member.username && <p className="text-[10px] text-muted">@{member.username}</p>}</td>
                        <td className="px-3 py-2">{score(member.intent_score)}</td>
                        <td className="px-3 py-2 font-semibold">{score(member.readiness_score)}</td>
                        <td className="px-3 py-2 text-xs text-muted">{member.strongest_signal_type?.replace(/_/g, " ") ?? "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {(members?.items.length ?? 0) === 0 && <div className="p-6 text-sm text-muted">This opportunity has no matched people yet. Refresh it after collecting more audience intelligence.</div>}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
