import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type CapacityFrontierPoint = {
  requested_capacity: number;
  allocated_count: number;
  cumulative_expected: number;
  cumulative_conservative: number;
  cumulative_upside: number;
  marginal_count: number;
  marginal_expected: number;
  marginal_conservative: number;
  marginal_upside: number;
  marginal_conservative_per_action: number | null;
  cumulative_cost: number | null;
  cumulative_conservative_net: number | null;
  marginal_cost: number | null;
  marginal_conservative_net: number | null;
};

export type CapacityFrontier = {
  objective: "incremental_outcomes" | "incremental_business_value";
  value_unit: string | null;
  event_type: string;
  horizon_hours: number;
  allocation_mode: string;
  global_prior_status: string;
  global_prior_i_squared: number;
  unique_positive_candidates: number;
  overlap_removed: number;
  candidate_pool_capped: boolean;
  cost_per_action: number | null;
  recommended_capacity: number | null;
  recommendation_reason: string;
  warnings: string[];
  points: CapacityFrontierPoint[];
};

export function useCapacityFrontier() {
  return useMutation({
    mutationFn: async (payload: {
      platform: string;
      stage: "engagement" | "business";
      event_type: string;
      horizon_hours: number;
      objective: "incremental_outcomes" | "incremental_business_value";
      value_unit?: string | null;
      value_aggregation?: "sum" | "max" | null;
      allocation_mode: "decision_grade" | "coverage_expansion";
      capacities: number[];
      cost_per_action?: number | null;
    }) => {
      const { data } = await apiClient.post<CapacityFrontier>("/allocations/capacity-frontier", payload);
      return data;
    },
  });
}
