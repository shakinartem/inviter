import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type SegmentCriteria = {
  min_activity_score?: number | null;
  min_relevance_score?: number | null;
  min_quality_score?: number | null;
  min_intent_score?: number | null;
  min_readiness_score?: number | null;
  last_activity_days?: number | null;
  community_ids?: string[];
  signal_types?: string[];
  signal_lookback_days?: number;
  min_communities?: number | null;
  include_bots?: boolean;
  max_members?: number;
  sort_by?: "readiness" | "intent" | "activity";
};

export type AudienceSegment = {
  id: string;
  owner_id: string;
  name: string;
  description: string | null;
  platform: string;
  criteria: SegmentCriteria;
  criteria_version: string;
  is_active: boolean;
  matched_count: number;
  last_refreshed_at: string | null;
  refresh_count: number;
  created_at: string;
  updated_at: string;
};

export type SegmentMember = {
  segment_member_id: string;
  audience_member_id: string;
  platform: string;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  activity_score: number | null;
  relevance_score: number | null;
  intent_score: number | null;
  readiness_score: number | null;
  strongest_signal_type: string | null;
  matched_at: string;
  match_reasons: Record<string, unknown> | null;
};

export type SegmentMemberList = {
  items: SegmentMember[];
  total: number;
  skip: number;
  limit: number;
};

export type SegmentCreatePayload = {
  name: string;
  description?: string | null;
  platform?: string;
  criteria: SegmentCriteria;
};

export type SegmentPreview = {
  platform: string;
  matched_count: number;
  max_members: number;
  average_activity_score: number | null;
  average_relevance_score: number | null;
  average_intent_score: number | null;
  average_readiness_score: number | null;
  strongest_signal_distribution: Record<string, number>;
  community_count: number;
  warnings: string[];
  sample: Array<{
    audience_member_id: string;
    username: string | null;
    first_name: string | null;
    last_name: string | null;
    activity_score: number | null;
    relevance_score: number | null;
    intent_score: number | null;
    readiness_score: number | null;
    strongest_signal_type: string | null;
  }>;
};

export function useSegments(params?: { active_only?: boolean; platform?: string }) {
  return useQuery({
    queryKey: ["segments", params],
    queryFn: async () => {
      const { data } = await apiClient.get<AudienceSegment[]>("/segments", { params });
      return data;
    },
  });
}

export function useSegmentMembers(segmentId: string | null, limit = 100) {
  return useQuery({
    queryKey: ["segment-members", segmentId, limit],
    queryFn: async () => {
      const { data } = await apiClient.get<SegmentMemberList>(`/segments/${segmentId}/members`, {
        params: { limit },
      });
      return data;
    },
    enabled: !!segmentId,
  });
}

export function usePreviewSegment() {
  return useMutation({
    mutationFn: async (payload: { platform: string; criteria: SegmentCriteria }) => {
      const { data } = await apiClient.post<SegmentPreview>("/segments/preview", payload);
      return data;
    },
  });
}

export function useCreateSegment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: SegmentCreatePayload) => {
      const { data } = await apiClient.post<AudienceSegment>("/segments", payload);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["segments"] }),
  });
}

export function useRefreshSegment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (segmentId: string) => {
      const { data } = await apiClient.post<{
        segment_id: string;
        matched_count: number;
        refresh_sequence: number;
        refreshed_at: string;
      }>(`/segments/${segmentId}/refresh`);
      return data;
    },
    onSuccess: (_data, segmentId) => {
      qc.invalidateQueries({ queryKey: ["segments"] });
      qc.invalidateQueries({ queryKey: ["segment-members", segmentId] });
    },
  });
}

export function useDeactivateSegment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (segmentId: string) => {
      await apiClient.delete(`/segments/${segmentId}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["segments"] }),
  });
}
