import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type ExperimentPowerPlan = {
  segment_id: string;
  segment_name: string;
  platform: string;
  stage: string;
  event_type: string;
  horizon_hours: number;
  holdout_percentage: number;
  alpha: number;
  target_power: number;
  baseline_rate: number | null;
  baseline_source: "mature_holdout_history" | "explicit_assumption" | "missing";
  baseline_samples: number;
  baseline_positives: number;
  target_lift_percentage_points: number;
  required_total_units: number | null;
  required_treatment_units: number | null;
  required_holdout_units: number | null;
  available_segment_units: number;
  requested_action_budget: number;
  projected_total_units: number;
  projected_treatment_units: number;
  projected_holdout_units: number;
  projected_mde_percentage_points: number | null;
  adequately_powered: boolean;
  status: "baseline_required" | "underpowered" | "adequately_powered" | "impossible";
  warnings: string[];
};

export function useExperimentPowerPlan(
  segmentId: string | null,
  params: {
    stage: string;
    event_type: string;
    horizon_hours: number;
    holdout_percentage: number;
    action_budget: number;
    target_lift_percentage_points: number;
    baseline_rate_assumption?: number;
  },
) {
  return useQuery({
    queryKey: ["experiment-power-plan", segmentId, params],
    queryFn: async () => {
      const query = {
        segment_id: segmentId,
        ...params,
        alpha: 0.05,
        target_power: 0.8,
        min_confidence: 0.5,
      };
      const { data } = await apiClient.get<ExperimentPowerPlan>("/experiments/power-plan", {
        params: query,
      });
      return data;
    },
    enabled: !!segmentId,
    retry: false,
  });
}
