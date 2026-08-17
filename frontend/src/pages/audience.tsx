import { useMemo, useState } from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Activity, Brain, Radar, Users, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { useAudience, useIntentSignals, type AudienceMember } from "@/hooks/use-intelligence";

const columnHelper = createColumnHelper<AudienceMember>();

function score(value: number | null) {
  if (value == null) return "—";
  return value.toFixed(1);
}

function humanize(value: string) {
  return value.replace(/_/g, " ");
}

export default function AudiencePage() {
  const [platform, setPlatform] = useState("telegram");
  const [minActivity, setMinActivity] = useState("0");
  const [minReadiness, setMinReadiness] = useState("0");
  const [selectedMember, setSelectedMember] = useState<AudienceMember | null>(null);

  const params = useMemo(
    () => ({
      platform: platform || undefined,
      min_activity_score: Number(minActivity) || undefined,
      min_readiness_score: Number(minReadiness) || undefined,
      limit: 500,
    }),
    [platform, minActivity, minReadiness],
  );

  const { data, isLoading } = useAudience(params);
  const { data: signals, isLoading: signalsLoading } = useIntentSignals(
    selectedMember ? { audience_member_id: selectedMember.id, limit: 20 } : undefined,
  );
  const audience = data?.items ?? [];

  const columns = useMemo(
    () => [
      columnHelper.accessor("username", {
        header: "Person",
        cell: (info) => {
          const item = info.row.original;
          const name = [item.first_name, item.last_name].filter(Boolean).join(" ");
          return (
            <div>
              <p className="font-medium text-ink">{name || item.username || item.external_user_id}</p>
              <p className="text-xs text-muted">
                {item.username ? `@${item.username}` : item.external_user_id}
              </p>
            </div>
          );
        },
      }),
      columnHelper.accessor("activity_score", {
        header: "Activity",
        cell: (info) => <span className="font-medium">{score(info.getValue())}</span>,
      }),
      columnHelper.accessor("relevance_score", {
        header: "Relevance",
        cell: (info) => score(info.getValue()),
      }),
      columnHelper.accessor("intent_score", {
        header: "Intent",
        cell: (info) => {
          const value = info.getValue();
          return (
            <span className="inline-flex min-w-14 justify-center rounded-full bg-violet-50 px-2.5 py-1 text-xs font-semibold text-violet-700">
              {score(value)}
            </span>
          );
        },
      }),
      columnHelper.accessor("readiness_score", {
        header: "Readiness",
        cell: (info) => {
          const value = info.getValue();
          return (
            <span className="inline-flex min-w-14 justify-center rounded-full bg-stone-100 px-2.5 py-1 text-xs font-semibold text-ink">
              {score(value)}
            </span>
          );
        },
      }),
      columnHelper.accessor("last_activity_at", {
        header: "Last activity",
        cell: (info) => {
          const value = info.getValue();
          return value ? new Date(value).toLocaleString() : "—";
        },
      }),
      columnHelper.accessor("platform", {
        header: "Platform",
        cell: (info) => <span className="capitalize">{info.getValue()}</span>,
      }),
      columnHelper.display({
        id: "explain",
        header: "Why",
        cell: (info) => (
          <Button
            size="sm"
            variant="outline"
            disabled={(info.row.original.intent_score ?? 0) <= 0}
            onClick={() => setSelectedMember(info.row.original)}
          >
            <Radar className="mr-1 h-3.5 w-3.5" /> Explain
          </Button>
        ),
      }),
    ],
    [],
  );

  const readyCount = audience.filter((item) => (item.readiness_score ?? 0) >= 60).length;
  const activeCount = audience.filter((item) => (item.activity_score ?? 0) >= 60).length;
  const highIntentCount = audience.filter((item) => (item.intent_score ?? 0) >= 60).length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">Audience Intelligence</h1>
        <p className="mt-1 text-sm text-muted">
          Deduplicated people ranked by activity, relevance, intent and readiness.
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted">
            <Users className="h-4 w-4" /> Profiles
          </div>
          <p className="mt-3 text-2xl font-semibold text-ink">{data?.total ?? 0}</p>
        </div>
        <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted">
            <Activity className="h-4 w-4" /> Active 60+
          </div>
          <p className="mt-3 text-2xl font-semibold text-ink">{activeCount}</p>
        </div>
        <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted">
            <Radar className="h-4 w-4" /> Intent 60+
          </div>
          <p className="mt-3 text-2xl font-semibold text-ink">{highIntentCount}</p>
        </div>
        <div className="rounded-xl border border-black/5 bg-white p-4 shadow-sm">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted">
            <Brain className="h-4 w-4" /> Ready 60+
          </div>
          <p className="mt-3 text-2xl font-semibold text-ink">{readyCount}</p>
        </div>
      </div>

      <div className="grid gap-3 rounded-xl border border-black/5 bg-white p-4 shadow-sm md:grid-cols-3">
        <label className="space-y-1 text-xs font-medium text-muted">
          Platform
          <select
            className="w-full rounded-lg border border-black/10 bg-white px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            value={platform}
            onChange={(event) => setPlatform(event.target.value)}
          >
            <option value="telegram">Telegram</option>
            <option value="discord">Discord</option>
            <option value="">All platforms</option>
          </select>
        </label>
        <label className="space-y-1 text-xs font-medium text-muted">
          Min activity
          <input
            className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            type="number"
            min={0}
            max={100}
            value={minActivity}
            onChange={(event) => setMinActivity(event.target.value)}
          />
        </label>
        <label className="space-y-1 text-xs font-medium text-muted">
          Min readiness
          <input
            className="w-full rounded-lg border border-black/10 px-3 py-2 text-sm text-ink outline-none focus:border-accent"
            type="number"
            min={0}
            max={100}
            value={minReadiness}
            onChange={(event) => setMinReadiness(event.target.value)}
          />
        </label>
      </div>

      <DataTable columns={columns} data={audience} loading={isLoading} pageSize={25} />

      {selectedMember && (
        <div className="rounded-xl border border-black/5 bg-white p-5 shadow-sm">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-ink">Why this person has intent</h2>
              <p className="mt-1 text-sm text-muted">
                {selectedMember.username ? `@${selectedMember.username}` : selectedMember.external_user_id}
                {" · "}Intent {score(selectedMember.intent_score)}
                {" · "}Readiness {score(selectedMember.readiness_score)}
              </p>
            </div>
            <Button size="sm" variant="ghost" onClick={() => setSelectedMember(null)}>
              <X className="h-4 w-4" />
            </Button>
          </div>

          <div className="mt-4 space-y-2">
            {signalsLoading && <p className="text-sm text-muted">Loading signals…</p>}
            {!signalsLoading && !(signals?.length) && (
              <p className="text-sm text-muted">No versioned evidence is available for this profile yet.</p>
            )}
            {(signals ?? []).map((signal) => {
              const dimensions = (signal.features?.dimensions ?? {}) as Record<string, string[]>;
              const dimensionNames = Object.keys(dimensions).map(humanize);
              const topicTerms = (signal.features?.topic_terms ?? []) as string[];
              return (
                <div key={signal.id} className="rounded-lg border border-black/5 bg-stone-50 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full bg-violet-100 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-violet-700">
                        {humanize(signal.signal_type)}
                      </span>
                      <span className="text-sm font-semibold text-ink">Score {signal.score.toFixed(1)}</span>
                      <span className="text-xs text-muted">confidence {(signal.confidence * 100).toFixed(0)}%</span>
                    </div>
                    <span className="text-xs text-muted">{new Date(signal.observed_at).toLocaleString()}</span>
                  </div>
                  <p className="mt-2 text-xs text-muted">
                    Matched dimensions: {dimensionNames.length ? dimensionNames.join(", ") : "topic interest"}
                    {topicTerms.length ? ` · topic terms: ${topicTerms.join(", ")}` : ""}
                    {` · model: ${signal.model_version}`}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
