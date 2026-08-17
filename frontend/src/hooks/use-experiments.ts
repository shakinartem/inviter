import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type CampaignExperiment = {
  id: string;
  campaign_id: string;
  holdout_percentage: number;
  status: string;
  action_budget: number | null;
  candidate_pool_size: number;
  treatment_count: number;
  holdout_count: number;
  assigned_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ExperimentArmResult = {
  variant: "treatment" | "holdout";
  units: number;
  positives: number;
  rate: number;
  confidence_low: number;
  confidence_high: number;
};

export type ExperimentBalanceMetric = {
  metric: string;
  treatment_mean: number | null;
  holdout_mean: number | null;
  standardized_difference: number | null;
};

export type CampaignCausalLift = {
  experiment_id: string;
  campaign_id: string;
  campaign_title: string;
  holdout_percentage: number;
  stage: string;
  event_type: string;
  horizon_hours: number;
  mature: boolean;
  hours_until_mature: number;
  status: "insufficient" | "inconclusive" | "positive" | "negative";
  treatment: ExperimentArmResult;
  holdout: ExperimentArmResult;
  lift_percentage_points: number;
  confidence_low_percentage_points: number;
  confidence_high_percentage_points: number;
  relative_lift_percent: number | null;
  incremental_outcomes_per_1000: number;
  treatment_execution_rate: number;
  treatment_transport_success_rate: number;
  balance: ExperimentBalanceMetric[];
  warnings: string[];
};

export function useExperiments() {
  return useQuery({
    queryKey: ["experiments"],
    queryFn: async () => {
      const { data } = await apiClient.get<CampaignExperiment[]>("/experiments");
      return data;
    },
    refetchInterval: 15_000,
  });
}

export function useCampaignCausalLift(
  campaignId: string | null,
  params: { stage: string; event_type: string; horizon_hours: number },
) {
  return useQuery({
    queryKey: ["causal-lift", campaignId, params],
    queryFn: async () => {
      const { data } = await apiClient.get<CampaignCausalLift>(
        `/experiments/campaigns/${campaignId}/lift`,
        { params: { ...params, min_confidence: 0.5 } },
      );
      return data;
    },
    enabled: !!campaignId,
    retry: false,
  });
}