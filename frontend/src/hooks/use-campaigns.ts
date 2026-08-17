import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { InviteCampaignListItem, InviteCampaignResponse, InviteTaskResponse, InviteSettingsPayload } from "@/types";

export type CampaignActionStats = {
  campaign_id: string;
  campaign_status: string;
  total: number;
  by_status: Record<string, number>;
  success_rate: number;
};

export type CampaignPlanPayload = {
  limit?: number;
  min_activity_score?: number;
  min_readiness_score?: number;
  account_ids?: string[] | null;
};

export type CampaignPlanResult = {
  campaign_id: string;
  planned: number;
  candidates: number;
  accounts: number;
  first_scheduled_at: string | null;
  last_scheduled_at: string | null;
  status?: string | null;
  experiment_id?: string | null;
  experiment_status?: string | null;
  action_budget?: number | null;
  candidate_pool_size?: number | null;
  treatment_count?: number | null;
  holdout_count?: number | null;
};

export type CanonicalCampaignCreatePayload = {
  title: string;
  target_community_id: string;
  source_segment_id: string;
  holdout_percentage?: number;
  notes?: string | null;
  settings?: InviteSettingsPayload;
};

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
    queryKey: ["campaign-action-stats", id],
    queryFn: async () => {
      const { data } = await apiClient.get<CampaignActionStats>(`/orchestration/campaigns/${id}/stats`);
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
    mutationFn: async (payload: CanonicalCampaignCreatePayload) => {
      const { data } = await apiClient.post<InviteCampaignResponse>("/orchestration/campaigns", payload);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      qc.invalidateQueries({ queryKey: ["experiments"] });
    },
  });
}

export function useStartCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, payload }: { id: string; payload?: CampaignPlanPayload }) => {
      const { data } = await apiClient.post<CampaignPlanResult>(`/orchestration/campaigns/${id}/start`, payload ?? {});
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      qc.invalidateQueries({ queryKey: ["campaign"] });
      qc.invalidateQueries({ queryKey: ["campaign-action-stats"] });
      qc.invalidateQueries({ queryKey: ["experiments"] });
    },
  });
}

export function usePauseCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post(`/orchestration/campaigns/${id}/pause`);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      qc.invalidateQueries({ queryKey: ["campaign"] });
      qc.invalidateQueries({ queryKey: ["campaign-action-stats"] });
    },
  });
}

export function useStopCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post(`/orchestration/campaigns/${id}/stop`);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      qc.invalidateQueries({ queryKey: ["campaign"] });
      qc.invalidateQueries({ queryKey: ["campaign-action-stats"] });
    },
  });
}

export function useDeleteCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/campaigns/${id}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      qc.invalidateQueries({ queryKey: ["experiments"] });
    },
  });
}