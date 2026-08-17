import { useMemo, useState } from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Globe, Search, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { StatusBadge } from "@/components/ui/status-badge";
import { useEnrichCommunity } from "@/hooks/use-intelligence";
import { useParsedChats, useParserStats, useParseSearch } from "@/hooks/use-parser";
import type { ParsedChatListItem } from "@/types";

const columnHelper = createColumnHelper<ParsedChatListItem>();

type ParserSource = "telegram" | "tgstat" | "telemetr";

export default function ParserPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [search, setSearch] = useState("");
  const [source, setSource] = useState<ParserSource>("telegram");
  const { data, isLoading } = useParsedChats({ search, limit: 500 });
  const { data: stats } = useParserStats();
  const parseSearch = useParseSearch();
  const enrichCommunity = useEnrichCommunity();

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    try {
      await parseSearch.mutateAsync({
        query: searchQuery.trim(),
        source,
        limit: 100,
      });
    } catch {
      toast.error("Discovery failed");
    }
  };

  const handleEnrich = async (community: ParsedChatListItem) => {
    try {
      const result = await enrichCommunity.mutateAsync({
        communityId: community.id,
        payload: {
          member_limit: 2_000,
          message_limit: 10_000,
          lookback_days: 30,
        },
      });
      toast.success(
        `Analyzed ${result.audience_profiles} people · quality ${result.quality_score.toFixed(1)}`,
      );
    } catch {
      toast.error("Community analysis failed. Check that an active account can access this community.");
    }
  };

  const columns = useMemo(
    () => [
      columnHelper.accessor("title", {
        header: "Community",
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
        cell: (info) => <StatusBadge status={(info.getValue() as any) ?? "chat"} />,
      }),
      columnHelper.accessor("participants_count", {
        header: "Members",
        cell: (info) => info.getValue()?.toLocaleString() ?? "—",
      }),
      columnHelper.accessor("niche", {
        header: "Discovery signal",
        cell: (info) => info.getValue() ?? "—",
      }),
      columnHelper.accessor("source", {
        header: "Source",
        cell: (info) => info.getValue(),
      }),
      columnHelper.accessor("created_at", {
        header: "Found",
        cell: (info) => new Date(info.getValue()).toLocaleDateString(),
      }),
      columnHelper.display({
        id: "intelligence",
        header: "Intelligence",
        cell: (info) => (
          <Button
            size="sm"
            variant="outline"
            disabled={enrichCommunity.isPending}
            onClick={() => handleEnrich(info.row.original)}
          >
            <Sparkles className="mr-1 h-3.5 w-3.5" />
            {enrichCommunity.isPending ? "Analyzing..." : "Analyze audience"}
          </Button>
        ),
      }),
    ],
    [enrichCommunity.isPending],
  );

  const chats = data?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Discovery</h1>
          <p className="mt-1 text-sm text-muted">
            {stats
              ? `${stats.total_chats} communities · ${stats.total_parses} discovery runs`
              : "Search communities, then measure the audience behind them"}
          </p>
        </div>
      </div>

      <div className="space-y-4 rounded-xl border border-black/5 bg-white p-5 shadow-sm">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
          <Globe className="h-4 w-4" /> Discover communities
        </h3>
        <div className="flex gap-3">
          <input
            className="flex-1 rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent"
            placeholder="Enter niche or keywords (e.g. real estate Moscow, AI, trading)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          />
          <div className="flex gap-2">
            <select
              value={source}
              onChange={(e) => setSource(e.target.value as ParserSource)}
              className="rounded-lg border border-black/10 bg-white px-3 py-2 text-sm outline-none focus:border-accent"
            >
              <option value="telegram">Telegram Search</option>
              <option value="tgstat">TGStat</option>
              <option value="telemetr">Telemetr</option>
            </select>
            <Button onClick={handleSearch} disabled={!searchQuery.trim() || parseSearch.isPending}>
              {parseSearch.isPending ? "Searching..." : "Search"}
            </Button>
          </div>
        </div>
        <p className="text-xs text-muted">
          After discovery, analyze a community to create a deduplicated audience and activity snapshot.
        </p>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
        <input
          className="w-full rounded-lg border border-black/10 bg-white py-2 pl-10 pr-4 text-sm outline-none focus:border-accent"
          placeholder="Filter communities..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <DataTable
        columns={columns}
        data={chats}
        loading={isLoading || parseSearch.isPending}
        pageSize={25}
      />
    </div>
  );
}
