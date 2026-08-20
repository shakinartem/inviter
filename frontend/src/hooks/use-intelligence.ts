import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type AudienceMember = {
  id: string;
  platform: string;
  external_user_id: string;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  is_bot: boolean;
  is_verified: boolean;
  is_scam: boolean;
  is_fake: boolean;
  is_blacklisted: boolean;
  last_activity_at: string | null;
  activity_score: number | null;
  relevance_score: number | null;
  quality_score: number | null;
  intent_score: number | null;
  readiness_score: number | null;
};

export type AudienceList = {
  items: AudienceMember[];
  total: number;
  skip: number;
  limit: number;
};

export type CommunityEnrichPayload = {
  account_id?: string | null;
  member_limit?: number;
  message_limit?: number;
  lookback_days?: number;
  relevance_score?: number | null;
};

export type CommunityEnrichResult = {
  community_id: string;
  platform: string;
  members_sampled: number;
  messages_sampled: number;
  audience_profiles: number;
  active_1d: number;
  active_7d: number;
  messages_1d: number;
  messages_7d: number;
  quality_score: number;
  snapshot_id: string;
  captured_at: string;
};

export type IntentScanResult = {
  community_id: string;
  platform: string;
  messages_scanned: number;
  candidate_signals: number;
  signals_created: number;
  members_scored: number;
  strongest_signal: number;
  average_member_intent: number;
  signal_types: Record<string, number>;
  model_version: string;
  scanned_at: string;
};

export type IntentSignal = {
  id: string;
  audience_member_id: string;
  parsed_chat_id: string;
  platform: string;
  external_message_id: string | null;
  observed_at: string;
  signal_type: string;
  topic: string | null;
  score: number;
  confidence: number;
  model_version: string;
  features: Record<string, unknown> | null;
  created_at: string;
};

export function useAudience(params?: {
  platform?: string;
  min_activity_score?: number;
  min_readiness_score?: number;
  include_bots?: boolean;
  skip?: number;
  limit?: number;
}) {
  return useQuery({
    queryKey: ["audience", params],
    queryFn: async () => {
      const { data } = await apiClient.get<AudienceList>("/intelligence/audience", { params });
      return data;
    },
  });
}

export function useEnrichCommunity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      communityId,
      payload,
    }: {
      communityId: string;
      payload?: CommunityEnrichPayload;
    }) => {
      const { data } = await apiClient.post<CommunityEnrichResult>(
        `/intelligence/communities/${communityId}/enrich`,
        payload ?? {},
      );
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["audience"] });
      qc.invalidateQueries({ queryKey: ["parsed-chats"] });
      qc.invalidateQueries({ queryKey: ["parser-stats"] });
    },
  });
}

export function useIntentScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      communityId,
      lookbackDays = 30,
      messageLimit = 10_000,
      minimumScore = 12,
    }: {
      communityId: string;
      lookbackDays?: number;
      messageLimit?: number;
      minimumScore?: number;
    }) => {
      const { data } = await apiClient.post<IntentScanResult>(
        `/intelligence/intent/communities/${communityId}/scan`,
        {
          lookback_days: lookbackDays,
          message_limit: messageLimit,
          minimum_score: minimumScore,
        },
      );
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["audience"] });
      qc.invalidateQueries({ queryKey: ["intent-signals"] });
    },
  });
}

export function useIntentSignals(params?: {
  audience_member_id?: string;
  community_id?: string;
  min_score?: number;
  limit?: number;
}) {
  return useQuery({
    queryKey: ["intent-signals", params],
    queryFn: async () => {
      const { data } = await apiClient.get<IntentSignal[]>("/intelligence/intent/signals", { params });
      return data;
    },
    enabled: Boolean(params?.audience_member_id || params?.community_id),
  });
}
