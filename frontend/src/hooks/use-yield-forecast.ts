import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type YieldEvidenceRow = {
  label: string;
  evidence_level: "exact" | "readiness" | "signal" | "global";
  current_members: number;
  historical_samples: number;
  historical_positives: number;
  observed_rate: number;
  posterior_rate: number;
  confidence_low: number;
  confidence_high: number;
};

export type SegmentYieldForecast = {
  segment_id: string;
  segment_name: string;
  platform: string;
  stage: string;
  event_type: string;
  horizon_hours: number;
  requested_budget: number;
  evaluated_members: number;
  historical_samples: number;
  historical_positives: number;
  historical_observed_rate: number;
  expected_outcomes: number;
  expected_rate: number;
  confidence_low_outcomes: number;
  confidence_high_outcomes: number;
  confidence_low_rate: number;
  confidence_high_rate: number;
  frozen_history_ratio: number;
  evidence_coverage: Record<string, number>;
  quality_status: "insufficient" | "limited" | "ready";
  warnings: string[];
  evidence_rows: YieldEvidenceRow[];
};

export function useYieldForecast(
  segmentId: string | null,
  params: { stage: string; event_type: string; horizon_hours: number; budget: number },
) {
  return useQuery({
    queryKey: ["yield-forecast", segmentId, params],
    queryFn: async () => {
      const { data } = await apiClient.get<SegmentYieldForecast>(`/segments/${segmentId}/forecast`, {
        params: { ...params, min_confidence: 0.5 },
      });
      return data;
    },
    enabled: !!segmentId,
  });
}
