import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type MetaExperimentRow = {
  experiment_id: string;
  campaign_id: string;
  campaign_title: string;
  treatment_units: number;
  treatment_positives: number;
  holdout_units: number;
  holdout_positives: number;
  lift_percentage_points: number;
  standard_error_percentage_points: number;
  weight_percent: number;
};

export type IncrementalYieldMeta = {
  stage: string;
  event_type: string;
  horizon_hours: number;
  experiments_considered: number;
  experiments_included: number;
  randomized_units: number;
  unique_people: number;
  repeated_people: number;
  pooled_lift_percentage_points: number;
  confidence_low_percentage_points: number;
  confidence_high_percentage_points: number;
  incremental_outcomes_per_1000: number;
  tau_squared: number;
  i_squared_percent: number;
  q_statistic: number;
  status: "insufficient" | "positive" | "negative" | "inconclusive" | "heterogeneous";
  warnings: string[];
  rows: MetaExperimentRow[];
};

export function useIncrementalYield(params: {
  stage: string;
  event_type: string;
  horizon_hours: number;
}) {
  return useQuery({
    queryKey: ["incremental-yield-meta", params],
    queryFn: async () => {
      const { data } = await apiClient.get<IncrementalYieldMeta>("/experiments/meta-lift", {
        params: { ...params, min_confidence: 0.5 },
      });
      return data;
    },
    retry: false,
  });
}
