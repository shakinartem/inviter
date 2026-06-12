import { useState } from "react";
import { useAccounts, useAccountStats, useCreateAccount, useUpdateAccountStatus, useDeleteAccount, useUploadSession, useCheckAccount } from "@/hooks/use-accounts";
import { DataTable } from "@/components/ui/data-table";
import { StatusBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import type { AccountListItem } from "@/types";
import { createColumnHelper } from "@tanstack/react-table";
import { Plus, Upload, CheckCircle, Trash2, RefreshCw, Search } from "lucide-react";

const columnHelper = createColumnHelper<AccountListItem>();

const columns = [
  columnHelper.accessor("label", {
    header: "Label",
    cell: (info) => (
      <div>
        <p className="font-medium text-ink">{info.getValue()}</p>
        {info.row.original.phone && (
          <p className="text-xs text-muted">{info.row.original.phone}</p>
        )}
      </div>
    ),
  }),
  columnHelper.accessor("status", {
    header: "Status",
    cell: (info) => <StatusBadge status={info.getValue()} />,
  }),
  columnHelper.accessor("username", {
    header: "Username",
    cell: (info) => info.getValue() ? `@${info.getValue()}` : "—",
  }),
  columnHelper.accessor("is_premium", {
    header: "Premium",
    cell: (info) => <StatusBadge status={info.getValue()} />,
  }),
  columnHelper.accessor("daily_invite_count", {
    header: "Invites Today",
    cell: (info) => info.getValue(),
  }),
  columnHelper.accessor("success_rate", {
    header: "Success Rate",
    cell: (info) => `${(info.getValue() * 100).toFixed(1)}%`,
  }),
  columnHelper.accessor("last_used_at", {
    header: "Last Used",
    cell: (info) => {
      const val = info.getValue();
      return val ? new Date(val).toLocaleDateString() : "—";
    },
  }),
  columnHelper.accessor("is_active", {
    header: "Active",
    cell: (info) => <StatusBadge status={info.getValue()} />,
  }),
];

export default function AccountsPage() {
  const [showCreate, setShowCreate] = useState(false);
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const { data: accounts, isLoading, refetch } = useAccounts({ search, limit: 500 });
  const { data: stats } = useAccountStats();
  const createAccount = useCreateAccount();
  const updateStatus = useUpdateAccountStatus();
  const deleteAccount = useDeleteAccount();
  const uploadSession = useUploadSession();
  const checkAccount = useCheckAccount();

  const [form, setForm] = useState({ label: "", phone: "", api_id: "", api_hash: "" });

  const handleCreate = async () => {
    await createAccount.mutateAsync({
      label: form.label,
      phone: form.phone || null,
      api_id: form.api_id ? parseInt(form.api_id) : null,
      api_hash: form.api_hash || null,
    });
    setForm({ label: "", phone: "", api_id: "", api_hash: "" });
    setShowCreate(false);
  };

  const handleFileUpload = async (accountId: string, e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    await uploadSession.mutateAsync({ accountId, file });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Accounts</h1>
          <p className="text-sm text-muted mt-1">
            {stats ? `${stats.active} active · ${stats.total} total` : "Manage Telegram accounts"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4 mr-1" /> Refresh
          </Button>
          <Button size="sm" onClick={() => setShowCreate(!showCreate)}>
            <Plus className="h-4 w-4 mr-1" /> Add Account
          </Button>
        </div>
      </div>

      {/* Create Form */}
      {showCreate && (
        <div className="rounded-xl border border-black/5 bg-white p-5 shadow-sm space-y-4">
          <h3 className="text-sm font-semibold text-ink">New Account</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <input
              className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent"
              placeholder="Label *"
              value={form.label}
              onChange={(e) => setForm({ ...form, label: e.target.value })}
            />
            <input
              className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent"
              placeholder="Phone (+79991234567)"
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
            />
            <input
              className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent"
              placeholder="API ID"
              value={form.api_id}
              onChange={(e) => setForm({ ...form, api_id: e.target.value })}
            />
            <input
              className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent"
              placeholder="API Hash"
              value={form.api_hash}
              onChange={(e) => setForm({ ...form, api_hash: e.target.value })}
            />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button size="sm" onClick={handleCreate} disabled={!form.label || createAccount.isPending}>
              {createAccount.isPending ? "Creating..." : "Create"}
            </Button>
          </div>
        </div>
      )}

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <input
          className="w-full rounded-lg border border-black/10 bg-white py-2 pl-10 pr-4 text-sm outline-none focus:border-accent"
          placeholder="Search accounts..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {/* Table */}
      <DataTable
        columns={columns}
        data={accounts ?? []}
        loading={isLoading}
        pageSize={25}
      />

      {/* Bulk actions footer */}
      {selectedId && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 rounded-xl border border-black/5 bg-white p-3 shadow-lg flex items-center gap-2">
          <span className="text-sm text-muted mr-2">Selected: {selectedId.slice(0, 8)}...</span>
          <Button variant="secondary" size="sm">
            <CheckCircle className="h-4 w-4 mr-1" /> Check
          </Button>
          <label className="cursor-pointer">
            <Button variant="secondary" size="sm" asChild>
              <span><Upload className="h-4 w-4 mr-1" /> Upload .session</span>
            </Button>
            <input
              type="file"
              accept=".session"
              className="hidden"
              onChange={(e) => handleFileUpload(selectedId, e)}
            />
          </label>
          <Button variant="destructive" size="sm" onClick={() => deleteAccount.mutate(selectedId)}>
            <Trash2 className="h-4 w-4 mr-1" /> Delete
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setSelectedId(null)}>Dismiss</Button>
        </div>
      )}
    </div>
  );
}