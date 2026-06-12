import { useState } from "react";
import { useCampaigns, useCreateCampaign, useDeleteCampaign } from "@/hooks/use-campaigns";
import { DataTable } from "@/components/ui/data-table";
import { StatusBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import type { InviteCampaignListItem } from "@/types";
import { createColumnHelper } from "@tanstack/react-table";
import { Plus, Trash2, Play, Pause, Square, Search } from "lucide-react";

const columnHelper = createColumnHelper<InviteCampaignListItem>();

const columns = [
  columnHelper.accessor("title", {
    header: "Title",
    cell: (info) => <span className="font-medium text-ink">{info.getValue()}</span>,
  }),
  columnHelper.accessor("status", {
    header: "Status",
    cell: (info) => <StatusBadge status={info.getValue()} />,
  }),
  columnHelper.accessor("target_chat_title", {
    header: "Target",
    cell: (info) => info.getValue() ?? info.row.original.target_chat_username ?? "—",
  }),
  columnHelper.accessor("tasks_count", {
    header: "Tasks",
    cell: (info) => info.getValue(),
  }),
  columnHelper.accessor("completed_tasks_count", {
    header: "Completed",
    cell: (info) => info.getValue(),
  }),
  columnHelper.accessor("success_rate", {
    header: "Success Rate",
    cell: (info) => `${info.getValue().toFixed(1)}%`,
  }),
  columnHelper.accessor("created_at", {
    header: "Created",
    cell: (info) => new Date(info.getValue()).toLocaleDateString(),
  }),
];

export default function CampaignsPage() {
  const [showCreate, setShowCreate] = useState(false);
  const [search, setSearch] = useState("");
  const { data: campaigns, isLoading } = useCampaigns({ skip: 0, limit: 500 });
  const createCampaign = useCreateCampaign();
  const deleteCampaign = useDeleteCampaign();

  const [form, setForm] = useState({
    title: "",
    target_chat_id: "",
    target_chat_title: "",
    target_chat_username: "",
  });

  const handleCreate = async () => {
    if (!form.title || !form.target_chat_id) return;
    await createCampaign.mutateAsync({
      title: form.title,
      target_chat_id: parseInt(form.target_chat_id),
      target_chat_title: form.target_chat_title || null,
      target_chat_username: form.target_chat_username || null,
      source_type: "parsed_list",
    });
    setForm({ title: "", target_chat_id: "", target_chat_title: "", target_chat_username: "" });
    setShowCreate(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Campaigns</h1>
          <p className="text-sm text-muted mt-1">Manage invite campaigns</p>
        </div>
        <Button size="sm" onClick={() => setShowCreate(!showCreate)}>
          <Plus className="h-4 w-4 mr-1" /> New Campaign
        </Button>
      </div>

      {showCreate && (
        <div className="rounded-xl border border-black/5 bg-white p-5 shadow-sm space-y-4">
          <h3 className="text-sm font-semibold text-ink">New Campaign</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <input className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent" placeholder="Title *" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            <input className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent" placeholder="Target Chat ID *" type="number" value={form.target_chat_id} onChange={(e) => setForm({ ...form, target_chat_id: e.target.value })} />
            <input className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent" placeholder="Target Chat Title" value={form.target_chat_title} onChange={(e) => setForm({ ...form, target_chat_title: e.target.value })} />
            <input className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent" placeholder="Target Chat Username" value={form.target_chat_username} onChange={(e) => setForm({ ...form, target_chat_username: e.target.value })} />
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

      <DataTable columns={columns} data={campaigns ?? []} loading={isLoading} pageSize={25} />
    </div>
  );
}