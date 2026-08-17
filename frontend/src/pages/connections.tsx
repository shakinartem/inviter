import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { createColumnHelper } from "@tanstack/react-table";
import { Cable, CheckCircle2, Plus, RefreshCw, ShieldCheck, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  useCheckConnection,
  useConnections,
  useCreateConnection,
  useDeleteConnection,
  type MessengerConnection,
} from "@/hooks/use-connections";

const columnHelper = createColumnHelper<MessengerConnection>();

export default function ConnectionsPage() {
  const [showCreate, setShowCreate] = useState(false);
  const [label, setLabel] = useState("");
  const [botToken, setBotToken] = useState("");
  const { data: connections, isLoading } = useConnections();
  const createConnection = useCreateConnection();
  const checkConnection = useCheckConnection();
  const deleteConnection = useDeleteConnection();

  const handleCreateDiscord = async () => {
    if (!label.trim() || !botToken.trim()) return;
    try {
      const connection = await createConnection.mutateAsync({
        platform: "discord",
        label: label.trim(),
        auth_type: "bot_token",
        credentials: { bot_token: botToken.trim() },
      });
      setLabel("");
      setBotToken("");
      setShowCreate(false);
      toast.success("Discord connection saved. Checking access…");
      await checkConnection.mutateAsync(connection.id);
      toast.success("Discord connection is active");
    } catch {
      toast.error("Could not connect Discord. Check the bot token and API permissions.");
    }
  };

  const columns = useMemo(
    () => [
      columnHelper.accessor("label", {
        header: "Connection",
        cell: (info) => {
          const item = info.row.original;
          return (
            <div>
              <p className="font-medium text-ink">{item.label}</p>
              <p className="text-xs capitalize text-muted">
                {item.platform} · {item.auth_type.replaceAll("_", " ")}
              </p>
            </div>
          );
        },
      }),
      columnHelper.accessor("status", {
        header: "Status",
        cell: (info) => <StatusBadge status={info.getValue()} />,
      }),
      columnHelper.accessor("username", {
        header: "Identity",
        cell: (info) => info.getValue() ? `@${info.getValue()}` : info.row.original.external_account_id ?? "—",
      }),
      columnHelper.accessor("health_score", {
        header: "Health",
        cell: (info) => `${Math.round(info.getValue())}/100`,
      }),
      columnHelper.display({
        id: "capabilities",
        header: "Capabilities",
        cell: (info) => {
          const enabled = Object.entries(info.row.original.capabilities ?? {})
            .filter(([, value]) => value)
            .map(([key]) => key.replaceAll("_", " "))
            .slice(0, 3);
          return (
            <div className="flex max-w-64 flex-wrap gap-1">
              {enabled.length ? enabled.map((name) => (
                <span key={name} className="rounded-full bg-stone-100 px-2 py-1 text-[10px] text-muted">
                  {name}
                </span>
              )) : <span className="text-xs text-muted">No connector capabilities</span>}
            </div>
          );
        },
      }),
      columnHelper.display({
        id: "actions",
        header: "Actions",
        cell: (info) => {
          const item = info.row.original;
          return (
            <div className="flex gap-1">
              <Button
                size="sm"
                variant="outline"
                disabled={checkConnection.isPending || !item.connector_available}
                onClick={async () => {
                  try {
                    await checkConnection.mutateAsync(item.id);
                    toast.success("Connection checked");
                  } catch {
                    toast.error("Connection check failed");
                  }
                }}
              >
                <RefreshCw className="h-3.5 w-3.5" />
              </Button>
              {item.platform !== "telegram" && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={async () => {
                    try {
                      await deleteConnection.mutateAsync(item.id);
                      toast.success("Connection removed");
                    } catch {
                      toast.error("Could not remove connection");
                    }
                  }}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              )}
            </div>
          );
        },
      }),
    ],
    [checkConnection.isPending, deleteConnection.isPending],
  );

  const discordCount = (connections ?? []).filter((item) => item.platform === "discord").length;
  const activeCount = (connections ?? []).filter((item) => item.status === "active").length;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Connections</h1>
          <p className="mt-1 text-sm text-muted">
            Messenger identities and bots used by Discovery, Intelligence and Actions.
          </p>
        </div>
        <Button size="sm" onClick={() => setShowCreate((value) => !value)}>
          <Plus className="mr-1 h-4 w-4" /> Add Discord bot
        </Button>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted">
            <Cable className="h-4 w-4" /> Connections
          </div>
          <p className="mt-3 text-2xl font-semibold text-ink">{connections?.length ?? 0}</p>
        </div>
        <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted">
            <CheckCircle2 className="h-4 w-4" /> Active
          </div>
          <p className="mt-3 text-2xl font-semibold text-ink">{activeCount}</p>
        </div>
        <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted">
            <ShieldCheck className="h-4 w-4" /> Discord
          </div>
          <p className="mt-3 text-2xl font-semibold text-ink">{discordCount}</p>
        </div>
      </div>

      {showCreate && (
        <div className="space-y-4 rounded-xl border border-black/5 bg-white p-5 shadow-sm">
          <div>
            <h3 className="text-sm font-semibold text-ink">Connect Discord bot</h3>
            <p className="mt-1 text-xs text-muted">
              Use a Discord application bot token. Normal user-account tokens/self-bots are not supported.
              The token is encrypted before it is stored.
            </p>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <input
              className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent"
              placeholder="Label, e.g. Community Research Bot"
              value={label}
              onChange={(event) => setLabel(event.target.value)}
            />
            <input
              className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent"
              placeholder="Discord bot token"
              type="password"
              autoComplete="off"
              value={botToken}
              onChange={(event) => setBotToken(event.target.value)}
            />
          </div>
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-muted">
              Telegram sessions are still managed in <Link to="/accounts" className="font-medium text-ink underline">Accounts</Link> during migration.
            </p>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => setShowCreate(false)}>Cancel</Button>
              <Button
                size="sm"
                disabled={!label.trim() || !botToken.trim() || createConnection.isPending}
                onClick={handleCreateDiscord}
              >
                {createConnection.isPending ? "Connecting…" : "Save & check"}
              </Button>
            </div>
          </div>
        </div>
      )}

      <DataTable columns={columns} data={connections ?? []} loading={isLoading} pageSize={25} />
    </div>
  );
}
