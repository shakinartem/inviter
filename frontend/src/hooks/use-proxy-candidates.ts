import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type { ProxyTestResult } from "@/types";
// ==================== Types ====================

export interface CandidateListItem {
  id: string;
  proxy_type: string;
  host: string;
  port: number;
  username: string | null;
  password: string | null;
  secret: string | null;
  source_type: string;
  source_name: string | null;
  status: string;
  score: number;
  latency_ms: number | null;
  last_checked_at: string | null;
  last_error: string | null;
  created_at: string;
}

export interface MtprotoImportRequest {
  text: string;
  source_name?: string | null;
}

export interface MtprotoImportResult {
  found_count: number;
  imported_count: number;
  skipped_duplicates: number;
  invalid_count: number;
  candidates: CandidateListItem[];
}

export interface TextImportRequest {
  text: string;
  source_name?: string | null;
}

export interface TextImportResult {
  found_count: number;
  imported_count: number;
  skipped_duplicates: number;
  invalid_count: number;
  candidates: CandidateListItem[];
}

export interface CandidateListResponse {
  items: CandidateListItem[];
  total: number;
  skip: number;
  limit: number;
}

export interface BulkCheckRequest {
  ids: string[];
}

// ==================== Hooks ====================

export function useProxyCandidates(params?: { proxy_type?: string; status?: string; skip?: number; limit?: number }) {
  return useQuery({
    queryKey: ["proxy-candidates", params],
    queryFn: async () => {
      const { data } = await apiClient.get<CandidateListResponse>("/proxy-candidates", { params });
      return data;
    },
  });
}

export function useImportMtproto() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: MtprotoImportRequest) => {
      const { data } = await apiClient.post<MtprotoImportResult>("/proxy-candidates/import-mtproto-text", payload);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["proxy-candidates"] });
    },
  });
}

export function useImportText() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: TextImportRequest) => {
      const { data } = await apiClient.post<TextImportResult>("/proxy-candidates/import-text", payload);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["proxy-candidates"] });
    },
  });
}

export function useCheckCandidate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post<ProxyTestResult>(`/proxy-candidates/${id}/check`);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["proxy-candidates"] });
    },
  });
}

export function useBulkCheckCandidates() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: BulkCheckRequest) => {
      const { data } = await apiClient.post<ProxyTestResult[]>("/proxy-candidates/bulk-check", payload);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["proxy-candidates"] });
    },
  });
}

export function useApproveCandidate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post(`/proxy-candidates/${id}/approve`);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["proxy-candidates"] });
      qc.invalidateQueries({ queryKey: ["proxies"] });
      qc.invalidateQueries({ queryKey: ["proxy-stats"] });
    },
  });
}

export function useRejectCandidate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post(`/proxy-candidates/${id}/reject`);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["proxy-candidates"] });
    },
  });
}

export function useDeleteCandidate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/proxy-candidates/${id}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["proxy-candidates"] });
    },
  });
}

// ==================== Platforms ====================

export interface PlatformInfo {
  platform: string;
  display_name: string;
  supports_proxy: boolean;
  supported_proxy_types: string[];
  supports_invites: boolean;
  supports_messages: boolean;
  supports_group_sources: boolean;
  supports_member_parsing: boolean;
  status: string;
  notes: string;
}

export function usePlatforms() {
  return useQuery({
    queryKey: ["platforms"],
    queryFn: async () => {
      const { data } = await apiClient.get<{ platforms: PlatformInfo[]; total: number }>("/platforms");
      return data;
    },
  });
}