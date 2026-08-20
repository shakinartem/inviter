import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type OutcomeSource = {
  id: string;
  name: string;
  slug: string;
  allowed_stages: string[];
  allowed_event_types: string[];
  is_active: boolean;
  delivery_count: number;
  accepted_count: number;
  rejected_count: number;
  last_received_at: string | null;
  last_accepted_at: string | null;
  last_failure_at: string | null;
  last_error: string | null;
  secret_rotated_at: string | null;
  created_at: string;
  updated_at: string;
};

export type OutcomeSourceSecret = {
  source: OutcomeSource;
  signing_secret: string;
  webhook_path: string;
};

export function useOutcomeSources() {
  return useQuery({
    queryKey: ["outcome-sources"],
    queryFn: async () => {
      const { data } = await apiClient.get<OutcomeSource[]>("/learning/webhook-sources");
      return data;
    },
  });
}

export function useCreateOutcomeSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { name: string; allowed_event_types: string[] }) => {
      const { data } = await apiClient.post<OutcomeSourceSecret>("/learning/webhook-sources", {
        ...payload,
        allowed_stages: ["business"],
      });
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["outcome-sources"] }),
  });
}

export function useUpdateOutcomeSource() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, payload }: { id: string; payload: Partial<Pick<OutcomeSource, "is_active" | "name" | "allowed_event_types">> }) => {
      const { data } = await apiClient.patch<OutcomeSource>(`/learning/webhook-sources/${id}`, payload);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["outcome-sources"] }),
  });
}

export function useRotateOutcomeSourceSecret() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post<OutcomeSourceSecret>(`/learning/webhook-sources/${id}/rotate-secret`);
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["outcome-sources"] }),
  });
}
