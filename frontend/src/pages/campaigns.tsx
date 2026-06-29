import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { createColumnHelper } from "@tanstack/react-table";
import { BarChart3, FileText, ListChecks, Pause, Play, Plus, Search, Square, Trash2 } from "lucide-react";

import {
  useCampaignLogs,
  useCampaignStats,
  useCampaignTasks,
  useCampaigns,
  useCreateCampaign,
  useDeleteCampaign,
  usePauseCampaign,
  useStartCampaign,
  useStopCampaign,
} from "@/hooks/use-campaigns";
import { useParsedChats } from "@/hooks/use-parser";
import { DataTable } from "@/components/ui/data-table";
import { StatusBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import type { InviteCampaignListItem, InviteLogResponse, InviteTaskResponse } from "@/types";

const campaignColumn = createColumnHelper<InviteCampaignListItem>();
const taskColumn = createColumnHelper<InviteTaskResponse>();
const logColumn = createColumnHelper<InviteLogResponse>();

function errMessage(error: unknown) {
  const anyErr = error as any;
  return anyErr?.response?.data?.detail ?? anyErr?.message ?? "Request failed";
}

export default function CampaignsPage() {
  const [params] = useSearchParams();
  const [showCreate, setShowCreate] = useState(false);
  const [search, setSearch] = useState("");
  const [panel, setPanel] = useState<"tasks" | "stats" | "logs">("tasks");
  const [selectedCampaignId, setSelectedCampaignId] = useState<string>();
  const { data: campaigns, isLoading, refetch } = useCampaigns({ skip: 0, limit: 500 });
  const { data: parsedChats } = useParsedChats({ limit: 500 });
  const { data: tasks, isLoading: tasksLoading } = useCampaignTasks(selectedCampaignId);
  const { data: stats } = useCampaignStats(selectedCampaignId);
  const { data: logs, isLoading: logsLoading } = useCampaignLogs(selectedCampaignId);
  const createCampaign = useCreateCampaign();
  const startCampaign = useStartCampaign();
  const pauseCampaign = usePauseCampaign();
  const stopCampaign = useStopCampaign();
  const deleteCampaign = useDeleteCampaign();

  const [form, setForm] = useState({
    title: "",
    source_type: "parsed_list" as "parsed_list" | "chat" | "uploaded_list",
    source_parsed_chat_id: "",
    target_chat_id: "",
    target_chat_title: "",
    target_chat_username: "",
  });

  useEffect(() => {
    const parsedChatId = params.get("source_parsed_chat_id");
    if (!parsedChatId) return;
    setShowCreate(true);
    setForm((prev) => ({
      ...prev,
      source_type: "parsed_list",
      source_parsed_chat_id: parsedChatId,
    }));
  }, [params]);

  const handleCreate = async () => {
    if (!form.title || !form.target_chat_id) return;
    try {
      await createCampaign.mutateAsync({
        title: form.title,
        target_chat_id: parseInt(form.target_chat_id),
        target_chat_title: form.target_chat_title || null,
        target_chat_username: form.target_chat_username || null,
        source_type: form.source_type,
        source_parsed_chat_id: form.source_type === "parsed_list" ? form.source_parsed_chat_id || null : null,
      });
      setForm({ title: "", source_type: "parsed_list", source_parsed_chat_id: "", target_chat_id: "", target_chat_title: "", target_chat_username: "" });
      setShowCreate(false);
      await refetch();
      toast.success("Campaign created");
    } catch (error) {
      toast.error(errMessage(error));
    }
  };

  const runAction = async (label: string, action: () => Promise<unknown>) => {
    try {
      await action();
      await refetch();
      toast.success(label);
    } catch (error) {
      toast.error(errMessage(error));
    }
  };

  const campaignsFiltered = (campaigns ?? []).filter((campaign) =>
    campaign.title.toLowerCase().includes(search.toLowerCase()),
  );

  const campaignColumns = useMemo(
    () => [
      campaignColumn.accessor("title", {
        header: "Title",
        cell: (info) => <span className="font-medium text-ink">{info.getValue()}</span>,
      }),
      campaignColumn.accessor("status", {
        header: "Status",
        cell: (info) => <StatusBadge status={info.getValue()} />,
      }),
      campaignColumn.accessor("target_chat_title", {
        header: "Target",
        cell: (info) => info.getValue() ?? info.row.original.target_chat_username ?? "-",
      }),
      campaignColumn.accessor("tasks_count", { header: "Tasks", cell: (info) => info.getValue() }),
      campaignColumn.accessor("completed_tasks_count", { header: "Completed", cell: (info) => info.getValue() }),
      campaignColumn.accessor("success_rate", { header: "Success Rate", cell: (info) => `${info.getValue().toFixed(1)}%` }),
      campaignColumn.display({
        id: "actions",
        header: "Actions",
        cell: (info) => {
          const campaign = info.row.original;
          return (
            <div className="flex min-w-[430px] flex-wrap gap-2">
              <Button variant="secondary" size="sm" disabled={startCampaign.isPending} onClick={() => runAction("Campaign started", () => startCampaign.mutateAsync(campaign.id))}>
                <Play className="mr-1 h-4 w-4" /> Start
              </Button>
              <Button variant="outline" size="sm" onClick={() => runAction("Campaign paused", () => pauseCampaign.mutateAsync(campaign.id))}>
                <Pause className="mr-1 h-4 w-4" /> Pause
              </Button>
              <Button variant="outline" size="sm" onClick={() => runAction("Campaign stopped", () => stopCampaign.mutateAsync(campaign.id))}>
                <Square className="mr-1 h-4 w-4" /> Stop
              </Button>
              <Button variant="outline" size="sm" onClick={() => { setSelectedCampaignId(campaign.id); setPanel("tasks"); }}>
                <ListChecks className="mr-1 h-4 w-4" /> Tasks
              </Button>
              <Button variant="outline" size="sm" onClick={() => { setSelectedCampaignId(campaign.id); setPanel("stats"); }}>
                <BarChart3 className="mr-1 h-4 w-4" /> Stats
              </Button>
              <Button variant="outline" size="sm" onClick={() => { setSelectedCampaignId(campaign.id); setPanel("logs"); }}>
                <FileText className="mr-1 h-4 w-4" /> Logs
              </Button>
              <Button variant="destructive" size="sm" onClick={() => {
                if (window.confirm(`Delete campaign "${campaign.title}"?`)) {
                  runAction("Campaign deleted", () => deleteCampaign.mutateAsync(campaign.id));
                }
              }}>
                <Trash2 className="mr-1 h-4 w-4" /> Delete
              </Button>
            </div>
          );
        },
      }),
    ],
    [startCampaign.isPending],
  );

  const taskColumns = useMemo(
    () => [
      taskColumn.accessor("target_user_id", { header: "Target ID", cell: (info) => info.getValue() }),
      taskColumn.accessor("target_username", { header: "Username", cell: (info) => (info.getValue() ? `@${info.getValue()}` : "-") }),
      taskColumn.accessor("account_id", { header: "Account", cell: (info) => <span className="font-mono text-xs">{info.getValue().slice(0, 8)}</span> }),
      taskColumn.accessor("proxy_id", { header: "Proxy", cell: (info) => (info.getValue() ? <span className="font-mono text-xs">{info.getValue()!.slice(0, 8)}</span> : "-") }),
      taskColumn.accessor("status", { header: "Status", cell: (info) => <StatusBadge status={info.getValue()} /> }),
      taskColumn.accessor("error_message", { header: "Error", cell: (info) => info.getValue() ?? "-" }),
      taskColumn.accessor("created_at", { header: "Created", cell: (info) => new Date(info.getValue()).toLocaleString() }),
      taskColumn.accessor("updated_at", { header: "Updated", cell: (info) => new Date(info.getValue()).toLocaleString() }),
    ],
    [],
  );

  const logColumns = useMemo(
    () => [
      logColumn.accessor("action", { header: "Action", cell: (info) => info.getValue() }),
      logColumn.accessor("success", { header: "Success", cell: (info) => <StatusBadge status={info.getValue()} /> }),
      logColumn.accessor("error_code", { header: "Code", cell: (info) => info.getValue() ?? "-" }),
      logColumn.accessor("error_message", { header: "Error", cell: (info) => info.getValue() ?? "-" }),
      logColumn.accessor("created_at", { header: "Created", cell: (info) => new Date(info.getValue()).toLocaleString() }),
    ],
    [],
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Campaigns</h1>
          <p className="mt-1 text-sm text-muted">Manage invite campaigns</p>
        </div>
        <Button size="sm" onClick={() => setShowCreate(!showCreate)}>
          <Plus className="mr-1 h-4 w-4" /> New Campaign
        </Button>
      </div>

      {showCreate && (
        <div className="rounded-xl border border-black/5 bg-white p-5 shadow-sm space-y-4">
          <h3 className="text-sm font-semibold text-ink">New Campaign</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <input className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent" placeholder="Title *" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            <select className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent bg-white" value={form.source_type} onChange={(e) => setForm({ ...form, source_type: e.target.value as any })}>
              <option value="parsed_list">Parsed list</option>
              <option value="chat">Chat</option>
              <option value="uploaded_list">Uploaded list</option>
            </select>
            {form.source_type === "parsed_list" && (
              <select className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent bg-white sm:col-span-2" value={form.source_parsed_chat_id} onChange={(e) => setForm({ ...form, source_parsed_chat_id: e.target.value })}>
                <option value="">Select ParsedChat</option>
                {(parsedChats?.items ?? []).map((chat) => (
                  <option key={chat.id} value={chat.id}>
                    {chat.title ?? chat.id} / {chat.participants_count ?? 0} users
                  </option>
                ))}
              </select>
            )}
            <input className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent" placeholder="Target Chat ID *" type="number" value={form.target_chat_id} onChange={(e) => setForm({ ...form, target_chat_id: e.target.value })} />
            <input className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent" placeholder="Target Chat Username" value={form.target_chat_username} onChange={(e) => setForm({ ...form, target_chat_username: e.target.value })} />
            <input className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent sm:col-span-2" placeholder="Target Chat Title" value={form.target_chat_title} onChange={(e) => setForm({ ...form, target_chat_title: e.target.value })} />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button size="sm" onClick={handleCreate} disabled={!form.title || !form.target_chat_id || (form.source_type === "parsed_list" && !form.source_parsed_chat_id) || createCampaign.isPending}>
              {createCampaign.isPending ? "Creating..." : "Create"}
            </Button>
          </div>
        </div>
      )}

      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <input className="w-full rounded-lg border border-black/10 bg-white py-2 pl-10 pr-4 text-sm outline-none focus:border-accent" placeholder="Search campaigns..." value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>

      <DataTable columns={campaignColumns} data={campaignsFiltered} loading={isLoading} pageSize={25} />

      {selectedCampaignId && (
        <div className="rounded-xl border border-black/5 bg-white p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex gap-2">
              <Button size="sm" variant={panel === "tasks" ? "secondary" : "outline"} onClick={() => setPanel("tasks")}>Tasks</Button>
              <Button size="sm" variant={panel === "stats" ? "secondary" : "outline"} onClick={() => setPanel("stats")}>Stats</Button>
              <Button size="sm" variant={panel === "logs" ? "secondary" : "outline"} onClick={() => setPanel("logs")}>Logs</Button>
            </div>
            <Button variant="ghost" size="sm" onClick={() => setSelectedCampaignId(undefined)}>Close</Button>
          </div>

          {panel === "tasks" && <DataTable columns={taskColumns} data={tasks ?? []} loading={tasksLoading} pageSize={25} />}
          {panel === "logs" && <DataTable columns={logColumns} data={logs ?? []} loading={logsLoading} pageSize={25} />}
          {panel === "stats" && stats && (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {[
                ["Total tasks", stats.total_tasks],
                ["Completed", stats.completed_tasks],
                ["Failed", stats.failed_tasks],
                ["Floodwait", stats.floodwait_tasks],
                ["Success rate", `${stats.success_rate.toFixed(1)}%`],
                ["Invites today", stats.invites_today],
                ["Active accounts", stats.active_accounts],
                ["Status", stats.status],
              ].map(([label, value]) => (
                <div key={label} className="rounded-lg bg-stone-50 p-3">
                  <p className="text-xs uppercase text-muted">{label}</p>
                  <p className="mt-1 text-lg font-semibold text-ink">{value}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
