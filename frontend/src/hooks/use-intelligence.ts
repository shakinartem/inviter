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
