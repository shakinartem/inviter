import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { createColumnHelper } from "@tanstack/react-table";
import { Eye, PlaySquare, RefreshCw, Search, Trash2, Users } from "lucide-react";

import {
  useCreateMockParsedUsers,
  useDeleteParsedChat,
  useParsedChats,
  useParsedUsers,
  useParserStats,
  useParseSearch,
} from "@/hooks/use-parser";
import { DataTable } from "@/components/ui/data-table";
import { StatusBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import type { ParsedChatListItem, ParsedUserResponse } from "@/types";

const chatColumn = createColumnHelper<ParsedChatListItem>();
const userColumn = createColumnHelper<ParsedUserResponse>();

function errMessage(error: unknown) {
  const anyErr = error as any;
  return anyErr?.response?.data?.detail ?? anyErr?.message ?? "Request failed";
}

export default function ParserPage() {
  const navigate = useNavigate();
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
        cell: (info) => <StatusBadge status={info.getValue() ? "active" : "inactive"} />,
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

  const chats = data?.items ?? [];

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
    </div>
  );
}
