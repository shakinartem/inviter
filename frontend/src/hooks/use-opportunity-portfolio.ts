import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type PortfolioForecastRow = {
  rank: number;
  segment_id: string;
  segment_name: string;
  matched_count: number;
  evaluated_members: number;
  expected_outcomes: number;
  conservative_outcomes: number;
  upside_outcomes: number;
  expected_rate: number;
  conservative_rate: number;
  quality_status: "insufficient" | "limited" | "ready";
  frozen_history_ratio: number;
  contextual_coverage: number;
  score: number;
  warnings: string[];
};

export type OpportunityPortfolio = {
  stage: string;
  event_type: string;
  horizon_hours: number;
  action_budget: number;
  ranking_basis: string;
  recommendation_segment_id: string | null;
  recommendation_name: string | null;
  warnings: string[];
  rows: PortfolioForecastRow[];
};

export function useOpportunityPortfolio(params: {
  stage: string;
  event_type: string;
  horizon_hours: number;
  action_budget: number;
  platform?: string;
}) {
  return useQuery({
    queryKey: ["opportunity-portfolio", params],
    queryFn: async () => {
      const { data } = await apiClient.get<OpportunityPortfolio>("/segments/portfolio/forecast", {
        params: { ...params, limit_segments: 20, min_confidence: 0.5 },
      });
      return data;
    },
  });
}
