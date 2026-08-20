import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type AdaptiveMove = {
  job_id: string;
  campaign_id: string;
  from_account_id: string;
  from_account_label: string;
  to_account_id: string;
  to_account_label: string;
  previous_scheduled_at: string;
  new_scheduled_at: string;
  reason: string;
  target_health_score: number;
  target_daily_capacity: number;
};

export type AdaptivePlan = {
  source_account_id: string;
  source_account_label: string;
  reason: string;
  movable_jobs: number;
  moved_jobs: number;
  untouched_started_or_retry_jobs: number;
  no_safe_target_jobs: number;
  target_accounts: number;
  latest_reassigned_at: string | null;
  moves: AdaptiveMove[];
};

export type AdaptiveEvent = {
  id: string;
  campaign_id: string;
  action_job_id: string;
  from_account_id: string;
  to_account_id: string;
  reason: string;
  policy_version: string;
  previous_scheduled_at: string;
  new_scheduled_at: string;
  details: Record<string, unknown> | null;
  created_at: string;
};

export type ResilienceAccount = {
  account_id: string;
  label: string;
  health_score: number;
  emergency_daily_capacity: number;
  normal_daily_capacity: number;
  reserved_headroom: number;
};

export type CampaignResilience = {
  campaign_id: string;
  campaign_title: string;
  reserve_capacity_percentage: number;
  campaign_accounts: number;
  normal_daily_capacity: number;
  emergency_daily_capacity: number;
  reserved_failover_headroom: number;
  worst_single_account_loss_capacity: number;
  n_minus_one_surviving_capacity: number;
  n_minus_one_margin: number;
  n_minus_one_covered: boolean;
  resilience_ratio: number;
  recommended_min_reserve_percentage: number | null;
  status: string;
  warnings: string[];
  accounts: ResilienceAccount[];
};

type RebalancePayload = {
  source_account_id: string;
  campaign_id?: string | null;
  max_jobs?: number;
  reason?: string;
};

export function useAdaptivePreview() {
  return useMutation({
    mutationFn: async (payload: RebalancePayload) => {
      const { data } = await apiClient.post<AdaptivePlan>("/adaptive-execution/preview", {
        source_account_id: payload.source_account_id,
        campaign_id: payload.campaign_id ?? null,
        max_jobs: payload.max_jobs ?? 500,
        reason: payload.reason ?? "manual_preview",
      });
      return data;
    },
  });
}

export function useAdaptiveRebalance() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: RebalancePayload) => {
      const { data } = await apiClient.post<AdaptivePlan>("/adaptive-execution/rebalance", {
        source_account_id: payload.source_account_id,
        campaign_id: payload.campaign_id ?? null,
        max_jobs: payload.max_jobs ?? 500,
        reason: payload.reason ?? "manual_rebalance",
      });
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["adaptive-execution-events"] });
      queryClient.invalidateQueries({ queryKey: ["campaign-resilience"] });
    },
  });
}

export function useAdaptiveEvents(limit = 100) {
  return useQuery({
    queryKey: ["adaptive-execution-events", limit],
    queryFn: async () => {
      const { data } = await apiClient.get<AdaptiveEvent[]>(`/adaptive-execution/events?limit=${limit}`);
      return data;
    },
  });
}

export function useCampaignResilience(campaignId: string | null) {
  return useQuery({
    queryKey: ["campaign-resilience", campaignId],
    enabled: Boolean(campaignId),
    queryFn: async () => {
      const { data } = await apiClient.get<CampaignResilience>(
        `/adaptive-execution/resilience/${campaignId}`,
      );
      return data;
    },
  });
}
