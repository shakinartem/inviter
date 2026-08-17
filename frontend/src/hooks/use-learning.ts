import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type LearningOverview = {
  snapshots: number;
  events_by_stage: Record<string, number>;
};

export type CalibrationRateRow = {
  label: string;
  samples: number;
  positives: number;
  rate: number;
  confidence_low: number;
  confidence_high: number;
};

export type CalibrationResult = {
  stage: string;
  event_type: string;
  horizon_hours: number;
  bucket_size: number;
  mature_samples: number;
  positives: number;
  observed_rate: number;
  buckets: CalibrationRateRow[];
  by_strongest_signal: CalibrationRateRow[];
};

export type FeedbackOutcome = {
  stage: string;
  event_type: string;
  success: boolean | null;
  source: string;
  observed_at: string;
};

export type FeedbackAction = {
  action_job_id: string;
  campaign_id: string;
  campaign_title: string;
  audience_member_id: string;
  person: string;
  username: string | null;
  platform: string;
  action: string;
  job_status: string;
  result_code: string | null;
  attempts: number;
  executed_at: string | null;
  activity_score: number | null;
  intent_score: number | null;
  readiness_score: number | null;
  strongest_signal_type: string | null;
  outcomes: FeedbackOutcome[];
};

export type FeedbackActionList = {
  items: FeedbackAction[];
  total: number;
  skip: number;
  limit: number;
};

export type ObserverCursor = {
  id: string;
  campaign_id: string;
  platform: string;
  status: string;
  last_observed_at: string | null;
  last_run_at: string | null;
  last_success_at: string | null;
  last_error: string | null;
  messages_seen: number;
  outcomes_created: number;
  run_count: number;
};

export type ObserverScanResult = {
  campaign_id: string;
  platform?: string | null;
  since?: string | null;
  messages_seen: number;
  outcomes_created: number;
  last_observed_at?: string | null;
  skipped: boolean;
  reason?: string | null;
  error?: string | null;
};

export function useLearningOverview() {
  return useQuery({
    queryKey: ["learning-overview"],
    queryFn: async () => {
      const { data } = await apiClient.get<LearningOverview>("/learning/overview");
      return data;
    },
    refetchInterval: 15_000,
  });
}

export function useCalibration(params: {
  stage: string;
  event_type: string;
  horizon_hours: number;
}) {
  return useQuery({
    queryKey: ["learning-calibration", params],
    queryFn: async () => {
      const { data } = await apiClient.get<CalibrationResult>("/learning/calibration", {
        params: { ...params, bucket_size: 20, min_confidence: 0.5 },
      });
      return data;
    },
  });
}

export function useFeedbackActions(limit = 100) {
  return useQuery({
    queryKey: ["learning-actions", limit],
    queryFn: async () => {
      const { data } = await apiClient.get<FeedbackActionList>("/learning/actions", {
        params: { limit },
      });
      return data;
    },
    refetchInterval: 15_000,
  });
}

export function useObserverStatus(limit = 100) {
  return useQuery({
    queryKey: ["learning-observer-status", limit],
    queryFn: async () => {
      const { data } = await apiClient.get<ObserverCursor[]>("/learning/observer/status", {
        params: { limit },
      });
      return data;
    },
    refetchInterval: 15_000,
  });
}

export function useScanCampaignObserver() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (campaignId: string) => {
      const { data } = await apiClient.post<ObserverScanResult>(
        `/learning/observer/campaigns/${campaignId}/scan`,
      );
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["learning-observer-status"] });
      qc.invalidateQueries({ queryKey: ["learning-actions"] });
      qc.invalidateQueries({ queryKey: ["learning-overview"] });
      qc.invalidateQueries({ queryKey: ["learning-calibration"] });
    },
  });
}

export function useRecordOutcome() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      action_job_id: string;
      stage: "engagement" | "business";
      event_type: string;
      success?: boolean | null;
      source?: string;
      confidence?: number;
      idempotency_key?: string;
      properties?: Record<string, unknown>;
    }) => {
      const { data } = await apiClient.post("/learning/outcomes", payload);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["learning-actions"] });
      qc.invalidateQueries({ queryKey: ["learning-overview"] });
      qc.invalidateQueries({ queryKey: ["learning-calibration"] });
    },
  });
}
