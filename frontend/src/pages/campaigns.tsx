import { useMemo, useState } from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Pause, Play, Plus, Search, Square, Trash2 } from "lucide-react";
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
import type { InviteCampaignListItem } from "@/types";

const columnHelper = createColumnHelper<InviteCampaignListItem>();

export default function CampaignsPage() {
  const [showCreate, setShowCreate] = useState(false);
  const [search, setSearch] = useState("");
  const [minActivity, setMinActivity] = useState("30");
  const [minReadiness, setMinReadiness] = useState("20");
  const [planLimit, setPlanLimit] = useState("1000");

  const { data: campaigns, isLoading } = useCampaigns({ skip: 0, limit: 500 });
  const createCampaign = useCreateCampaign();
  const deleteCampaign = useDeleteCampaign();
  const startCampaign = useStartCampaign();
  const pauseCampaign = usePauseCampaign();
  const stopCampaign = useStopCampaign();

  const [form, setForm] = useState({
    title: "",
    target_chat_id: "",
    target_chat_title: "",
    target_chat_username: "",
  });

  const handleCreate = async () => {
    if (!form.title || !form.target_chat_id) return;
    try {
      await createCampaign.mutateAsync({
        title: form.title,
        target_chat_id: parseInt(form.target_chat_id),
        target_chat_title: form.target_chat_title || null,
        target_chat_username: form.target_chat_username || null,
        source_type: "parsed_list",
      });
      setForm({ title: "", target_chat_id: "", target_chat_title: "", target_chat_username: "" });
      setShowCreate(false);
      toast.success("Campaign created");
    } catch {
      toast.error("Failed to create campaign");
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
      toast.error("Could not start campaign. Make sure audience and active accounts are available.");
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
          <div>
            <h3 className="text-sm font-semibold text-ink">New Campaign</h3>
            <p className="mt-1 text-xs text-muted">Audience comes from analyzed and ranked profiles.</p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <input className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent" placeholder="Campaign title *" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            <input className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent" placeholder="Destination Chat ID *" type="number" value={form.target_chat_id} onChange={(e) => setForm({ ...form, target_chat_id: e.target.value })} />
            <input className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent" placeholder="Destination title" value={form.target_chat_title} onChange={(e) => setForm({ ...form, target_chat_title: e.target.value })} />
            <input className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent" placeholder="Destination username" value={form.target_chat_username} onChange={(e) => setForm({ ...form, target_chat_username: e.target.value })} />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button size="sm" onClick={handleCreate} disabled={!form.title || !form.target_chat_id || createCampaign.isPending}>
              {createCampaign.isPending ? "Creating..." : "Create"}
            </Button>
          </div>
        </div>
      )}

      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <input className="w-full rounded-lg border border-black/10 bg-white py-2 pl-10 pr-4 text-sm outline-none focus:border-accent" placeholder="Search campaigns..." value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>

      <DataTable columns={columns} data={filteredCampaigns} loading={isLoading} pageSize={25} />
    </div>
  );
}
