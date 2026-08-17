import { useMemo, useState } from "react";
import { BrainCircuit, Check, MessageCircle, Target, Users } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  useCalibration,
  useFeedbackActions,
  useLearningOverview,
  useRecordOutcome,
  type FeedbackAction,
} from "@/hooks/use-learning";

function score(value: number | null) {
  return value == null ? "—" : value.toFixed(1);
}

export default function LearningPage() {
  const [stage, setStage] = useState("business");
  const [eventType, setEventType] = useState("converted");
  const [horizonHours, setHorizonHours] = useState(168);

  const { data: overview } = useLearningOverview();
  const { data: calibration, isLoading: calibrationLoading } = useCalibration({
    stage,
    event_type: eventType,
    horizon_hours: horizonHours,
  });
  const { data: feedback, isLoading: feedbackLoading } = useFeedbackActions(100);
  const recordOutcome = useRecordOutcome();

  const labelAction = async (
    item: FeedbackAction,
    labelStage: "engagement" | "business",
    type: string,
  ) => {
    try {
      await recordOutcome.mutateAsync({
        action_job_id: item.action_job_id,
        stage: labelStage,
        event_type: type,
        success: true,
        source: "manual",
        confidence: 1,
        idempotency_key: `${item.action_job_id}:${labelStage}:${type}`,
        properties: { labeled_from: "learning_feedback_queue" },
      });
      toast.success(`Outcome recorded: ${type.replace(/_/g, " ")}`);
    } catch {
      toast.error("Could not save outcome label");
    }
  };

  const hasOutcome = (item: FeedbackAction, labelStage: string, type: string) =>
    item.outcomes.some((outcome) => outcome.stage === labelStage && outcome.event_type === type);

  const cards = useMemo(
    () => [
      { label: "Decision snapshots", value: overview?.snapshots ?? 0, icon: BrainCircuit },
      { label: "Transport events", value: overview?.events_by_stage.transport ?? 0, icon: Target },
      { label: "Engagement labels", value: overview?.events_by_stage.engagement ?? 0, icon: MessageCircle },
      { label: "Business labels", value: overview?.events_by_stage.business ?? 0, icon: Check },
    ],
    [overview],
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">Outcome Learning</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">
          Compare what the system predicted before an action with what actually happened later.
          Transport, engagement and business outcomes stay separate so technical delivery never masquerades as buyer intent.
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        {cards.map((card) => (
          <div key={card.label} className="rounded-xl border border-black/5 bg-white p-4 shadow-sm">
            <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted">
              <card.icon className="h-4 w-4" /> {card.label}
            </div>
            <p className="mt-3 text-2xl font-semibold text-ink">{card.value}</p>
          </div>
        ))}
      </div>

      <section className="space-y-4 rounded-xl border border-black/5 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold text-ink">Prediction calibration</h2>
            <p className="mt-1 max-w-2xl text-xs text-muted">
              Only actions whose complete observation horizon has elapsed enter the denominator. This avoids treating recent actions as false negatives.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <select
              value={stage}
              onChange={(event) => setStage(event.target.value)}
              className="rounded-lg border border-black/10 bg-white px-3 py-2 text-sm"
            >
              <option value="business">Business</option>
              <option value="engagement">Engagement</option>
              <option value="transport">Transport</option>
            </select>
            <input
              value={eventType}
              onChange={(event) => setEventType(event.target.value)}
              className="w-36 rounded-lg border border-black/10 px-3 py-2 text-sm"
              placeholder="converted"
            />
            <select
              value={horizonHours}
              onChange={(event) => setHorizonHours(Number(event.target.value))}
              className="rounded-lg border border-black/10 bg-white px-3 py-2 text-sm"
            >
              <option value={24}>24h horizon</option>
              <option value={72}>3 day horizon</option>
              <option value={168}>7 day horizon</option>
              <option value={336}>14 day horizon</option>
              <option value={720}>30 day horizon</option>
            </select>
          </div>
        </div>

        {calibrationLoading ? (
          <p className="text-sm text-muted">Calculating mature cohorts…</p>
        ) : calibration && calibration.mature_samples > 0 ? (
          <div className="space-y-5">
            <div className="flex flex-wrap gap-6 text-sm">
              <div><span className="text-muted">Mature samples</span><p className="font-semibold text-ink">{calibration.mature_samples}</p></div>
              <div><span className="text-muted">Observed outcomes</span><p className="font-semibold text-ink">{calibration.positives}</p></div>
              <div><span className="text-muted">Observed rate</span><p className="font-semibold text-ink">{calibration.observed_rate.toFixed(1)}%</p></div>
            </div>

            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">By readiness at action time</h3>
              <div className="overflow-hidden rounded-lg border border-black/5">
                <table className="w-full text-left text-sm">
                  <thead className="bg-stone-50 text-xs text-muted">
                    <tr><th className="px-3 py-2">Readiness</th><th className="px-3 py-2">Samples</th><th className="px-3 py-2">Outcomes</th><th className="px-3 py-2">Rate</th><th className="px-3 py-2">95% interval</th></tr>
                  </thead>
                  <tbody>
                    {calibration.buckets.map((row) => (
                      <tr key={row.label} className="border-t border-black/5">
                        <td className="px-3 py-2 font-medium">{row.label}</td>
                        <td className="px-3 py-2">{row.samples}</td>
                        <td className="px-3 py-2">{row.positives}</td>
                        <td className="px-3 py-2 font-semibold">{row.rate.toFixed(1)}%</td>
                        <td className="px-3 py-2 text-muted">{row.confidence_low.toFixed(1)}–{row.confidence_high.toFixed(1)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">By strongest intent signal</h3>
              <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                {calibration.by_strongest_signal.map((row) => (
                  <div key={row.label} className="rounded-lg border border-black/5 bg-stone-50 p-3">
                    <p className="text-xs text-muted">{row.label.replace(/_/g, " ")}</p>
                    <div className="mt-1 flex items-end justify-between gap-2">
                      <p className="text-xl font-semibold text-ink">{row.rate.toFixed(1)}%</p>
                      <p className="text-xs text-muted">n={row.samples}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="rounded-lg bg-stone-50 p-4 text-sm text-muted">
            No mature cohort yet for <span className="font-medium text-ink">{stage}:{eventType}</span>. Actions only enter calibration after the full {horizonHours}-hour observation window.
          </div>
        )}
      </section>

      <section className="space-y-4 rounded-xl border border-black/5 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold text-ink">Feedback queue</h2>
            <p className="mt-1 text-xs text-muted">
              Label downstream outcomes. Each click becomes an idempotent training label tied to the original decision-time snapshot.
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted"><Users className="h-4 w-4" /> {feedback?.total ?? 0} attempted actions</div>
        </div>

        {feedbackLoading ? (
          <p className="text-sm text-muted">Loading actions…</p>
        ) : (
          <div className="space-y-2">
            {(feedback?.items ?? []).map((item) => (
              <div key={item.action_job_id} className="grid gap-3 rounded-lg border border-black/5 p-3 lg:grid-cols-[1.4fr_1fr_0.8fr_1.8fr] lg:items-center">
                <div>
                  <p className="font-medium text-ink">{item.person}</p>
                  <p className="text-xs text-muted">{item.username ? `@${item.username}` : item.platform} · {item.campaign_title}</p>
                </div>
                <div className="flex gap-3 text-xs">
                  <span><span className="text-muted">Intent</span> <b>{score(item.intent_score)}</b></span>
                  <span><span className="text-muted">Ready</span> <b>{score(item.readiness_score)}</b></span>
                </div>
                <div>
                  <StatusBadge status={item.job_status} />
                  <p className="mt-1 text-[10px] text-muted">{item.result_code ?? "no result"}</p>
                </div>
                <div className="flex flex-wrap justify-start gap-1 lg:justify-end">
                  <Button size="sm" variant={hasOutcome(item, "engagement", "joined") ? "default" : "outline"} disabled={recordOutcome.isPending || hasOutcome(item, "engagement", "joined")} onClick={() => labelAction(item, "engagement", "joined")}>Joined</Button>
                  <Button size="sm" variant={hasOutcome(item, "engagement", "replied") ? "default" : "outline"} disabled={recordOutcome.isPending || hasOutcome(item, "engagement", "replied")} onClick={() => labelAction(item, "engagement", "replied")}>Replied</Button>
                  <Button size="sm" variant={hasOutcome(item, "business", "converted") ? "default" : "outline"} disabled={recordOutcome.isPending || hasOutcome(item, "business", "converted")} onClick={() => labelAction(item, "business", "converted")}>Converted</Button>
                  <Button size="sm" variant={hasOutcome(item, "engagement", "not_interested") ? "default" : "ghost"} disabled={recordOutcome.isPending || hasOutcome(item, "engagement", "not_interested")} onClick={() => labelAction(item, "engagement", "not_interested")}>Not interested</Button>
                </div>
              </div>
            ))}
            {(feedback?.items.length ?? 0) === 0 && (
              <div className="rounded-lg bg-stone-50 p-4 text-sm text-muted">No attempted actions yet. Once campaigns execute, their decision snapshots and feedback rows will appear here.</div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
