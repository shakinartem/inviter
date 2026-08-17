import { useMemo, useState } from "react";
import { createColumnHelper } from "@tanstack/react-table";
import { Activity, Brain, Users } from "lucide-react";

import { DataTable } from "@/components/ui/data-table";
import { useAudience, type AudienceMember } from "@/hooks/use-intelligence";

const columnHelper = createColumnHelper<AudienceMember>();

function score(value: number | null) {
  if (value == null) return "—";
  return value.toFixed(1);
}

export default function AudiencePage() {
  const [platform, setPlatform] = useState("telegram");
  const [minActivity, setMinActivity] = useState("0");
  const [minReadiness, setMinReadiness] = useState("0");

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
        cell: (info) => score(info.getValue()),
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
    ],
    [],
  );

  const readyCount = audience.filter((item) => (item.readiness_score ?? 0) >= 60).length;
  const activeCount = audience.filter((item) => (item.activity_score ?? 0) >= 60).length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">Audience Intelligence</h1>
        <p className="mt-1 text-sm text-muted">
          Deduplicated people ranked by activity, relevance, intent and readiness.
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
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
    </div>
  );
}
