import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { ParsedChatListItem, ParsedChatResponse, ParsedUserResponse, ParserSearchPayload, ParserStats } from "@/types";

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

export function useCreateMockParsedUsers() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      title: string;
      count: number;
      username_prefix: string;
      include_bots?: boolean;
      include_scam?: boolean;
      include_fake?: boolean;
    }) => {
      const { data } = await apiClient.post<ParsedChatResponse>("/parser/mock-users", payload);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["parsed-chats"] });
      qc.invalidateQueries({ queryKey: ["parser-stats"] });
    },
  });
}

export function useParsedUsers(chatId: string | undefined) {
  return useQuery({
    queryKey: ["parsed-users", chatId],
    queryFn: async () => {
      const { data } = await apiClient.get<{ items: ParsedUserResponse[]; total: number }>(`/parser/chats/${chatId}/users`);
      return data;
    },
    enabled: !!chatId,
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
