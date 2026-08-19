import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { CampaignPlanResult } from "@/hooks/use-campaigns";

export type CampaignPreflightCheck = {
  key: string;
  status: "pass" | "warn" | "block" | string;
  blocking: boolean;
  title: string;
  message: string;
  details: Record<string, unknown> | null;
};

export type CampaignPreflightAccount = {
  account_id: string;
  label: string;
  health_score: number;
  risk_score: number;
  emergency_daily_capacity: number;
  normal_daily_capacity: number;
  queued_jobs: number;
  reasons: string[];
};

export type CampaignPreflight = {
  campaign_id: string;
  campaign_title: string;
  decision: "go" | "go_with_guards" | "block" | string;
  action_budget_requested: number;
  action_budget_executable: number;
  deadline_days: number;
  required_daily_rate: number;
  platform: string | null;
  destination_title: string | null;
  destination_ready: boolean;
  frozen_cohort_size: number;
  eligible_candidate_pool: number;
  required_candidate_pool: number;
  holdout_percentage: number;
  estimated_treatment_candidates: number;
  eligible_accounts: number;
  quarantined_accounts: number;
  recommended_account_ids: string[];
  normal_daily_capacity: number;
  emergency_daily_capacity: number;
  reserved_failover_headroom: number;
  estimated_completion_days: number | null;
  n_minus_one_surviving_capacity: number;
  n_minus_one_covers_required_rate: boolean;
  model_health_status: string;
  active_calibrator_version: string | null;
  checks: CampaignPreflightCheck[];
  accounts: CampaignPreflightAccount[];
  warnings: string[];
};

export type CampaignPreflightPayload = {
  campaign_id: string;
  action_budget: number;
  deadline_days: number;
  min_activity_score?: number;
  min_readiness_score?: number;
  account_ids?: string[] | null;
};

function requestBody(payload: CampaignPreflightPayload) {
  const { campaign_id: _campaignId, ...body } = payload;
  return {
    min_activity_score: 0,
    min_readiness_score: 0,
    account_ids: null,
    ...body,
  };
}

export function useCampaignPreflight() {
  return useMutation({
    mutationFn: async (payload: CampaignPreflightPayload) => {
      const { data } = await apiClient.post<CampaignPreflight>(
        `/orchestration/campaigns/${payload.campaign_id}/preflight`,
        requestBody(payload),
      );
      return data;
    },
  });
}

export function useStartWithFreshPreflight() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: CampaignPreflightPayload) => {
      const { data } = await apiClient.post<{
        preflight: CampaignPreflight;
        plan: CampaignPlanResult;
      }>(
        `/orchestration/campaigns/${payload.campaign_id}/preflight/start`,
        requestBody(payload),
      );
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      qc.invalidateQueries({ queryKey: ["campaign"] });
      qc.invalidateQueries({ queryKey: ["campaign-action-stats"] });
      qc.invalidateQueries({ queryKey: ["experiments"] });
      qc.invalidateQueries({ queryKey: ["execution-events"] });
    },
  });
}
