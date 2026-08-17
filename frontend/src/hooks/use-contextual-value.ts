import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type ContextualValueLiftRow = {
  readiness_bucket: string;
  strongest_signal_type: string;
  experiments: number;
  treatment_units: number;
  holdout_units: number;
  treatment_mean_value: number;
  holdout_mean_value: number;
  raw_incremental_value_per_unit: number;
  shrunk_incremental_value_per_unit: number;
  confidence_low_per_unit: number;
  confidence_high_per_unit: number;
  data_weight_percent: number;
  incremental_value_per_1000: number;
  evidence_status: "exploratory" | "replicated";
  direction: "positive" | "negative" | "inconclusive";
};

export type ContextualIncrementalBusinessValue = {
  event_type: string;
  value_unit: string;
  horizon_hours: number;
  aggregation: "sum" | "max";
  global_prior_value_per_unit: number;
  global_prior_status: string;
  global_prior_i_squared_percent: number;
  strata_evaluated: number;
  strata_replicated: number;
  warnings: string[];
  rows: ContextualValueLiftRow[];
};

export function useContextualBusinessValue(params: {
  event_type: string;
  value_unit: string;
  horizon_hours: number;
  aggregation: "sum" | "max";
}) {
  return useQuery({
    queryKey: ["contextual-business-value", params],
    queryFn: async () => {
      const { data } = await apiClient.get<ContextualIncrementalBusinessValue>(
        "/experiments/contextual-value",
        { params: { ...params, min_confidence: 0.5 } },
      );
      return data;
    },
    enabled: !!params.event_type.trim() && !!params.value_unit.trim(),
    retry: false,
  });
}
