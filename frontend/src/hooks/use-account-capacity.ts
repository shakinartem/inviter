import { useMutation, useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type AccountCapacityAssessment = {
  account_id: string;
  label: string;
  platform: string;
  status: string;
  health_score: number;
  risk_score: number;
  capacity_multiplier: number;
  suggested_daily_capacity: number;
  campaign_daily_limit: number;
  attempts_24h: number;
  successes_24h: number;
  account_errors_24h: number;
  target_errors_24h: number;
  floodwaits_24h: number;
  peer_floods_7d: number;
  connector_errors_24h: number;
  queued_jobs: number;
  eligible: boolean;
  next_safe_at: string | null;
  reasons: string[];
  calculated_at: string;
};

export type AccountCapacityPool = {
  platform: string;
  campaign_daily_limit: number;
  total_accounts: number;
  eligible_accounts: number;
  quarantined_accounts: number;
  suggested_total_daily_capacity: number;
  queued_jobs: number;
  average_health_score: number;
  assessments: AccountCapacityAssessment[];
};

export function useAccountCapacityRefresh() {
  return useMutation({
    mutationFn: async (payload: { platform?: string; campaign_daily_limit: number; persist_snapshots?: boolean }) => {
      const { data } = await apiClient.post<AccountCapacityPool>("/account-capacity/refresh", {
        platform: payload.platform ?? "telegram",
        campaign_daily_limit: payload.campaign_daily_limit,
        persist_snapshots: payload.persist_snapshots ?? true,
      });
      return data;
    },
  });
}

export function useAccountCapacityHistory(accountId: string | null) {
  return useQuery({
    queryKey: ["account-capacity-history", accountId],
    enabled: Boolean(accountId),
    queryFn: async () => {
      const { data } = await apiClient.get<{ account_id: string; items: Array<Record<string, unknown>> }>(
        `/account-capacity/${accountId}/history?limit=30`,
      );
      return data;
    },
  });
}
