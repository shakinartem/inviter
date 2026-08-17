import { useMemo, useState } from "react";
import { Eye, Filter, Plus, RefreshCw, Search, Target, Trash2, Users } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { useParsedChats } from "@/hooks/use-parser";
import {
  useCreateSegment,
  useDeactivateSegment,
  usePreviewSegment,
  useRefreshSegment,
  useSegmentMembers,
  useSegments,
  type AudienceSegment,
  type SegmentCriteria,
} from "@/hooks/use-segments";

function score(value: number | null) {
  return value == null ? "—" : value.toFixed(1);
}

function criteriaSummary(segment: AudienceSegment) {
  const c = segment.criteria;
  const items: string[] = [];
  if ((c.community_ids ?? []).length) items.push(`${c.community_ids?.length} scoped communities`);
  if (c.min_readiness_score != null) items.push(`Ready ≥ ${c.min_readiness_score}`);
  if (c.min_intent_score != null) items.push(`Intent ≥ ${c.min_intent_score}`);
  if (c.min_activity_score != null) items.push(`Activity ≥ ${c.min_activity_score}`);
  if (c.last_activity_days != null) items.push(`Active ≤ ${c.last_activity_days}d`);
  if ((c.signal_types ?? []).length) items.push(...(c.signal_types ?? []).slice(0, 2));
  return items.slice(0, 6);
}

export default function SegmentsPage() {
  const [showCreate, setShowCreate] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [communitySearch, setCommunitySearch] = useState("");
  const { data: segments, isLoading } = useSegments({});
  const { data: members, isLoading: membersLoading } = useSegmentMembers(selectedId, 100);
  const { data: parsedChats } = useParsedChats({ limit: 200 });
  const createSegment = useCreateSegment();
  const refreshSegment = useRefreshSegment();
  const deactivateSegment = useDeactivateSegment();
  const previewSegment = usePreviewSegment();

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
    communityIds: [] as string[],
  });

  const updateForm = (patch: Partial<typeof form>) => {
    setForm((value) => ({ ...value, ...patch }));
    previewSegment.reset();
  };

  const activeSegments = useMemo(
    () => (segments ?? []).filter((segment) => segment.is_active),
    [segments],
  );
  const selected = (segments ?? []).find((segment) => segment.id === selectedId) ?? null;

  const availableCommunities = useMemo(() => {
    const query = communitySearch.trim().toLowerCase();
    return (parsedChats?.items ?? [])
      .filter((chat) => form.platform === "discord" ? chat.source === "discord" : chat.source !== "discord")
      .filter((chat) => !query || (chat.title ?? "").toLowerCase().includes(query) || (chat.username ?? "").toLowerCase().includes(query))
      .slice(0, 100);
  }, [parsedChats, form.platform, communitySearch]);

  const criteriaFromForm = (): SegmentCriteria => ({
    min_activity_score: form.minActivity ? Number(form.minActivity) : null,
    min_intent_score: form.minIntent ? Number(form.minIntent) : null,
    min_readiness_score: form.minReadiness ? Number(form.minReadiness) : null,
    min_relevance_score: form.minRelevance ? Number(form.minRelevance) : null,
    last_activity_days: form.lastActivityDays ? Number(form.lastActivityDays) : null,
    min_communities: form.minCommunities ? Number(form.minCommunities) : null,
    community_ids: form.communityIds,
    signal_types: form.signalTypes.split(",").map((value) => value.trim()).filter(Boolean),
    signal_lookback_days: 90,
    include_bots: false,
    max_members: Number(form.maxMembers) || 10000,
    sort_by: form.sortBy,
  });

  const toggleCommunity = (id: string) => {
    const next = form.communityIds.includes(id)
      ? form.communityIds.filter((value) => value !== id)
      : [...form.communityIds, id];
    updateForm({ communityIds: next });
  };

  const handlePreview = async () => {
    try {
      await previewSegment.mutateAsync({ platform: form.platform, criteria: criteriaFromForm() });
    } catch {
      toast.error("Could not preview this Opportunity. Check community scope and criteria.");
    }
  };

  const handleCreate = async () => {
    if (!form.name.trim()) return;
    try {
      const segment = await createSegment.mutateAsync({
        name: form.name.trim(),
        description: form.description.trim() || null,
        platform: form.platform,
        criteria: criteriaFromForm(),
      });
      const refreshed = await refreshSegment.mutateAsync(segment.id);
      setSelectedId(segment.id);
      setShowCreate(false);
      setForm((value) => ({ ...value, name: "", description: "", communityIds: [] }));
      previewSegment.reset();
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
            Define explicit context + intent + readiness cohorts. Preview the population first, then materialize it; campaigns freeze a copy so later rescoring cannot rewrite the decision.
          </p>
        </div>
        <Button size="sm" onClick={() => setShowCreate((value) => !value)}>
          <Plus className="mr-1 h-4 w-4" /> New Opportunity
        </Button>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted"><Target className="h-4 w-4" /> Active opportunities</div><p className="mt-3 text-2xl font-semibold text-ink">{activeSegments.length}</p></div>
        <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted"><Users className="h-4 w-4" /> Materialized people</div><p className="mt-3 text-2xl font-semibold text-ink">{activeSegments.reduce((sum, segment) => sum + segment.matched_count, 0).toLocaleString()}</p></div>
        <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm"><div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted"><Filter className="h-4 w-4" /> Refreshed opportunities</div><p className="mt-3 text-2xl font-semibold text-ink">{activeSegments.filter((segment) => segment.last_refreshed_at).length}</p></div>
      </div>

      {showCreate && (
        <section className="space-y-5 rounded-xl border border-black/5 bg-white p-5 shadow-sm">
          <div><h2 className="text-sm font-semibold text-ink">Define an Opportunity</h2><p className="mt-1 text-xs text-muted">Community scope says where evidence must come from. Score thresholds say how strong the person must be inside that context.</p></div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <label className="space-y-1 text-xs font-medium text-muted xl:col-span-2">Name<input className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm text-ink" placeholder="Hot Moscow new-build intent" value={form.name} onChange={(event) => updateForm({ name: event.target.value })} /></label>
            <label className="space-y-1 text-xs font-medium text-muted">Platform<select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm text-ink" value={form.platform} onChange={(event) => updateForm({ platform: event.target.value, communityIds: [] })}><option value="telegram">Telegram</option><option value="discord">Discord</option></select></label>
            <label className="space-y-1 text-xs font-medium text-muted">Sort by<select className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm text-ink" value={form.sortBy} onChange={(event) => updateForm({ sortBy: event.target.value as typeof form.sortBy })}><option value="readiness">Readiness</option><option value="intent">Intent</option><option value="activity">Activity</option></select></label>
            <label className="space-y-1 text-xs font-medium text-muted xl:col-span-4">Description<input className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm text-ink" placeholder="Who this opportunity represents and which future action matters" value={form.description} onChange={(event) => updateForm({ description: event.target.value })} /></label>
            {[["Min activity", "minActivity"], ["Min intent", "minIntent"], ["Min readiness", "minReadiness"], ["Min relevance", "minRelevance"], ["Last activity ≤ days", "lastActivityDays"], ["Min communities", "minCommunities"], ["Max members", "maxMembers"]].map(([label, key]) => (
              <label key={key} className="space-y-1 text-xs font-medium text-muted">{label}<input type="number" min={0} className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm text-ink" value={form[key as keyof typeof form] as string} onChange={(event) => updateForm({ [key]: event.target.value } as Partial<typeof form>)} /></label>
            ))}
            <label className="space-y-1 text-xs font-medium text-muted xl:col-span-2">Intent signal types<input className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm text-ink" placeholder="transaction_intent, need_intent, urgency_intent" value={form.signalTypes} onChange={(event) => updateForm({ signalTypes: event.target.value })} /></label>
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
            <div className="rounded-lg border border-black/5 bg-stone-50 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2"><div><h3 className="text-xs font-semibold uppercase tracking-wide text-muted">Community scope</h3><p className="mt-1 text-xs text-muted">{form.communityIds.length ? `${form.communityIds.length} selected` : "No selection = global platform audience"}</p></div><div className="relative"><Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted" /><input className="w-56 rounded-lg border border-black/10 bg-white py-1.5 pl-8 pr-2 text-xs" placeholder="Find community" value={communitySearch} onChange={(event) => setCommunitySearch(event.target.value)} /></div></div>
              <div className="mt-3 max-h-52 overflow-auto rounded-lg border border-black/5 bg-white">
                {availableCommunities.map((chat) => <label key={chat.id} className="flex cursor-pointer items-center gap-2 border-b border-black/5 px-3 py-2 text-xs last:border-0"><input type="checkbox" checked={form.communityIds.includes(chat.id)} onChange={() => toggleCommunity(chat.id)} /><span className="min-w-0 flex-1 truncate text-ink">{chat.title ?? chat.username ?? `Community ${chat.id}`}</span><span className="text-[10px] text-muted">{chat.participants_count?.toLocaleString() ?? "—"}</span></label>)}
                {availableCommunities.length === 0 && <p className="p-3 text-xs text-muted">No discovered communities match this platform/search.</p>}
              </div>
            </div>

            <div className="rounded-lg border border-black/5 p-4">
              <div className="flex items-center justify-between gap-2"><div><h3 className="text-xs font-semibold uppercase tracking-wide text-muted">Cohort preview</h3><p className="mt-1 text-xs text-muted">Read-only evaluation; nothing is saved.</p></div><Button size="sm" variant="outline" disabled={previewSegment.isPending} onClick={handlePreview}><Eye className="mr-1 h-3.5 w-3.5" /> {previewSegment.isPending ? "Evaluating…" : "Preview"}</Button></div>
              {previewSegment.data ? <div className="mt-4 space-y-3"><div className="grid grid-cols-2 gap-2"><div className="rounded-lg bg-stone-50 p-3"><p className="text-[10px] uppercase text-muted">Matched</p><p className="text-xl font-semibold text-ink">{previewSegment.data.matched_count.toLocaleString()}</p></div><div className="rounded-lg bg-stone-50 p-3"><p className="text-[10px] uppercase text-muted">Avg readiness</p><p className="text-xl font-semibold text-ink">{score(previewSegment.data.average_readiness_score)}</p></div><div className="rounded-lg bg-stone-50 p-3"><p className="text-[10px] uppercase text-muted">Avg intent</p><p className="text-xl font-semibold text-ink">{score(previewSegment.data.average_intent_score)}</p></div><div className="rounded-lg bg-stone-50 p-3"><p className="text-[10px] uppercase text-muted">Avg activity</p><p className="text-xl font-semibold text-ink">{score(previewSegment.data.average_activity_score)}</p></div></div><div className="flex flex-wrap gap-1">{Object.entries(previewSegment.data.strongest_signal_distribution).slice(0, 5).map(([signal, count]) => <span key={signal} className="rounded-full bg-stone-100 px-2 py-1 text-[10px] text-muted">{signal.replace(/_/g, " ")} · {count}</span>)}</div>{previewSegment.data.warnings.length > 0 && <p className="text-[11px] text-amber-700">{previewSegment.data.warnings.map((value) => value.replace(/_/g, " ")).join(" · ")}</p>}</div> : <p className="mt-4 rounded-lg bg-stone-50 p-3 text-xs text-muted">Preview before materializing to catch cohorts that are too broad, too small or dominated by the wrong signal.</p>}
            </div>
          </div>

          <div className="flex justify-end gap-2"><Button variant="outline" size="sm" onClick={() => setShowCreate(false)}>Cancel</Button><Button size="sm" disabled={!form.name.trim() || createSegment.isPending || refreshSegment.isPending} onClick={handleCreate}>{createSegment.isPending || refreshSegment.isPending ? "Building opportunity…" : "Create & materialize"}</Button></div>
        </section>
      )}

      <section className="grid gap-4 xl:grid-cols-[1.1fr_1.4fr]">
        <div className="space-y-2">
          {isLoading ? <div className="rounded-xl border border-black/5 bg-white p-5 text-sm text-muted">Loading opportunities…</div> : activeSegments.length ? activeSegments.map((segment) => (
            <button key={segment.id} onClick={() => setSelectedId(segment.id)} className={`w-full rounded-xl border p-4 text-left shadow-sm transition ${selectedId === segment.id ? "border-ink bg-white" : "border-black/5 bg-white hover:border-black/15"}`}>
              <div className="flex items-start justify-between gap-3"><div><p className="font-semibold text-ink">{segment.name}</p><p className="mt-1 text-xs capitalize text-muted">{segment.platform} · {segment.criteria.sort_by ?? "readiness"} priority</p></div><div className="text-right"><p className="text-xl font-semibold text-ink">{segment.matched_count.toLocaleString()}</p><p className="text-[10px] uppercase tracking-wide text-muted">people</p></div></div>
              <div className="mt-3 flex flex-wrap gap-1">{criteriaSummary(segment).map((item) => <span key={item} className="rounded-full bg-stone-100 px-2 py-1 text-[10px] text-muted">{item.replace(/_/g, " ")}</span>)}</div>
              <div className="mt-3 flex items-center justify-between gap-2 border-t border-black/5 pt-3"><p className="text-[11px] text-muted">{segment.last_refreshed_at ? `Refreshed ${new Date(segment.last_refreshed_at).toLocaleString()}` : "Not refreshed"}</p><div className="flex gap-1" onClick={(event) => event.stopPropagation()}><Button size="sm" variant="outline" disabled={refreshSegment.isPending} onClick={() => handleRefresh(segment)}><RefreshCw className="h-3.5 w-3.5" /></Button><Button size="sm" variant="ghost" disabled={deactivateSegment.isPending} onClick={() => handleDeactivate(segment)}><Trash2 className="h-3.5 w-3.5" /></Button></div></div>
            </button>
          )) : <div className="rounded-xl border border-dashed border-black/10 bg-white p-6 text-sm text-muted">No opportunity segments yet. Create one from context + intent + readiness.</div>}
        </div>

        <div className="rounded-xl border border-black/5 bg-white shadow-sm">
          <div className="border-b border-black/5 p-4"><h2 className="text-sm font-semibold text-ink">{selected ? selected.name : "Opportunity members"}</h2><p className="mt-1 text-xs text-muted">Materialized snapshot. A campaign freezes a copy of these members.</p></div>
          {!selected ? <div className="p-6 text-sm text-muted">Select an opportunity to inspect who matched.</div> : membersLoading ? <div className="p-6 text-sm text-muted">Loading matched people…</div> : <div className="max-h-[640px] overflow-auto"><table className="w-full text-left text-sm"><thead className="sticky top-0 bg-stone-50 text-xs text-muted"><tr><th className="px-3 py-2">Person</th><th className="px-3 py-2">Intent</th><th className="px-3 py-2">Ready</th><th className="px-3 py-2">Signal</th></tr></thead><tbody>{(members?.items ?? []).map((member) => { const name = [member.first_name, member.last_name].filter(Boolean).join(" ") || member.username || member.audience_member_id; return <tr key={member.segment_member_id} className="border-t border-black/5"><td className="px-3 py-2"><p className="font-medium text-ink">{name}</p>{member.username && <p className="text-[10px] text-muted">@{member.username}</p>}</td><td className="px-3 py-2">{score(member.intent_score)}</td><td className="px-3 py-2 font-semibold">{score(member.readiness_score)}</td><td className="px-3 py-2 text-xs text-muted">{member.strongest_signal_type?.replace(/_/g, " ") ?? "—"}</td></tr>; })}</tbody></table>{(members?.items.length ?? 0) === 0 && <div className="p-6 text-sm text-muted">This opportunity has no matched people yet.</div>}</div>}
        </div>
      </section>
    </div>
  );
}
