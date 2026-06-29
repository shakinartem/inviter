import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";
import type {
  AccountListItem,
  AccountResponse,
  AccountStats,
  AccountCreatePayload,
  AccountStatus,
} from "@/types";

export function useAccounts(params?: { status?: string; search?: string; skip?: number; limit?: number }) {
  return useQuery({
    queryKey: ["accounts", params],
    queryFn: async () => {
      const { data } = await apiClient.get<AccountListItem[]>("/accounts", { params });
      return data;
    },
  });
}

export function useAccount(id: string | undefined) {
  return useQuery({
    queryKey: ["account", id],
    queryFn: async () => {
      const { data } = await apiClient.get<AccountResponse>(`/accounts/${id}`);
      return data;
    },
    enabled: !!id,
  });
}

export function useAccountStats() {
  return useQuery({
    queryKey: ["account-stats"],
    queryFn: async () => {
      const { data } = await apiClient.get<AccountStats>("/accounts/stats");
      return data;
    },
    refetchInterval: 30_000,
  });
}

export function useCreateAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: AccountCreatePayload) => {
      const { data } = await apiClient.post<AccountResponse>("/accounts", payload);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
  });
}

export function useUpdateAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      payload,
    }: {
      id: string;
      payload: Partial<AccountCreatePayload> & { is_active?: boolean };
    }) => {
      const { data } = await apiClient.patch<AccountResponse>(`/accounts/${id}`, payload);
      return data;
    },
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["accounts"] });
      qc.invalidateQueries({ queryKey: ["account", vars.id] });
      qc.invalidateQueries({ queryKey: ["account-stats"] });
    },
  });
}

export function useUpdateAccountStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, status, status_message }: { id: string; status: AccountStatus; status_message?: string }) => {
      const { data } = await apiClient.patch<AccountResponse>(`/accounts/${id}/status`, { status, status_message });
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["accounts"] });
      qc.invalidateQueries({ queryKey: ["account-stats"] });
    },
  });
}

export function useDeleteAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/accounts/${id}`);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["accounts"] });
      qc.invalidateQueries({ queryKey: ["account-stats"] });
    },
  });
}

export function useUploadSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ accountId, file }: { accountId: string; file: File }) => {
      const formData = new FormData();
      formData.append("file", file);
      const { data } = await apiClient.post(`/accounts/${accountId}/upload-session`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
  });
}

export function useCheckAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post(`/accounts/${id}/check`);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
  });
}
