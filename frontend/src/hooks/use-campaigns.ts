import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { InviteCampaignListItem, InviteCampaignResponse, CampaignCreatePayload, CampaignStats, InviteTaskResponse } from "@/types";

export function useCampaigns(params?: { status?: string; skip?: number; limit?: number }) {
  return useQuery({
    queryKey: ["campaigns", params],
    queryFn: async () => {
      const { data } = await apiClient.get<InviteCampaignListItem[]>("/campaigns", { params });
      return data;
    },
  });
}

export function useCampaign(id: string | undefined) {
  return useQuery({
    queryKey: ["campaign", id],
    queryFn: async () => {
      const { data } = await apiClient.get<InviteCampaignResponse>(`/campaigns/${id}`);
      return data;
    },
    enabled: !!id,
  });
}

export function useCampaignStats(id: string | undefined) {
  return useQuery({
    queryKey: ["campaign-stats", id],
    queryFn: async () => {
      const { data } = await apiClient.get<CampaignStats>(`/campaigns/${id}/stats`);
      return data;
    },
    enabled: !!id,
    refetchInterval: 10_000,
  });
}

export function useCampaignTasks(id: string | undefined) {
  return useQuery({
    queryKey: ["campaign-tasks", id],
    queryFn: async () => {
      const { data } = await apiClient.get<InviteTaskResponse[]>(`/campaigns/${id}/tasks`);
      return data;
    },
    enabled: !!id,
    refetchInterval: 10_000,
  });
}

export function useCreateCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: CampaignCreatePayload) => {
      const { data } = await apiClient.post<InviteCampaignResponse>("/campaigns", payload);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["campaigns"] }),
  });
}

export function useStartCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post(`/campaigns/${id}/start`);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      qc.invalidateQueries({ queryKey: ["campaign"] });
    },
  });
}

export function usePauseCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post(`/campaigns/${id}/pause`);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      qc.invalidateQueries({ queryKey: ["campaign"] });
    },
  });
}

export function useStopCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post(`/campaigns/${id}/stop`);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      qc.invalidateQueries({ queryKey: ["campaign"] });
    },
  });
}

export function useDeleteCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/campaigns/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["campaigns"] }),
  });
}