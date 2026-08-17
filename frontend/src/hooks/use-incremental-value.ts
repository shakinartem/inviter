import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type ExperimentValueLiftRow = {
  experiment_id: string;
  campaign_id: string;
  campaign_title: string;
  treatment_units: number;
  holdout_units: number;
  treatment_mean_value: number;
  holdout_mean_value: number;
  incremental_value_per_unit: number;
  standard_error: number;
  weight_percent: number;
};

export type IncrementalBusinessValue = {
  event_type: string;
  value_unit: string;
  horizon_hours: number;
  aggregation: "sum" | "max";
  experiments_considered: number;
  experiments_included: number;
  randomized_units: number;
  pooled_incremental_value_per_unit: number;
  confidence_low_per_unit: number;
  confidence_high_per_unit: number;
  incremental_value_per_1000: number;
  tau_squared: number;
  i_squared_percent: number;
  status: "insufficient" | "positive" | "negative" | "inconclusive" | "heterogeneous";
  warnings: string[];
  rows: ExperimentValueLiftRow[];
};

export function useIncrementalBusinessValue(params: {
  event_type: string;
  value_unit: string;
  horizon_hours: number;
  aggregation: "sum" | "max";
}) {
  return useQuery({
    queryKey: ["incremental-business-value", params],
    queryFn: async () => {
      const { data } = await apiClient.get<IncrementalBusinessValue>(
        "/experiments/value-lift",
        { params: { ...params, min_confidence: 0.5 } },
      );
      return data;
    },
    enabled: !!params.event_type.trim() && !!params.value_unit.trim(),
    retry: false,
  });
}
