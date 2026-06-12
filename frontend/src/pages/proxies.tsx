import { useState } from "react";
import { useProxies, useProxyStats, useCreateProxy, useDeleteProxy, useTestProxy, useImportProxies } from "@/hooks/use-proxies";
import { DataTable } from "@/components/ui/data-table";
import { StatusBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import type { ProxyListItem } from "@/types";
import { createColumnHelper } from "@tanstack/react-table";
import { Plus, Trash2, RefreshCw, Search, Upload } from "lucide-react";

const columnHelper = createColumnHelper<ProxyListItem>();

const columns = [
  columnHelper.accessor("title", {
    header: "Title",
    cell: (info) => (
      <div>
        <p className="font-medium text-ink">{info.getValue()}</p>
        <p className="text-xs text-muted">{info.row.original.host}:{info.row.original.port}</p>
      </div>
    ),
  }),
  columnHelper.accessor("scheme", {
    header: "Scheme",
    cell: (info) => <StatusBadge status={info.getValue() as any} />,
  }),
  columnHelper.accessor("country", {
    header: "Country",
    cell: (info) => info.getValue() ?? "—",
  }),
  columnHelper.accessor("is_working", {
    header: "Status",
    cell: (info) => <StatusBadge status={info.getValue() === null ? "pending" : info.getValue() ? "working" : "failed"} />,
  }),
  columnHelper.accessor("ping_ms", {
    header: "Ping",
    cell: (info) => info.getValue() !== null ? `${info.getValue()}ms` : "—",
  }),
  columnHelper.accessor("in_use_count", {
    header: "In Use",
    cell: (info) => info.getValue(),
  }),
  columnHelper.accessor("created_at", {
    header: "Created",
    cell: (info) => new Date(info.getValue()).toLocaleDateString(),
  }),
];

export default function ProxiesPage() {
  const [showCreate, setShowCreate] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [search, setSearch] = useState("");
  const { data, isLoading, refetch } = useProxies({ search, limit: 500 });
  const { data: stats } = useProxyStats();
  const createProxy = useCreateProxy();
  const deleteProxy = useDeleteProxy();
  const testProxy = useTestProxy();
  const importProxies = useImportProxies();

  const [form, setForm] = useState({ title: "", host: "", port: "1080", scheme: "socks5" });
  const [importText, setImportText] = useState("");

  const handleCreate = async () => {
    await createProxy.mutateAsync({
      title: form.title,
      host: form.host,
      port: parseInt(form.port),
      scheme: form.scheme as any,
    });
    setForm({ title: "", host: "", port: "1080", scheme: "socks5" });
    setShowCreate(false);
  };

  const handleImport = async () => {
    await importProxies.mutateAsync(importText);
    setImportText("");
    setShowImport(false);
  };

  const proxies = data?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Proxies</h1>
          <p className="text-sm text-muted mt-1">
            {stats ? `${stats.working} working · ${stats.total} total` : "Manage proxy servers"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setShowImport(!showImport)}>
            <Upload className="h-4 w-4 mr-1" /> Import
          </Button>
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4 mr-1" /> Refresh
          </Button>
          <Button size="sm" onClick={() => setShowCreate(!showCreate)}>
            <Plus className="h-4 w-4 mr-1" /> Add Proxy
          </Button>
        </div>
      </div>

      {showCreate && (
        <div className="rounded-xl border border-black/5 bg-white p-5 shadow-sm space-y-4">
          <h3 className="text-sm font-semibold text-ink">New Proxy</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            <input className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent" placeholder="Title *" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            <input className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent" placeholder="Host *" value={form.host} onChange={(e) => setForm({ ...form, host: e.target.value })} />
            <input className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent" placeholder="Port" type="number" value={form.port} onChange={(e) => setForm({ ...form, port: e.target.value })} />
            <select className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent bg-white" value={form.scheme} onChange={(e) => setForm({ ...form, scheme: e.target.value })}>
              <option value="socks5">SOCKS5</option>
              <option value="http">HTTP</option>
              <option value="mtproto">MTProto</option>
            </select>
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setShowCreate(false)}>Cancel</Button>
            <Button size="sm" onClick={handleCreate} disabled={!form.title || !form.host || createProxy.isPending}>Create</Button>
          </div>
        </div>
      )}

      {showImport && (
        <div className="rounded-xl border border-black/5 bg-white p-5 shadow-sm space-y-4">
          <h3 className="text-sm font-semibold text-ink">Import Proxies</h3>
          <textarea
            className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent min-h-[120px]"
            placeholder="socks5://user:pass@host:port (one per line)"
            value={importText}
            onChange={(e) => setImportText(e.target.value)}
          />
          <div className="flex justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setShowImport(false)}>Cancel</Button>
            <Button size="sm" onClick={handleImport} disabled={!importText.trim() || importProxies.isPending}>Import</Button>
          </div>
        </div>
      )}

      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <input className="w-full rounded-lg border border-black/10 bg-white py-2 pl-10 pr-4 text-sm outline-none focus:border-accent" placeholder="Search proxies..." value={search} onChange={(e) => setSearch(e.target.value)} />
      </div>

      <DataTable columns={columns} data={proxies} loading={isLoading} pageSize={25} />
    </div>
  );
}