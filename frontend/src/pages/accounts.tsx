import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { createColumnHelper } from "@tanstack/react-table";
import { CheckCircle, Eye, Pencil, Plug, Plus, RefreshCw, Search, Trash2 } from "lucide-react";

import {
  useAccount,
  useAccounts,
  useAccountStats,
  useCheckAccount,
  useCreateAccount,
  useDeleteAccount,
  useUpdateAccount,
} from "@/hooks/use-accounts";
import { useProxies } from "@/hooks/use-proxies";
import { apiClient } from "@/lib/api-client";
import { DataTable } from "@/components/ui/data-table";
import { StatusBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import type { AccountListItem } from "@/types";

const columnHelper = createColumnHelper<AccountListItem>();

interface SettingsData {
  system_config: Record<string, any> | null;
}

function errMessage(error: unknown) {
  const anyErr = error as any;
  return anyErr?.response?.data?.detail ?? anyErr?.message ?? "Request failed";
}

export default function AccountsPage() {
  const [showCreate, setShowCreate] = useState(false);
  const [search, setSearch] = useState("");
  const [detailsId, setDetailsId] = useState<string>();
  const [editAccount, setEditAccount] = useState<AccountListItem | null>(null);
  const [assignAccount, setAssignAccount] = useState<AccountListItem | null>(null);
  const [checkingId, setCheckingId] = useState<string | null>(null);
  const [telegramApiConfigured, setTelegramApiConfigured] = useState(false);
  const { data: accounts, isLoading, refetch } = useAccounts({ search, limit: 500 });
  const { data: stats } = useAccountStats();
  const { data: details } = useAccount(detailsId);
  const { data: proxies } = useProxies({ limit: 500 });
  const createAccount = useCreateAccount();
  const updateAccount = useUpdateAccount();
  const deleteAccount = useDeleteAccount();
  const checkAccount = useCheckAccount();

  const [form, setForm] = useState({ label: "", phone: "", api_id: "", api_hash: "" });
  const [editForm, setEditForm] = useState({ label: "", phone: "", api_id: "", api_hash: "", is_active: true });

  useEffect(() => {
    apiClient
      .get<SettingsData>("/settings/")
      .then((res) => {
        const profile = res.data.system_config?.telegram_api;
        setTelegramApiConfigured(Boolean(profile?.api_id && profile?.api_hash));
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!editAccount) return;
    setEditForm({
      label: editAccount.label,
      phone: editAccount.phone ?? "",
      api_id: "",
      api_hash: "",
      is_active: editAccount.is_active,
    });
  }, [editAccount]);

  const handleCreate = async () => {
    try {
      await createAccount.mutateAsync({
        label: form.label,
        phone: form.phone || null,
        api_id: form.api_id ? parseInt(form.api_id) : null,
        api_hash: form.api_hash || null,
      });
      setForm({ label: "", phone: "", api_id: "", api_hash: "" });
      setShowCreate(false);
      await refetch();
      toast.success("Account created");
    } catch (error) {
      toast.error(errMessage(error));
    }
  };

  const handleCheck = async (id: string) => {
    setCheckingId(id);
    try {
      const result: any = await checkAccount.mutateAsync(id);
      await refetch();
      toast.success(result?.status_message ?? "Account checked");
    } catch (error) {
      toast.error(errMessage(error));
    } finally {
      setCheckingId(null);
    }
  };

  const handleDelete = async (account: AccountListItem) => {
    if (!window.confirm(`Delete account "${account.label}"?`)) return;
    try {
      await deleteAccount.mutateAsync(account.id);
      await refetch();
      toast.success("Account deleted");
    } catch (error) {
      toast.error(errMessage(error));
    }
  };

  const handleEdit = async () => {
    if (!editAccount) return;
    try {
      await updateAccount.mutateAsync({
        id: editAccount.id,
        payload: {
          label: editForm.label,
          phone: editForm.phone || null,
          api_id: editForm.api_id ? parseInt(editForm.api_id) : null,
          api_hash: editForm.api_hash || null,
          is_active: editForm.is_active,
        },
      });
      setEditAccount(null);
      await refetch();
      toast.success("Account updated");
    } catch (error) {
      toast.error(errMessage(error));
    }
  };

  const handleAssignProxy = async (proxyId: string) => {
    if (!assignAccount) return;
    try {
      await updateAccount.mutateAsync({
        id: assignAccount.id,
        payload: { proxy_id: proxyId || null },
      });
      setAssignAccount(null);
      await refetch();
      toast.success("Proxy assigned");
    } catch (error) {
      toast.error(errMessage(error));
    }
  };

  const columns = useMemo(
    () => [
      columnHelper.accessor("label", {
        header: "Label",
        cell: (info) => (
          <div>
            <p className="font-medium text-ink">{info.getValue()}</p>
            {info.row.original.phone && <p className="text-xs text-muted">{info.row.original.phone}</p>}
          </div>
        ),
      }),
      columnHelper.accessor("status", {
        header: "Status",
        cell: (info) => <StatusBadge status={info.getValue()} />,
      }),
      columnHelper.accessor("username", {
        header: "Username",
        cell: (info) => (info.getValue() ? `@${info.getValue()}` : "-"),
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
        cell: (info) => (info.getValue() ? new Date(info.getValue()!).toLocaleDateString() : "-"),
      }),
      columnHelper.accessor("is_active", {
        header: "Active",
        cell: (info) => <StatusBadge status={info.getValue()} />,
      }),
      columnHelper.display({
        id: "actions",
        header: "Actions",
        cell: (info) => {
          const account = info.row.original;
          return (
            <div className="flex min-w-[330px] flex-wrap gap-2">
              <Button variant="secondary" size="sm" onClick={() => handleCheck(account.id)} disabled={checkingId === account.id}>
                <CheckCircle className="mr-1 h-4 w-4" />
                {checkingId === account.id ? "Checking..." : "Check"}
              </Button>
              <Button variant="outline" size="sm" onClick={() => setEditAccount(account)}>
                <Pencil className="mr-1 h-4 w-4" /> Edit
              </Button>
              <Button variant="outline" size="sm" onClick={() => setAssignAccount(account)}>
                <Plug className="mr-1 h-4 w-4" /> Proxy
              </Button>
              <Button variant="outline" size="sm" onClick={() => setDetailsId(account.id)}>
                <Eye className="mr-1 h-4 w-4" /> Details
              </Button>
              <Button variant="destructive" size="sm" onClick={() => handleDelete(account)}>
                <Trash2 className="mr-1 h-4 w-4" /> Delete
              </Button>
            </div>
          );
        },
      }),
    ],
    [checkingId, proxies],
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Accounts</h1>
          <p className="mt-1 text-sm text-muted">
            {stats ? `${stats.active} active / ${stats.total} total` : "Manage Telegram accounts"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="mr-1 h-4 w-4" /> Refresh
          </Button>
          <Button size="sm" onClick={() => setShowCreate(!showCreate)}>
            <Plus className="mr-1 h-4 w-4" /> Add Account
          </Button>
        </div>
      </div>

      {showCreate && (
        <div className="rounded-xl border border-black/5 bg-white p-5 shadow-sm space-y-4">
          <h3 className="text-sm font-semibold text-ink">New Account</h3>
          {telegramApiConfigured && (
            <p className="text-xs text-muted">Using Telegram API profile from settings.</p>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            <input className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent" placeholder="Label *" value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} />
            <input className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent" placeholder="Phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
            <input className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent" placeholder={telegramApiConfigured ? "API ID override" : "API ID"} value={form.api_id} onChange={(e) => setForm({ ...form, api_id: e.target.value })} />
            <input className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent" placeholder={telegramApiConfigured ? "API Hash override" : "API Hash"} value={form.api_hash} onChange={(e) => setForm({ ...form, api_hash: e.target.value })} />
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button size="sm" onClick={handleCreate} disabled={!form.label || createAccount.isPending}>
              {createAccount.isPending ? "Creating..." : "Create"}
            </Button>
          </div>
        </div>
      )}

      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <input className="w-full rounded-lg border border-black/10 bg-white py-2 pl-10 pr-4 text-sm outline-none focus:border-accent" placeholder="Search accounts..." value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>

      <DataTable columns={columns} data={accounts ?? []} loading={isLoading} pageSize={25} />

      {editAccount && (
        <div className="rounded-xl border border-black/5 bg-white p-5 shadow-sm space-y-4">
          <h3 className="text-sm font-semibold text-ink">Edit Account</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <input className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent" value={editForm.label} onChange={(e) => setEditForm({ ...editForm, label: e.target.value })} />
            <input className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent" value={editForm.phone} placeholder="Phone" onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })} />
            <input className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent" value={editForm.api_id} placeholder="API ID override" onChange={(e) => setEditForm({ ...editForm, api_id: e.target.value })} />
            <input className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent" value={editForm.api_hash} placeholder="API Hash override" onChange={(e) => setEditForm({ ...editForm, api_hash: e.target.value })} />
            <label className="flex items-center gap-2 text-sm text-ink">
              <input type="checkbox" checked={editForm.is_active} onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })} />
              Active
            </label>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setEditAccount(null)}>Cancel</Button>
            <Button size="sm" onClick={handleEdit} disabled={!editForm.label || updateAccount.isPending}>Save</Button>
          </div>
        </div>
      )}

      {assignAccount && (
        <div className="rounded-xl border border-black/5 bg-white p-5 shadow-sm space-y-4">
          <h3 className="text-sm font-semibold text-ink">Assign Proxy</h3>
          <select className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent bg-white" defaultValue={assignAccount.proxy_id ?? ""} onChange={(e) => handleAssignProxy(e.target.value)}>
            <option value="">No proxy</option>
            {(proxies?.items ?? []).map((proxy) => (
              <option key={proxy.id} value={proxy.id}>
                {proxy.title} / {proxy.scheme} / {proxy.host}:{proxy.port}
              </option>
            ))}
          </select>
          <p className="text-xs text-muted">Proxy candidates can be approved/imported on the Proxies page before assignment.</p>
          <div className="flex justify-end">
            <Button variant="outline" size="sm" onClick={() => setAssignAccount(null)}>Close</Button>
          </div>
        </div>
      )}

      {detailsId && details && (
        <div className="rounded-xl border border-black/5 bg-white p-5 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-ink">Account Details</h3>
            <Button variant="ghost" size="sm" onClick={() => setDetailsId(undefined)}>Close</Button>
          </div>
          <div className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
            {[
              ["ID", details.id],
              ["Label", details.label],
              ["Phone", details.phone ?? "-"],
              ["Username", details.username ? `@${details.username}` : "-"],
              ["Status", details.status],
              ["Active", String(details.is_active)],
              ["Premium", String(details.is_premium)],
              ["Proxy", details.proxy ? `${details.proxy.title} (${details.proxy.host}:${details.proxy.port})` : "-"],
              ["Session", details.session_name],
              ["Last used", details.last_used_at ? new Date(details.last_used_at).toLocaleString() : "-"],
              ["Last error", details.status_message ?? "-"],
              ["Invites today", String(details.daily_invite_count)],
              ["Success rate", `${(details.success_rate * 100).toFixed(1)}%`],
            ].map(([label, value]) => (
              <div key={label} className="rounded-lg bg-stone-50 p-3">
                <p className="text-xs uppercase text-muted">{label}</p>
                <p className="mt-1 break-words text-ink">{value}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
