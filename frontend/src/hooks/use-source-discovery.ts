import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

// ==================== Types ====================

export interface SourceCandidateItem {
  id: string;
  source_type: string;
  title: string | null;
  username: string | null;
  url: string | null;
  tgstat_url: string | null;
  category: string | null;
  subscribers_count: number | null;
  status: string;
  total_score: number | null;
  discovered_by_query: string | null;
  discovered_at: string | null;
  created_at: string;
}

export interface SourceCandidateListResponse {
  items: SourceCandidateItem[];
  total: number;
  skip: number;
  limit: number;
}

export interface SourceScoreItem {
  id: string;
  source_candidate_id: string;
  topic_score: number;
  activity_score: number;
  audience_quality_score: number;
  chat_liveness_score: number;
  total_score: number;
  reasons: string[] | null;
  created_at: string;
}

export interface SearchSourcesRequest {
  query: string;
  limit?: number;
  category?: string;
}

export interface AnalysisResult {
  candidate: any;
  score: SourceScoreItem;
}

// ==================== Hooks ====================

export function useSourceCandidates(params?: { status?: string; skip?: number; limit?: number }) {
  return useQuery({
    queryKey: ["source-candidates", params],
    queryFn: async () => {
      const { data } = await apiClient.get<SourceCandidateListResponse>("/source-discovery/sources", { params });
      return data;
    },
  });
}

export function useSearchSources() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: SearchSourcesRequest) => {
      const { data } = await apiClient.post<SourceCandidateItem[]>("/source-discovery/tgstat/search", payload);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["source-candidates"] });
    },
  });
}

export function useAnalyzeSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (sourceId: string) => {
      const { data } = await apiClient.post<AnalysisResult>(`/source-discovery/sources/${sourceId}/analyze`);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["source-candidates"] });
    },
  });
}

export function useSelectSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (sourceId: string) => {
      const { data } = await apiClient.post(`/source-discovery/sources/${sourceId}/select`);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["source-candidates"] });
    },
  });
}

export function useRejectSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (sourceId: string) => {
      const { data } = await apiClient.post(`/source-discovery/sources/${sourceId}/reject`);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["source-candidates"] });
    },
  });
}

export function useDeleteSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (sourceId: string) => {
      const { data } = await apiClient.delete(`/source-discovery/sources/${sourceId}`);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["source-candidates"] });
    },
  });
}