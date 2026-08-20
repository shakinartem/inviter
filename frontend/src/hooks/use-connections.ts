import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/api-client";

export type MessengerConnection = {
  id: string;
  owner_id: string;
  platform: string;
  external_account_id: string | null;
  label: string;
  auth_type: string;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  status: string;
  status_message: string | null;
  is_active: boolean;
  capabilities: Record<string, boolean> | null;
  health_score: number;
  proxy_id: string | null;
  last_seen_at: string | null;
  last_used_at: string | null;
  last_checked_at: string | null;
  metadata: Record<string, unknown> | null;
  notes: string | null;
  has_credentials: boolean;
  connector_available: boolean;
  created_at: string;
  updated_at: string;
};

export type CreateConnectionPayload = {
  platform: string;
  label: string;
  auth_type: string;
  external_account_id?: string | null;
  credentials: Record<string, string>;
  proxy_id?: string | null;
  notes?: string | null;
};

export function useConnections(params?: { platform?: string; search?: string }) {
  return useQuery({
    queryKey: ["connections", params],
    queryFn: async () => {
      const { data } = await apiClient.get<MessengerConnection[]>("/connections", { params });
      return data;
    },
  });
}

export function useCreateConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: CreateConnectionPayload) => {
      const { data } = await apiClient.post<MessengerConnection>("/connections", payload);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["connections"] }),
  });
}

export function useCheckConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post(`/connections/${id}/check`);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["connections"] }),
  });
}

export function useDeleteConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/connections/${id}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["connections"] }),
  });
}
