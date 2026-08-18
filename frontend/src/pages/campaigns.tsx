import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { createColumnHelper } from "@tanstack/react-table";
import { FlaskConical, Pause, Play, Plus, RefreshCw, Search, Square, Target, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  useCampaigns,
  useCreateCampaign,
  useDeleteCampaign,
  usePauseCampaign,
  useStartCampaign,
  useStopCampaign,
} from "@/hooks/use-campaigns";
import { useExperiments } from "@/hooks/use-experiments";
import { useParsedChats, usePlatformDiscovery } from "@/hooks/use-parser";
import { useSegments } from "@/hooks/use-segments";
import type { InviteCampaignListItem } from "@/types";

const columnHelper = createColumnHelper<InviteCampaignListItem>();

export default function CampaignsPage() {
  const [showCreate, setShowCreate] = useState(false);
  const [search, setSearch] = useState("");
  const [planLimit, setPlanLimit] = useState("1000");

  const { data: campaigns, isLoading } = useCampaigns({ skip: 0, limit: 500 });
  const { data: experiments } = useExperiments();
  const { data: segments, isLoading: segmentsLoading } = useSegments({ active_only: true, platform: "telegram" });
  const { data: syncedChats, isLoading: chatsLoading } = useParsedChats({
    source: "telegram_dialogs",
    limit: 500,
  });
  const syncChats = usePlatformDiscovery();
  const createCampaign = useCreateCampaign();
  const deleteCampaign = useDeleteCampaign();
  const startCampaign = useStartCampaign();
  const pauseCampaign = usePauseCampaign();
  const stopCampaign = useStopCampaign();

  const [form, setForm] = useState({
    title: "",
    source_segment_id: "",
    target_community_id: "",
    holdout_percentage: "10",
    reserve_capacity_percentage: "0",
  });

  const experimentByCampaign = useMemo(
    () => new Map((experiments ?? []).map((experiment) => [experiment.campaign_id, experiment])),
    [experiments],
  );
  const destinations = useMemo(
    () =>
      (syncedChats?.items ?? []).filter((chat) =>
        ["group", "supergroup", "chat"].includes(chat.chat_type ?? ""),
      ),
    [syncedChats],
  );
  const availableSegments = useMemo(
    () =>
      (segments ?? []).filter(
        (segment) => segment.is_active && !!segment.last_refreshed_at && segment.matched_count > 0,
      ),
    [segments],
  );

  const handleSyncChats = async () => {
    try {
      const items = await syncChats.mutateAsync({ platform: "telegram", query: "", limit: 200 });
      const groups = items.filter((chat) => ["group", "supergroup", "chat"].includes(chat.chat_type ?? ""));
      toast.success(`Synced ${groups.length} Telegram groups`);
    } catch {
      toast.error("Could not sync Telegram chats. Check that an active Telegram connection is available.");
    }
  };

  const handleCreate = async () => {
    if (!form.title.trim() || !form.source_segment_id || !form.target_community_id) return;
    try {
      const holdout = Math.max(0, Math.min(50, Number(form.holdout_percentage) || 0));
      const reserve = Math.max(0, Math.min(50, Number(form.reserve_capacity_percentage) || 0));
      await createCampaign.mutateAsync({
        title: form.title.trim(),
        source_segment_id: form.source_segment_id,
        target_community_id: form.target_community_id,
        holdout_percentage: holdout,
        settings: {
          reserve_capacity_percentage: reserve,
        },
      });
      setForm({
        title: "",
        source_segment_id: "",
        target_community_id: "",
        holdout_percentage: "10",
        reserve_capacity_percentage: "0",
      });
      setShowCreate(false);
      const details = [
        holdout > 0 ? `${holdout}% causal holdout` : "no holdout",
        reserve > 0 ? `${reserve}% failover reserve` : "no failover reserve",
      ].join(" · ");
      toast.success(`Campaign created · ${details}`);
    } catch {
      toast.error("Failed to create campaign. Refresh the Opportunity and resync a private destination if needed.");
    }
  };

  const handleStart = async (campaign: InviteCampaignListItem) => {
    try {
      const experiment = experimentByCampaign.get(campaign.id);
      const requestedLimit = experiment?.action_budget ?? (Number(planLimit) || 1000);
      const result = await startCampaign.mutateAsync({
        id: campaign.id,
        payload: {
          limit: requestedLimit,
          min_activity_score: 0,
          min_readiness_score: 0,
        },
      });
      const headroom = result.reserved_failover_headroom ?? 0;
      const reserveText = headroom > 0 ? ` · ${headroom}/day failover headroom` : "";
      if (result.experiment_id) {
        toast.success(
          `Campaign started · ${result.planned} actions · ${result.holdout_count ?? 0} randomized holdout${reserveText}`,
        );
      } else {
        toast.success(`Campaign started · ${result.planned} actions planned from frozen cohort${reserveText}`);
      }
    } catch {
      toast.error("Could not start campaign. If a randomized experiment was already assigned, its original action budget is immutable.");
    }
  };

  const handlePause = async (id: string) => {
    try {
      await pauseCampaign.mutateAsync(id);
      toast.success("Campaign paused");
    } catch {
      toast.error("Failed to pause campaign");
    }
  };

  const handleStop = async (id: string) => {
    try {
      await stopCampaign.mutateAsync(id);
      toast.success("Campaign stopped");
    } catch {
      toast.error("Failed to stop campaign");
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteCampaign.mutateAsync(id);
      toast.success("Campaign deleted");
    } catch {
      toast.error("Failed to delete campaign");
    }
  };

  const columns = useMemo(
    () => [
      columnHelper.accessor("title", {
        header: "Campaign",
        cell: (info) => <span className="font-medium text-ink">{info.getValue()}</span>,
      }),
      columnHelper.accessor("status", {
        header: "Status",
        cell: (info) => <StatusBadge status={info.getValue()} />,
      }),
      columnHelper.accessor("target_chat_title", {
        header: "Destination",
        cell: (info) => info.getValue() ?? info.row.original.target_chat_username ?? "Configured chat",
      }),
      columnHelper.display({
        id: "audience",
        header: "Opportunity",
        cell: () => (
          <span className="inline-flex items-center gap-1 text-xs text-muted">
            <Target className="h-3.5 w-3.5" /> Frozen cohort
          </span>
        ),
      }),
      columnHelper.display({
        id: "experiment",
        header: "Causal holdout",
        cell: (info) => {
          const experiment = experimentByCampaign.get(info.row.original.id);
          if (!experiment) return <span className="text-xs text-muted">Off</span>;
          return (
            <div className="text-xs">
              <div className="flex items-center gap-1 font-medium text-ink">
                <FlaskConical className="h-3.5 w-3.5" /> {experiment.holdout_percentage.toFixed(0)}%
              </div>
              <p className="mt-0.5 text-[10px] text-muted">
                {experiment.status === "assigned"
                  ? `${experiment.treatment_count} treatment · ${experiment.holdout_count} holdout · budget ${experiment.action_budget}`
                  : "assigns on first Start"}
              </p>
            </div>
          );
        },
      }),
      columnHelper.accessor("created_at", {
        header: "Created",
        cell: (info) => new Date(info.getValue()).toLocaleDateString(),
      }),
      columnHelper.display({
        id: "actions",
        header: "Actions",
        cell: (info) => {
          const campaign = info.row.original;
          const busy = startCampaign.isPending || pauseCampaign.isPending || stopCampaign.isPending;
          return (
            <div className="flex items-center gap-1">
              {(campaign.status === "draft" || campaign.status === "paused") && (
                <Button size="sm" variant="outline" disabled={busy} onClick={() => handleStart(campaign)}>
                  <Play className="mr-1 h-3.5 w-3.5" /> Start
                </Button>
              )}
              {campaign.status === "active" && (
                <Button size="sm" variant="outline" disabled={busy} onClick={() => handlePause(campaign.id)}>
                  <Pause className="mr-1 h-3.5 w-3.5" /> Pause
                </Button>
              )}
              {(campaign.status === "active" || campaign.status === "paused") && (
                <Button size="sm" variant="outline" disabled={busy} onClick={() => handleStop(campaign.id)}>
                  <Square className="h-3.5 w-3.5" />
                </Button>
              )}
              {campaign.status === "draft" && (
                <Button size="sm" variant="ghost" onClick={() => handleDeleteCampaign(campaign.id)}>
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              )}
            </div>
          );
        },
      }),
    ],
    [experimentByCampaign, startCampaign.isPending, pauseCampaign.isPending, stopCampaign.isPending],
  );

  function handleDeleteCampaign(id: string) {
    void handleDelete(id);
  }

  const filteredCampaigns = (campaigns ?? []).filter((campaign) =>
    campaign.title.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Campaigns</h1>
          <p className="mt-1 text-sm text-muted">Apply a frozen Opportunity cohort to a concrete destination and action.</p>
        </div>
        <Button size="sm" onClick={() => setShowCreate(!showCreate)}>
          <Plus className="mr-1 h-4 w-4" /> New Campaign
        </Button>
      </div>

      <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm">
        <label className="block max-w-xs space-y-1 text-xs font-medium text-muted">
          Max treatment actions to schedule
          <input
            className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            type="number"
            min={1}
            max={50000}
            value={planLimit}
            onChange={(event) => setPlanLimit(event.target.value)}
          />
        </label>
        <p className="mt-2 text-xs text-muted">
          This becomes the immutable action budget when a randomized holdout is assigned. Paused experiments reuse their original budget automatically.
        </p>
      </div>

      {showCreate && (
        <div className="space-y-4 rounded-xl border border-black/5 bg-white p-5 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-sm font-semibold text-ink">New Campaign</h3>
              <p className="mt-1 text-xs text-muted">
                Opportunity + Destination → Action. Holdout measures causal lift; failover reserve protects execution capacity.
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={handleSyncChats} disabled={syncChats.isPending}>
              <RefreshCw className="mr-1 h-3.5 w-3.5" />
              {syncChats.isPending ? "Syncing..." : "Sync my Telegram chats"}
            </Button>
          </div>
          <div className="grid gap-3 md:grid-cols-5">
            <input className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent" placeholder="Campaign title *" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} />
            <select className="rounded-lg border border-black/10 bg-white px-3 py-2 text-sm outline-none focus:border-accent" value={form.source_segment_id} onChange={(event) => setForm({ ...form, source_segment_id: event.target.value })} disabled={segmentsLoading}>
              <option value="">Select Opportunity *</option>
              {availableSegments.map((segment) => <option key={segment.id} value={segment.id}>{segment.name} · {segment.matched_count.toLocaleString()} people</option>)}
            </select>
            <select className="rounded-lg border border-black/10 bg-white px-3 py-2 text-sm outline-none focus:border-accent" value={form.target_community_id} onChange={(event) => setForm({ ...form, target_community_id: event.target.value })} disabled={chatsLoading}>
              <option value="">Select destination group *</option>
              {destinations.map((chat) => <option key={chat.id} value={chat.id}>{chat.title ?? chat.username ?? `Telegram group ${chat.id}`}{chat.username ? ` (@${chat.username})` : " (private)"}</option>)}
            </select>
            <label className="space-y-1 text-[10px] font-medium uppercase tracking-wide text-muted">
              Causal holdout %
              <input type="number" min={0} max={50} step={1} className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm normal-case text-ink" value={form.holdout_percentage} onChange={(event) => setForm({ ...form, holdout_percentage: event.target.value })} />
            </label>
            <label className="space-y-1 text-[10px] font-medium uppercase tracking-wide text-muted">
              Failover reserve %
              <input type="number" min={0} max={50} step={1} className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm normal-case text-ink" value={form.reserve_capacity_percentage} onChange={(event) => setForm({ ...form, reserve_capacity_percentage: event.target.value })} />
            </label>
          </div>
          <div className="grid gap-2 md:grid-cols-2">
            <div className="rounded-lg bg-stone-50 px-3 py-2 text-xs text-muted">
              <strong className="text-ink">Holdout is deliberate reach cost.</strong> At 10%, randomized units receive no action so downstream lift can be measured. Set 0% to disable causal measurement.
            </div>
            <div className="rounded-lg bg-stone-50 px-3 py-2 text-xs text-muted">
              <strong className="text-ink">Failover reserve is deliberate throughput headroom.</strong> Normal planning leaves this share unused; adaptive execution may consume it after hard account cooldown. Default 0% means no hidden throughput reduction.
            </div>
          </div>
          {!segmentsLoading && availableSegments.length === 0 && (
            <p className="rounded-lg bg-stone-50 px-3 py-2 text-xs text-muted">No materialized Telegram Opportunity yet. <Link to="/segments" className="font-medium text-ink underline">Create and refresh an Opportunity Segment</Link> first.</p>
          )}
          {!chatsLoading && destinations.length === 0 && (
            <p className="rounded-lg bg-stone-50 px-3 py-2 text-xs text-muted">No synced Telegram groups yet. Click “Sync my Telegram chats” after connecting an active Telegram account.</p>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button size="sm" onClick={handleCreate} disabled={!form.title.trim() || !form.source_segment_id || !form.target_community_id || createCampaign.isPending}>{createCampaign.isPending ? "Freezing cohort…" : "Create Campaign"}</Button>
          </div>
        </div>
      )}

      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <input className="w-full rounded-lg border border-black/10 bg-white py-2 pl-10 pr-4 text-sm outline-none focus:border-accent" placeholder="Search campaigns..." value={search} onChange={(event) => setSearch(event.target.value)} />
      </div>

      <DataTable columns={columns} data={filteredCampaigns} loading={isLoading} pageSize={25} />
    </div>
  );
}
