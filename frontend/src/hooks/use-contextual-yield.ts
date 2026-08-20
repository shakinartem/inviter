import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type ContextualLiftRow = {
  readiness_bucket: string;
  strongest_signal_type: string;
  experiments: number;
  treatment_units: number;
  treatment_positives: number;
  holdout_units: number;
  holdout_positives: number;
  raw_lift_percentage_points: number;
  shrunk_lift_percentage_points: number;
  confidence_low_percentage_points: number;
  confidence_high_percentage_points: number;
  data_weight_percent: number;
  incremental_outcomes_per_1000: number;
  evidence_status: "exploratory" | "replicated";
  direction: "positive" | "negative" | "inconclusive";
};

export type ContextualIncrementalYield = {
  stage: string;
  event_type: string;
  horizon_hours: number;
  global_prior_lift_percentage_points: number;
  global_prior_status: string;
  global_prior_i_squared_percent: number;
  strata_evaluated: number;
  strata_replicated: number;
  warnings: string[];
  rows: ContextualLiftRow[];
};

export function useContextualYield(params: {
  stage: string;
  event_type: string;
  horizon_hours: number;
}) {
  return useQuery({
    queryKey: ["contextual-incremental-yield", params],
    queryFn: async () => {
      const { data } = await apiClient.get<ContextualIncrementalYield>(
        "/experiments/contextual-lift",
        { params: { ...params, min_confidence: 0.5 } },
      );
      return data;
    },
    retry: false,
  });
}
