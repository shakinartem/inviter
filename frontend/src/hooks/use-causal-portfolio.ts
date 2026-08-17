import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type CausalPortfolioRow = {
  rank: number;
  segment_id: string;
  segment_name: string;
  matched_count: number;
  evaluated_members: number;
  expected_incremental_outcomes: number;
  conservative_incremental_outcomes: number;
  upside_incremental_outcomes: number;
  expected_incremental_rate: number;
  conservative_incremental_rate: number;
  replicated_context_coverage: number;
  exploratory_context_coverage: number;
  global_fallback_coverage: number;
  evidence_status: "insufficient" | "limited" | "ready";
  warnings: string[];
};

export type CausalOpportunityPortfolio = {
  stage: string;
  event_type: string;
  horizon_hours: number;
  action_budget: number;
  global_prior_status: string;
  global_prior_lift_percentage_points: number;
  global_prior_i_squared_percent: number;
  recommendation_segment_id: string | null;
  recommendation_name: string | null;
  ranking_basis: string;
  warnings: string[];
  rows: CausalPortfolioRow[];
};

export function useCausalPortfolio(params: {
  stage: string;
  event_type: string;
  horizon_hours: number;
  action_budget: number;
  platform?: string;
}) {
  return useQuery({
    queryKey: ["causal-opportunity-portfolio", params],
    queryFn: async () => {
      const { data } = await apiClient.get<CausalOpportunityPortfolio>(
        "/segments/causal-portfolio/forecast",
        { params: { ...params, min_confidence: 0.5 } },
      );
      return data;
    },
    retry: false,
  });
}
