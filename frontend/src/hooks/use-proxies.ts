import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { ProxyListItem, ProxyResponse, ProxyStats, ProxyCreatePayload } from "@/types";

export function useProxies(params?: { scheme?: string; search?: string; skip?: number; limit?: number }) {
  return useQuery({
    queryKey: ["proxies", params],
    queryFn: async () => {
      const { data } = await apiClient.get<{ items: ProxyListItem[]; total: number }>("/proxies", { params });
      return data;
    },
  });
}

export function useProxy(id: string | undefined) {
  return useQuery({
    queryKey: ["proxy", id],
    queryFn: async () => {
      const { data } = await apiClient.get<ProxyResponse>(`/proxies/${id}`);
      return data;
    },
    enabled: !!id,
  });
}

export function useProxyStats() {
  return useQuery({
    queryKey: ["proxy-stats"],
    queryFn: async () => {
      const { data } = await apiClient.get<ProxyStats>("/proxies/stats");
      return data;
    },
    refetchInterval: 30_000,
  });
}

export function useCreateProxy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: ProxyCreatePayload) => {
      const { data } = await apiClient.post<ProxyResponse>("/proxies", payload);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["proxies"] }),
  });
}

export function useDeleteProxy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/proxies/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["proxies"] }),
  });
}

export function useTestProxy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post(`/proxies/${id}/test`);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["proxies"] }),
  });
}

export function useImportProxies() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (text: string) => {
      const { data } = await apiClient.post("/proxies/import", { text, default_scheme: "socks5" });
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["proxies"] }),
  });
}