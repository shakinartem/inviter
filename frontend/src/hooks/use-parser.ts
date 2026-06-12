import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { ParsedChatListItem, ParsedChatResponse, ParserSearchPayload, ParserStats } from "@/types";

export function useParsedChats(params?: {
  source?: string;
  category?: string;
  niche?: string;
  search?: string;
  skip?: number;
  limit?: number;
}) {
  return useQuery({
    queryKey: ["parsed-chats", params],
    queryFn: async () => {
      const { data } = await apiClient.get<{ items: ParsedChatListItem[]; total: number }>("/parser/chats", { params });
      return data;
    },
  });
}

export function useParserStats() {
  return useQuery({
    queryKey: ["parser-stats"],
    queryFn: async () => {
      const { data } = await apiClient.get<ParserStats>("/parser/stats");
      return data;
    },
    refetchInterval: 30_000,
  });
}

export function useParseSearch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: ParserSearchPayload) => {
      const { data } = await apiClient.post<ParsedChatResponse[]>("/parser/parse", payload);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["parsed-chats"] }),
  });
}

export function useDeleteParsedChat() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/parser/chats/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["parsed-chats"] }),
  });
}