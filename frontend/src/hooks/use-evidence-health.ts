import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export type EvidenceWindowEstimate = {
  experiments: number;
  estimate: number | null;
  confidence_low: number | null;
  confidence_high: number | null;
  i_squared_percent: number | null;
};

export type EvidenceHealth = {
  objective: "incremental_outcomes" | "incremental_business_value";
  event_type: string;
  value_unit: string | null;
  horizon_hours: number;
  recent_window_days: number;
  max_evidence_age_days: number;
  latest_mature_assignment_at: string | null;
  evidence_age_days: number | null;
  recent: EvidenceWindowEstimate;
  historical: EvidenceWindowEstimate;
  drift_difference: number | null;
  drift_confidence_low: number | null;
  drift_confidence_high: number | null;
  drift_z_score: number | null;
  status: "insufficient" | "stable" | "watch" | "drift_positive" | "drift_negative" | "stale";
  recommend_reexperiment: boolean;
  warnings: string[];
};

export function useEvidenceHealth() {
  return useMutation({
    mutationFn: async (payload: {
      objective: "incremental_outcomes" | "incremental_business_value";
      stage: "engagement" | "business";
      event_type: string;
      value_unit?: string | null;
      value_aggregation?: "sum" | "max" | null;
      horizon_hours: number;
      recent_window_days: number;
      max_evidence_age_days: number;
    }) => {
      const { data } = await apiClient.post<EvidenceHealth>("/experiments/evidence-health", payload);
      return data;
    },
  });
}
