import { useState } from "react";
import { useParsedChats, useParserStats, useParseSearch, useDeleteParsedChat } from "@/hooks/use-parser";
import { DataTable } from "@/components/ui/data-table";
import { StatusBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import type { ParsedChatListItem } from "@/types";
import { createColumnHelper } from "@tanstack/react-table";
import { Search, Trash2, RefreshCw, Globe } from "lucide-react";

const columnHelper = createColumnHelper<ParsedChatListItem>();

const columns = [
  columnHelper.accessor("title", {
    header: "Title",
    cell: (info) => (
      <div>
        <p className="font-medium text-ink">{info.getValue() ?? "—"}</p>
        {info.row.original.username && (
          <p className="text-xs text-muted">@{info.row.original.username}</p>
        )}
      </div>
    ),
  }),
  columnHelper.accessor("chat_type", {
    header: "Type",
    cell: (info) => <StatusBadge status={info.getValue() as any ?? "chat"} />,
  }),
  columnHelper.accessor("participants_count", {
    header: "Members",
    cell: (info) => info.getValue()?.toLocaleString() ?? "—",
  }),
  columnHelper.accessor("category", {
    header: "Category",
    cell: (info) => info.getValue() ?? "—",
  }),
  columnHelper.accessor("niche", {
    header: "Niche",
    cell: (info) => info.getValue() ?? "—",
  }),
  columnHelper.accessor("language", {
    header: "Lang",
    cell: (info) => info.getValue()?.toUpperCase() ?? "—",
  }),
  columnHelper.accessor("source", {
    header: "Source",
    cell: (info) => info.getValue(),
  }),
  columnHelper.accessor("created_at", {
    header: "Found",
    cell: (info) => new Date(info.getValue()).toLocaleDateString(),
  }),
];

export default function ParserPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [search, setSearch] = useState("");
  const { data, isLoading } = useParsedChats({ search, limit: 500 });
  const { data: stats } = useParserStats();
  const parseSearch = useParseSearch();
  const deleteChat = useDeleteParsedChat();

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    await parseSearch.mutateAsync({
      query: searchQuery,
      source: "telegram",
      limit: 100,
    });
  };

  const chats = data?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Parser</h1>
          <p className="text-sm text-muted mt-1">
            {stats ? `${stats.total_chats} chats · ${stats.total_parses} parses` : "Search and discover Telegram chats"}
          </p>
        </div>
      </div>

      {/* Search Form */}
      <div className="rounded-xl border border-black/5 bg-white p-5 shadow-sm space-y-4">
        <h3 className="text-sm font-semibold text-ink flex items-center gap-2">
          <Globe className="h-4 w-4" /> Search Telegram Chats
        </h3>
        <div className="flex gap-3">
          <input
            className="flex-1 rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent"
            placeholder="Enter niche or keywords (e.g., crypto, ai, trading)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />
          <div className="flex gap-2">
            <select className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent bg-white">
              <option value="telegram">Telegram Search</option>
              <option value="tgstat">TGStat</option>
              <option value="telemetr">Telemetr</option>
            </select>
            <Button onClick={handleSearch} disabled={!searchQuery.trim() || parseSearch.isPending}>
              {parseSearch.isPending ? "Searching..." : "Search"}
            </Button>
          </div>
        </div>
      </div>

      {/* Filter */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <input
          className="w-full rounded-lg border border-black/10 bg-white py-2 pl-10 pr-4 text-sm outline-none focus:border-accent"
          placeholder="Filter results..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <DataTable columns={columns} data={chats} loading={isLoading || parseSearch.isPending} pageSize={25} />
    </div>
  );
}