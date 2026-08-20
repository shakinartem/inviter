import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type SLACalibratorBin = {
  lower_bound: number;
  upper_bound: number;
  samples: number;
  mean_raw_prediction: number;
  observed_rate: number | null;
  calibrated_probability: number;
};

export type SLACalibrator = {
  id: string;
  base_model_version: string;
  calibrator_version: string;
  status: string;
  sample_count: number;
  train_count: number;
  test_count: number;
  training_cutoff_at: string;
  raw_brier_test: number;
  calibrated_brier_test: number;
  raw_ece_test: number;
  calibrated_ece_test: number;
  raw_bias_test: number;
  calibrated_bias_test: number;
  activation_eligible: boolean;
  mapping: SLACalibratorBin[];
  trained_at: string;
  activated_at: string | null;
  retired_at: string | null;
};

export type SLACalibratorTrainResult = {
  status: string;
  eligible_samples: number;
  minimum_required: number;
  calibrator: SLACalibrator | null;
  warnings: string[];
};

export type SLALiveMonitorBucket = {
  lower_bound: number;
  upper_bound: number;
  samples: number;
  calibrated_mean_prediction: number | null;
  observed_completion_rate: number | null;
};

export type SLALiveMonitor = {
  base_model_version: string;
  active_calibrator_id: string | null;
  active_calibrator_version: string | null;
  activated_at: string | null;
  post_activation_labels: number;
  minimum_revalidation_samples: number;
  raw_brier: number | null;
  calibrated_brier: number | null;
  raw_ece: number | null;
  calibrated_ece: number | null;
  raw_bias: number | null;
  calibrated_bias: number | null;
  holdout_calibrated_brier: number | null;
  holdout_calibrated_ece: number | null;
  status: string;
  retirement_recommended: boolean;
  warnings: string[];
  buckets: SLALiveMonitorBucket[];
};

export function useSLACalibrators() {
  return useQuery({
    queryKey: ["execution-sla-calibrators"],
    queryFn: async () => {
      const { data } = await apiClient.get<SLACalibrator[]>("/execution-sla/calibrators");
      return data;
    },
  });
}

export function useSLALiveHealth() {
  return useQuery({
    queryKey: ["execution-sla-live-health"],
    queryFn: async () => {
      const { data } = await apiClient.get<SLALiveMonitor>("/execution-sla/calibrators/live-health");
      return data;
    },
    refetchInterval: 60_000,
  });
}

export function useTrainSLACalibrator() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.post<SLACalibratorTrainResult>("/execution-sla/calibrators/train", {
        base_model_version: "execution-sla-v1",
        min_samples: 100,
        test_fraction: 0.2,
        prior_strength: 8,
      });
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["execution-sla-calibrators"] }),
  });
}

export function useActivateSLACalibrator() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post<SLACalibrator>(`/execution-sla/calibrators/${id}/activate`);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["execution-sla-calibrators"] });
      qc.invalidateQueries({ queryKey: ["execution-sla-live-health"] });
    },
  });
}

export function useRetireSLACalibrator() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const { data } = await apiClient.post<SLACalibrator>(`/execution-sla/calibrators/${id}/retire`);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["execution-sla-calibrators"] });
      qc.invalidateQueries({ queryKey: ["execution-sla-live-health"] });
    },
  });
}
