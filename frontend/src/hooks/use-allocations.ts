import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type CapacityAllocationPlan = {
  id: string;
  name: string;
  platform: string;
  stage: string;
  event_type: string;
  horizon_hours: number;
  total_capacity: number;
  allocation_mode: "decision_grade" | "coverage_expansion";
  require_positive_conservative: boolean;
  status: string;
  evidence_version: string;
  offers_considered: number;
  unique_candidates: number;
  duplicate_offers_removed: number;
  allocated_count: number;
  unallocated_capacity: number;
  expected_incremental_outcomes: number;
  conservative_incremental_outcomes: number;
  upside_incremental_outcomes: number;
  replicated_context_coverage: number;
  global_prior_status: string;
  global_prior_lift: number;
  global_prior_i_squared: number;
  candidate_pool_capped: boolean;
  warnings: string[] | null;
  frozen_at: string;
  created_at: string;
  updated_at: string;
};

export type CapacityAllocationAssignment = {
  id: string;
  plan_id: string;
  segment_id: string;
  audience_member_id: string;
  allocation_rank: number;
  segment_rank: number;
  segment_name_snapshot: string;
  activity_score: number | null;
  intent_score: number | null;
  readiness_score: number | null;
  strongest_signal_type: string | null;
  evidence_source: string;
  context_key: string;
  expected_incremental_probability: number;
  conservative_incremental_probability: number;
  upside_incremental_probability: number;
};

export type CapacityAllocationAssignmentList = {
  items: CapacityAllocationAssignment[];
  total: number;
  skip: number;
  limit: number;
};

export function useAllocationPlans() {
  return useQuery({
    queryKey: ["allocation-plans"],
    queryFn: async () => {
      const { data } = await apiClient.get<CapacityAllocationPlan[]>("/allocations/plans");
      return data;
    },
    refetchInterval: 15_000,
  });
}

export function useCreateAllocationPlan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      name: string;
      platform: string;
      stage: "engagement" | "business";
      event_type: string;
      horizon_hours: number;
      total_capacity: number;
      allocation_mode: "decision_grade" | "coverage_expansion";
      require_positive_conservative: boolean;
    }) => {
      const { data } = await apiClient.post<CapacityAllocationPlan>("/allocations/plans", payload);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["allocation-plans"] }),
  });
}

export function useAllocationAssignments(planId: string | null, limit = 250) {
  return useQuery({
    queryKey: ["allocation-assignments", planId, limit],
    queryFn: async () => {
      const { data } = await apiClient.get<CapacityAllocationAssignmentList>(
        `/allocations/plans/${planId}/assignments`,
        { params: { limit } },
      );
      return data;
    },
    enabled: !!planId,
  });
}
