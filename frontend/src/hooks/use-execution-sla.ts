import { useMutation, useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type AccountHazard = {
  account_id: string;
  label: string;
  health_score: number;
  emergency_daily_capacity: number;
  exposure_days: number;
  hard_failure_days: number;
  posterior_daily_hazard: number;
  conservative_daily_hazard: number;
  evidence_quality: string;
};

export type SLAScenario = {
  reserve_percentage: number;
  normal_daily_capacity: number;
  emergency_daily_capacity: number;
  reserved_headroom: number;
  required_daily_rate: number;
  supports_required_daily_rate: boolean;
  nominal_completion_days: number | null;
  modelled_schedule_continuity_probability: number;
  conservative_schedule_continuity_probability: number;
  modelled_workload_completion_probability: number;
  conservative_workload_completion_probability: number;
  expected_actions_by_deadline: number;
  conservative_expected_actions_by_deadline: number;
  meets_target_sla: boolean;
  throughput_penalty_vs_zero_reserve: number;
};

export type ExecutionSLAForecast = {
  forecast_id: string | null;
  model_version: string;
  campaign_id: string;
  campaign_title: string;
  remaining_actions: number;
  deadline_days: number;
  required_daily_rate: number;
  deadline_at: string;
  target_sla: number;
  lookback_days: number;
  simulations: number;
  evidence_quality: string;
  total_exposure_days: number;
  total_hard_failure_days: number;
  current_reserve_percentage: number;
  current_scenario: SLAScenario;
  recommended_scenario: SLAScenario | null;
  status: string;
  warnings: string[];
  accounts: AccountHazard[];
  scenarios: SLAScenario[];
};

export type ExecutionSLAHistoryItem = {
  id: string;
  campaign_id: string;
  model_version: string;
  remaining_actions: number;
  deadline_at: string;
  target_sla: number;
  evidence_quality: string;
  current_reserve_percentage: number;
  recommended_reserve_percentage: number | null;
  recommended_conservative_continuity_probability: number | null;
  normal_daily_capacity: number;
  emergency_daily_capacity: number;
  actual_completed_at: string | null;
  actual_met_sla: boolean | null;
  created_at: string;
};

export function useExecutionSLAForecast() {
  return useMutation({
    mutationFn: async (payload: {
      campaign_id: string;
      remaining_actions: number;
      deadline_days: number;
      target_sla: number;
      lookback_days?: number;
      simulations?: number;
      persist_snapshot?: boolean;
    }) => {
      const { data } = await apiClient.post<ExecutionSLAForecast>("/execution-sla/forecast", {
        lookback_days: 60,
        simulations: 3000,
        persist_snapshot: true,
        ...payload,
      });
      return data;
    },
  });
}

export function useExecutionSLAHistory(campaignId: string | null, limit = 30) {
  return useQuery({
    queryKey: ["execution-sla-history", campaignId, limit],
    enabled: Boolean(campaignId),
    queryFn: async () => {
      const { data } = await apiClient.get<ExecutionSLAHistoryItem[]>("/execution-sla/history", {
        params: { campaign_id: campaignId, limit },
      });
      return data;
    },
  });
}
