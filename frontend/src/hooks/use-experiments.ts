import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type CampaignExperiment = {
  id: string;
  campaign_id: string;
  holdout_percentage: number;
  status: string;
  action_budget: number | null;
  candidate_pool_size: number;
  treatment_count: number;
  holdout_count: number;
  assigned_at: string | null;
  created_at: string;
  updated_at: string;
};

export function useExperiments() {
  return useQuery({
    queryKey: ["experiments"],
    queryFn: async () => {
      const { data } = await apiClient.get<CampaignExperiment[]>("/experiments");
      return data;
    },
    refetchInterval: 15_000,
  });
}
