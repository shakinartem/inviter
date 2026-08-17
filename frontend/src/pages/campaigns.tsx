import { useMemo, useState } from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Pause, Play, Plus, RefreshCw, Search, Square, Trash2 } from "lucide-react";
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
import { useParsedChats, usePlatformDiscovery } from "@/hooks/use-parser";
import type { InviteCampaignListItem } from "@/types";

const columnHelper = createColumnHelper<InviteCampaignListItem>();

export default function CampaignsPage() {
  const [showCreate, setShowCreate] = useState(false);
  const [search, setSearch] = useState("");
  const [minActivity, setMinActivity] = useState("30");
  const [minReadiness, setMinReadiness] = useState("20");
  const [planLimit, setPlanLimit] = useState("1000");

  const { data: campaigns, isLoading } = useCampaigns({ skip: 0, limit: 500 });
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
    target_community_id: "",
  });

  const destinations = useMemo(
    () =>
      (syncedChats?.items ?? []).filter((chat) =>
        ["group", "supergroup", "chat"].includes(chat.chat_type ?? ""),
      ),
    [syncedChats],
  );

  const handleSyncChats = async () => {
    try {
      const items = await syncChats.mutateAsync({
        platform: "telegram",
        query: "",
        limit: 200,
      });
      const groups = items.filter((chat) => ["group", "supergroup", "chat"].includes(chat.chat_type ?? ""));
      toast.success(`Synced ${groups.length} Telegram groups`);
    } catch {
      toast.error("Could not sync Telegram chats. Check that an active Telegram connection is available.");
    }
  };

  const handleCreate = async () => {
    if (!form.title.trim() || !form.target_community_id) return;
    try {
      await createCampaign.mutateAsync({
        title: form.title.trim(),
        target_community_id: form.target_community_id,
        source_type: "parsed_list",
      });
      setForm({ title: "", target_community_id: "" });
      setShowCreate(false);
      toast.success("Campaign created");
    } catch {
      toast.error("Failed to create campaign. Resync the destination chat if it is private.");
    }
  };

  const handleStart = async (campaign: InviteCampaignListItem) => {
    try {
      const result = await startCampaign.mutateAsync({
        id: campaign.id,
        payload: {
          limit: Number(planLimit) || 1000,
          min_activity_score: Number(minActivity) || 0,
          min_readiness_score: Number(minReadiness) || 0,
        },
      });
      toast.success(`Campaign started · ${result.planned ?? 0} actions planned`);
    } catch {
      toast.error("Could not start campaign. Check destination, audience and active Telegram accounts.");
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
        header: "Audience",
        cell: () => "Ranked audience",
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
                <Button size="sm" variant="ghost" onClick={() => handleDelete(campaign.id)}>
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              )}
            </div>
          );
        },
      }),
    ],
    [startCampaign.isPending, pauseCampaign.isPending, stopCampaign.isPending],
  );

  const filteredCampaigns = (campaigns ?? []).filter((campaign) =>
    campaign.title.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Campaigns</h1>
          <p className="mt-1 text-sm text-muted">Turn ranked audience into scheduled platform actions.</p>
        </div>
        <Button size="sm" onClick={() => setShowCreate(!showCreate)}>
          <Plus className="mr-1 h-4 w-4" /> New Campaign
        </Button>
      </div>

      <div className="grid gap-3 rounded-xl border border-black/5 bg-white p-4 shadow-sm md:grid-cols-3">
        <label className="space-y-1 text-xs font-medium text-muted">
          Min activity
          <input
            className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            type="number"
            min={0}
            max={100}
            value={minActivity}
            onChange={(event) => setMinActivity(event.target.value)}
          />
        </label>
        <label className="space-y-1 text-xs font-medium text-muted">
          Min readiness
          <input
            className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            type="number"
            min={0}
            max={100}
            value={minReadiness}
            onChange={(event) => setMinReadiness(event.target.value)}
          />
        </label>
        <label className="space-y-1 text-xs font-medium text-muted">
          Max audience
          <input
            className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            type="number"
            min={1}
            max={50000}
            value={planLimit}
            onChange={(event) => setPlanLimit(event.target.value)}
          />
        </label>
      </div>

      {showCreate && (
        <div className="space-y-4 rounded-xl border border-black/5 bg-white p-5 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-sm font-semibold text-ink">New Campaign</h3>
              <p className="mt-1 text-xs text-muted">
                Choose a Telegram group already accessible to one of your connected accounts. Raw chat IDs are not required.
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={handleSyncChats} disabled={syncChats.isPending}>
              <RefreshCw className="mr-1 h-3.5 w-3.5" />
              {syncChats.isPending ? "Syncing..." : "Sync my Telegram chats"}
            </Button>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <input
              className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent"
              placeholder="Campaign title *"
              value={form.title}
              onChange={(event) => setForm({ ...form, title: event.target.value })}
            />
            <select
              className="rounded-lg border border-black/10 bg-white px-3 py-2 text-sm outline-none focus:border-accent"
              value={form.target_community_id}
              onChange={(event) => setForm({ ...form, target_community_id: event.target.value })}
              disabled={chatsLoading}
            >
              <option value="">Select destination group *</option>
              {destinations.map((chat) => (
                <option key={chat.id} value={chat.id}>
                  {chat.title ?? chat.username ?? `Telegram group ${chat.id}`}
                  {chat.username ? ` (@${chat.username})` : " (private)"}
                </option>
              ))}
            </select>
          </div>
          {!chatsLoading && destinations.length === 0 && (
            <p className="rounded-lg bg-stone-50 px-3 py-2 text-xs text-muted">
              No synced Telegram groups yet. Click “Sync my Telegram chats” after connecting an active Telegram account.
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button
              size="sm"
              onClick={handleCreate}
              disabled={!form.title.trim() || !form.target_community_id || createCampaign.isPending}
            >
              {createCampaign.isPending ? "Creating..." : "Create"}
            </Button>
          </div>
        </div>
      )}

      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <input
          className="w-full rounded-lg border border-black/10 bg-white py-2 pl-10 pr-4 text-sm outline-none focus:border-accent"
          placeholder="Search campaigns..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      </div>

      <DataTable columns={columns} data={filteredCampaigns} loading={isLoading} pageSize={25} />
    </div>
  );
}
