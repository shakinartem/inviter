import { useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { createColumnHelper } from "@tanstack/react-table";
import { Activity, CheckCircle, Eye, PlaySquare, RefreshCw, Search, ThumbsDown, Trash2, Users, XCircle } from "lucide-react";

import {
  useCreateMockParsedUsers,
  useDeleteParsedChat,
  useParsedChats,
  useParsedUsers,
  useParserStats,
  useParseSearch,
} from "@/hooks/use-parser";
import { useAnalyzeSource, useDeleteSource, useRejectSource, useSearchSources, useSelectSource, useSourceCandidates } from "@/hooks/use-source-discovery";
import { DataTable } from "@/components/ui/data-table";
import { StatusBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import type { ParsedChatListItem, ParsedUserResponse } from "@/types";

const chatColumn = createColumnHelper<ParsedChatListItem>();
const userColumn = createColumnHelper<ParsedUserResponse>();

interface SourceCandidateItem {
  id: string;
  source_type: string;
  title: string | null;
  username: string | null;
  url: string | null;
  tgstat_url: string | null;
  category: string | null;
  subscribers_count: number | null;
  status: string;
  total_score: number | null;
  discovered_by_query: string | null;
  discovered_at: string | null;
  created_at: string;
}

const sourceColumn = createColumnHelper<SourceCandidateItem>();

function errMessage(error: unknown) {
  const anyErr = error as any;
  return anyErr?.response?.data?.detail ?? anyErr?.message ?? "Request failed";
}

export default function ParserPage() {
  const navigate = useNavigate();

  // Tab state
  const [activeTab, setActiveTab] = useState<"discovery" | "parse" | "lists">("discovery");

  // Parse tab
  const [searchQuery, setSearchQuery] = useState("");
  const [search, setSearch] = useState("");
  const [sourceType, setSourceType] = useState<"telegram" | "manual">("manual");
  const [mockTitle, setMockTitle] = useState("Mock audience");
  const [mockCount, setMockCount] = useState("10");
  const [mockPrefix, setMockPrefix] = useState("lead");
  const [selectedChatId, setSelectedChatId] = useState<string>();
  const { data, isLoading, refetch } = useParsedChats({ search, limit: 500 });
  const { data: stats } = useParserStats();
  const { data: users, isLoading: usersLoading } = useParsedUsers(selectedChatId);
  const parseSearch = useParseSearch();
  const createMock = useCreateMockParsedUsers();
  const deleteChat = useDeleteParsedChat();

  // Discovery tab
  const [discoveryQuery, setDiscoveryQuery] = useState("");
  const [discoveryCategory, setDiscoveryCategory] = useState("");
  const [discoveryLimit, setDiscoveryLimit] = useState("20");
  const { data: sourcesData, isLoading: sourcesLoading, refetch: refetchSources } = useSourceCandidates();
  const searchSources = useSearchSources();
  const analyzeSource = useAnalyzeSource();
  const selectSource = useSelectSource();
  const rejectSource = useRejectSource();
  const deleteSource = useDeleteSource();
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);
  const [expandedSource, setExpandedSource] = useState<string | null>(null);

  const [analyzeResults, setAnalyzeResults] = useState<Record<string, any>>({});

  const handleParse = async () => {
    try {
      if (sourceType === "manual") {
        await createMock.mutateAsync({
          title: mockTitle,
          count: parseInt(mockCount) || 10,
          username_prefix: mockPrefix || "lead",
        });
        toast.success("Parsed list created");
      } else {
        await parseSearch.mutateAsync({ query: searchQuery, source: "telegram", limit: 100 });
        toast.success("Parse finished");
      }
      await refetch();
    } catch (error) {
      toast.error(errMessage(error));
    }
  };

  const handleDelete = async (chat: ParsedChatListItem) => {
    if (!window.confirm(`Delete parsed list "${chat.title ?? chat.id}"?`)) return;
    try {
      await deleteChat.mutateAsync(chat.id);
      if (selectedChatId === chat.id) setSelectedChatId(undefined);
      await refetch();
      toast.success("Parsed list deleted");
    } catch (error) {
      toast.error(errMessage(error));
    }
  };

  // Discovery handlers
  const handleDiscoverySearch = async () => {
    if (!discoveryQuery.trim()) return;
    try {
      await searchSources.mutateAsync({
        query: discoveryQuery,
        limit: parseInt(discoveryLimit) || 20,
        category: discoveryCategory || undefined,
      });
      toast.success("Search completed");
      await refetchSources();
    } catch (error) {
      toast.error(errMessage(error));
    }
  };

  const handleAnalyze = async (sourceId: string) => {
    setAnalyzingId(sourceId);
    try {
      const result: any = await analyzeSource.mutateAsync(sourceId);
      setAnalyzeResults((prev) => ({ ...prev, [sourceId]: result }));
      toast.success(`Score: ${result.score.total_score}/100`);
    } catch (error) {
      toast.error(errMessage(error));
    } finally {
      setAnalyzingId(null);
    }
  };

  const handleSelect = async (sourceId: string) => {
    try {
      await selectSource.mutateAsync(sourceId);
      toast.success("Source selected");
      await refetchSources();
    } catch (error) {
      toast.error(errMessage(error));
    }
  };

  const handleReject = async (sourceId: string) => {
    try {
      await rejectSource.mutateAsync(sourceId);
      toast.success("Source rejected");
      await refetchSources();
    } catch (error) {
      toast.error(errMessage(error));
    }
  };

  const handleDeleteSource = async (sourceId: string) => {
    if (!window.confirm("Delete this source candidate?")) return;
    try {
      await deleteSource.mutateAsync(sourceId);
      toast.success("Source deleted");
      await refetchSources();
    } catch (error) {
      toast.error(errMessage(error));
    }
  };

  const chatColumns = useMemo(
    () => [
      chatColumn.accessor("id", {
        header: "ID",
        cell: (info) => <span className="font-mono text-xs">{info.getValue().slice(0, 8)}</span>,
      }),
      chatColumn.accessor("title", {
        header: "Title",
        cell: (info) => (
          <div>
            <p className="font-medium text-ink">{info.getValue() ?? "-"}</p>
            {info.row.original.username && <p className="text-xs text-muted">@{info.row.original.username}</p>}
          </div>
        ),
      }),
      chatColumn.accessor("source", {
        header: "Source",
        cell: (info) => info.getValue(),
      }),
      chatColumn.accessor("participants_count", {
        header: "Users",
        cell: (info) => info.getValue()?.toLocaleString() ?? "-",
      }),
      chatColumn.accessor("created_at", {
        header: "Created",
        cell: (info) => new Date(info.getValue()).toLocaleString(),
      }),
      chatColumn.accessor("is_active", {
        header: "Status",
        cell: (info) => <StatusBadge status={info.getValue() as any} />,
      }),
      chatColumn.display({
        id: "actions",
        header: "Actions",
        cell: (info) => {
          const chat = info.row.original;
          return (
            <div className="flex min-w-[280px] flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={() => setSelectedChatId(chat.id)}>
                <Eye className="mr-1 h-4 w-4" /> Users
              </Button>
              <Button variant="secondary" size="sm" onClick={() => navigate(`/campaigns?source_parsed_chat_id=${chat.id}`)}>
                <PlaySquare className="mr-1 h-4 w-4" /> Campaign
              </Button>
              <Button variant="destructive" size="sm" onClick={() => handleDelete(chat)}>
                <Trash2 className="mr-1 h-4 w-4" /> Delete
              </Button>
            </div>
          );
        },
      }),
    ],
    [navigate, selectedChatId],
  );

  const userColumns = useMemo(
    () => [
      userColumn.accessor("user_id", { header: "User ID", cell: (info) => info.getValue() }),
      userColumn.accessor("username", { header: "Username", cell: (info) => (info.getValue() ? `@${info.getValue()}` : "-") }),
      userColumn.accessor("first_name", { header: "First Name", cell: (info) => info.getValue() ?? "-" }),
      userColumn.accessor("is_bot", { header: "Bot", cell: (info) => <StatusBadge status={info.getValue()} /> }),
      userColumn.accessor("is_scam", { header: "Scam", cell: (info) => <StatusBadge status={info.getValue()} /> }),
      userColumn.accessor("is_fake", { header: "Fake", cell: (info) => <StatusBadge status={info.getValue()} /> }),
      userColumn.accessor("status", { header: "Status", cell: (info) => info.getValue() ?? "-" }),
    ],
    [],
  );

  const sourceColumns = useMemo(
    () => [
      sourceColumn.accessor("title", {
        header: "Title",
        cell: (info) => (
          <div>
            <p className="font-medium text-ink">{info.getValue() ?? "-"}</p>
            {info.row.original.username && <p className="text-xs text-muted">@{info.row.original.username}</p>}
          </div>
        ),
      }),
      sourceColumn.accessor("category", {
        header: "Category",
        cell: (info) => info.getValue() ?? "-",
      }),
      sourceColumn.accessor("subscribers_count", {
        header: "Subscribers",
        cell: (info) => (info.getValue()?.toLocaleString() ?? "-"),
      }),
      sourceColumn.accessor("total_score", {
        header: "Score",
        cell: (info) => {
          const score = info.getValue();
          if (score === null) return <span className="text-muted">—</span>;
          const color = score >= 75 ? "text-green-600" : score >= 50 ? "text-yellow-600" : "text-red-600";
          return <span className={`font-semibold ${color}`}>{score}</span>;
        },
      }),
      sourceColumn.accessor("status", {
        header: "Status",
        cell: (info) => <StatusBadge status={info.getValue()} />,
      }),
      sourceColumn.accessor("source_type", {
        header: "Type",
        cell: (info) => info.getValue(),
      }),
      sourceColumn.display({
        id: "actions",
        header: "Actions",
        cell: (info) => {
          const source = info.row.original;
          return (
            <div className="flex min-w-[320px] flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleAnalyze(source.id)}
                disabled={analyzingId === source.id}
              >
                <Activity className="mr-1 h-4 w-4" />
                {analyzingId === source.id ? "Analyzing..." : "Analyze"}
              </Button>
              {source.tgstat_url && (
                <Button variant="ghost" size="sm" onClick={() => window.open(source.tgstat_url!, "_blank")}>
                  <Eye className="mr-1 h-4 w-4" /> TGStat
                </Button>
              )}
              {source.status !== "selected" && (
                <Button variant="secondary" size="sm" onClick={() => handleSelect(source.id)}>
                  <CheckCircle className="mr-1 h-4 w-4" /> Select
                </Button>
              )}
              {source.status !== "rejected" && source.status !== "selected" && (
                <Button variant="outline" size="sm" onClick={() => handleReject(source.id)}>
                  <ThumbsDown className="mr-1 h-4 w-4" /> Reject
                </Button>
              )}
              <Button variant="destructive" size="sm" onClick={() => handleDeleteSource(source.id)}>
                <Trash2 className="mr-1 h-4 w-4" /> Delete
              </Button>
            </div>
          );
        },
      }),
    ],
    [analyzingId, sourcesData],
  );

  const chats = data?.items ?? [];
  const sources: SourceCandidateItem[] = sourcesData?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">Parser</h1>
          <p className="mt-1 text-sm text-muted">
            {stats ? `${stats.total_chats} chats / ${stats.total_users} users` : "Build parsed audiences"}
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <RefreshCw className="mr-1 h-4 w-4" /> Refresh
        </Button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-black/10">
        {(["discovery", "parse", "lists"] as const).map((tab) => (
          <button
            key={tab}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab
                ? "border-accent text-accent"
                : "border-transparent text-muted hover:text-ink"
            }`}
            onClick={() => setActiveTab(tab)}
          >
            {tab === "discovery" ? "TGStat Discovery" : tab === "parse" ? "Telegram Parse" : "Parsed Lists"}
          </button>
        ))}
      </div>

      {/* ==================== Discovery Tab ==================== */}
      {activeTab === "discovery" && (
        <>
          <div className="rounded-xl border border-black/5 bg-white p-5 shadow-sm space-y-4">
            <div className="grid gap-3 sm:grid-cols-[1fr_200px_100px]">
              <input
                className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent"
                placeholder="Keywords: Сад, Стоматология, Косметология..."
                value={discoveryQuery}
                onChange={(e) => setDiscoveryQuery(e.target.value)}
              />
              <input
                className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent"
                placeholder="Category (optional)"
                value={discoveryCategory}
                onChange={(e) => setDiscoveryCategory(e.target.value)}
              />
              <input
                className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent"
                placeholder="Limit"
                type="number"
                value={discoveryLimit}
                onChange={(e) => setDiscoveryLimit(e.target.value)}
              />
            </div>
            <div className="flex justify-end">
              <Button
                onClick={handleDiscoverySearch}
                disabled={!discoveryQuery.trim() || searchSources.isPending}
              >
                {searchSources.isPending ? "Searching..." : "Search TGStat"}
              </Button>
            </div>
          </div>

          <DataTable
            columns={sourceColumns}
            data={sources}
            loading={sourcesLoading || searchSources.isPending}
            pageSize={25}
          />

          {/* Expanded source analysis details */}
          {expandedSource && analyzeResults[expandedSource] && (
            <div className="rounded-xl border border-black/5 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-ink">Analysis Details</h3>
                <Button variant="ghost" size="sm" onClick={() => setExpandedSource(null)}>Close</Button>
              </div>
              <div className="grid gap-4 sm:grid-cols-4">
                {[
                  ["Topic", analyzeResults[expandedSource]?.score?.topic_score, "Relevance to keywords"],
                  ["Activity", analyzeResults[expandedSource]?.score?.activity_score, "Posting frequency"],
                  ["Audience", analyzeResults[expandedSource]?.score?.audience_quality_score, "Engagement quality"],
                  ["Liveness", analyzeResults[expandedSource]?.score?.chat_liveness_score, "Discussion activity"],
                ].map(([label, score, desc]) => (
                  <div key={label as string} className="rounded-lg bg-stone-50 p-3 text-center">
                    <p className="text-2xl font-bold text-ink">{(score as number) ?? "—"}</p>
                    <p className="text-xs font-medium text-muted mt-1">{label as string}</p>
                    <p className="text-xs text-muted mt-0.5">{desc as string}</p>
                  </div>
                ))}
              </div>
              {analyzeResults[expandedSource]?.score?.reasons && (
                <div className="mt-4">
                  <p className="text-xs font-medium text-muted mb-2">Reasons:</p>
                  <ul className="text-xs text-ink space-y-1">
                    {(analyzeResults[expandedSource].score.reasons as string[]).map((r: string, i: number) => (
                      <li key={i} className="flex items-start gap-2">
                        <span className="text-accent mt-0.5">•</span>
                        {r}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* ==================== Parse Tab ==================== */}
      {activeTab === "parse" && (
        <div className="rounded-xl border border-black/5 bg-white p-5 shadow-sm space-y-4">
          <div className="grid gap-3 sm:grid-cols-[220px_1fr_140px]">
            <select className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent bg-white" value={sourceType} onChange={(e) => setSourceType(e.target.value as "telegram" | "manual")}>
              <option value="manual">Manual/mock list</option>
              <option value="telegram">Telegram chat/channel</option>
            </select>
            {sourceType === "manual" ? (
              <div className="grid gap-3 sm:grid-cols-3">
                <input className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent" placeholder="Title" value={mockTitle} onChange={(e) => setMockTitle(e.target.value)} />
                <input className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent" placeholder="Count" type="number" min={1} max={1000} value={mockCount} onChange={(e) => setMockCount(e.target.value)} />
                <input className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent" placeholder="Username prefix" value={mockPrefix} onChange={(e) => setMockPrefix(e.target.value)} />
              </div>
            ) : (
              <input className="rounded-lg border border-black/10 px-3 py-2 text-sm outline-none focus:border-accent" placeholder="Username, link, chat_id, or niche" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
            )}
            <Button onClick={handleParse} disabled={(sourceType === "manual" ? !mockTitle : !searchQuery.trim()) || parseSearch.isPending || createMock.isPending}>
              {parseSearch.isPending || createMock.isPending ? "Parsing..." : "Parse"}
            </Button>
          </div>
          {sourceType === "telegram" && (
            <p className="text-xs text-muted">Real Telegram parsing requires an authorized active account.</p>
          )}
        </div>
      )}

      {/* ==================== Lists Tab ==================== */}
      {activeTab === "lists" && (
        <>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <input className="w-full rounded-lg border border-black/10 bg-white py-2 pl-10 pr-4 text-sm outline-none focus:border-accent" placeholder="Filter parsed lists..." value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>

          <DataTable columns={chatColumns} data={chats} loading={isLoading || parseSearch.isPending || createMock.isPending} pageSize={25} />

          {selectedChatId && (
            <div className="rounded-xl border border-black/5 bg-white p-5 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-ink flex items-center gap-2">
                  <Users className="h-4 w-4" /> Parsed Users
                </h3>
                <Button variant="ghost" size="sm" onClick={() => setSelectedChatId(undefined)}>Close</Button>
              </div>
              <DataTable columns={userColumns} data={users?.items ?? []} loading={usersLoading} pageSize={25} />
            </div>
          )}
        </>
      )}
    </div>
  );
}