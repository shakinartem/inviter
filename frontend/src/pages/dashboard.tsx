import { useAccountStats } from "@/hooks/use-accounts";
import { useProxyStats } from "@/hooks/use-proxies";
import { useParserStats } from "@/hooks/use-parser";
import { useCampaigns } from "@/hooks/use-campaigns";
import { Users, Shield, Search, Send, Activity, CheckCircle, XCircle, Clock } from "lucide-react";

function StatCard({
  title,
  value,
  icon: Icon,
  description,
  className,
}: {
  title: string;
  value: string | number;
  icon: React.ElementType;
  description?: string;
  className?: string;
}) {
  return (
    <div className="rounded-xl border border-black/5 bg-white p-5 shadow-sm transition-shadow hover:shadow-md">
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <p className="text-sm font-medium text-muted">{title}</p>
          <p className="text-3xl font-semibold text-ink">{value}</p>
          {description && <p className="text-xs text-muted">{description}</p>}
        </div>
        <div className={`rounded-lg p-2.5 ${className}`}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { data: accountStats, isLoading: loadingAccounts } = useAccountStats();
  const { data: proxyStats, isLoading: loadingProxies } = useProxyStats();
  const { data: parserStats, isLoading: loadingParser } = useParserStats();
  const { data: campaigns, isLoading: loadingCampaigns } = useCampaigns();

  const activeCampaigns = campaigns?.filter((c) => c.status === "active") ?? [];
  const failedCampaigns = campaigns?.filter((c) => c.status === "failed") ?? [];
  const completedCampaigns = campaigns?.filter((c) => c.status === "completed") ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">Dashboard</h1>
        <p className="text-sm text-muted mt-1">Overview of your Telegram inviter system</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Accounts"
          value={loadingAccounts ? "..." : accountStats?.total ?? 0}
          icon={Users}
          description={`${accountStats?.active ?? 0} active · ${accountStats?.banned ?? 0} banned`}
          className="bg-blue-50 text-blue-600"
        />
        <StatCard
          title="Proxies"
          value={loadingProxies ? "..." : proxyStats?.total ?? 0}
          icon={Shield}
          description={`${proxyStats?.working ?? 0} working · ${proxyStats?.failing ?? 0} failing`}
          className="bg-green-50 text-green-600"
        />
        <StatCard
          title="Parsed Chats"
          value={loadingParser ? "..." : parserStats?.total_chats ?? 0}
          icon={Search}
          description={`${parserStats?.total_parses ?? 0} total parses`}
          className="bg-purple-50 text-purple-600"
        />
        <StatCard
          title="Campaigns"
          value={loadingCampaigns ? "..." : campaigns?.length ?? 0}
          icon={Send}
          description={`${activeCampaigns.length} active · ${completedCampaigns.length} completed`}
          className="bg-orange-50 text-orange-600"
        />
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Account Breakdown */}
        <div className="rounded-xl border border-black/5 bg-white p-5 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold text-ink">Account Status</h3>
          <div className="space-y-2">
            <StatRow label="Active" value={accountStats?.active ?? 0} color="text-green-600" />
            <StatRow label="Banned" value={accountStats?.banned ?? 0} color="text-red-600" />
            <StatRow label="Limited" value={accountStats?.limited ?? 0} color="text-yellow-600" />
            <StatRow label="Cooldown" value={accountStats?.cooldown ?? 0} color="text-orange-600" />
            <StatRow label="Premium" value={accountStats?.premium_count ?? 0} color="text-blue-600" />
          </div>
        </div>

        {/* Recent Campaigns */}
        <div className="rounded-xl border border-black/5 bg-white p-5 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold text-ink">Recent Campaigns</h3>
          {loadingCampaigns ? (
            <p className="text-sm text-muted">Loading...</p>
          ) : campaigns && campaigns.length > 0 ? (
            <div className="space-y-2">
              {campaigns.slice(0, 5).map((c) => (
                <div key={c.id} className="flex items-center justify-between text-sm">
                  <span className="truncate text-ink max-w-[160px]">{c.title}</span>
                  <span className={`text-xs font-medium ${
                    c.status === "active" ? "text-green-600" :
                    c.status === "completed" ? "text-blue-600" :
                    c.status === "failed" ? "text-red-600" :
                    "text-muted"
                  }`}>
                    {c.status}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted">No campaigns yet</p>
          )}
        </div>

        {/* Quick Stats */}
        <div className="rounded-xl border border-black/5 bg-white p-5 shadow-sm">
          <h3 className="mb-3 text-sm font-semibold text-ink">Quick Stats</h3>
          <div className="space-y-2">
            <StatRow label="Invites Today" value={accountStats?.total_invites_today ?? 0} color="text-ink" icon={Activity} />
            <StatRow label="Avg Success Rate" value={`${((accountStats?.avg_success_rate ?? 0) * 100).toFixed(1)}%`} color="text-ink" icon={CheckCircle} />
            <StatRow label="Failed Campaigns" value={failedCampaigns.length} color="text-red-600" icon={XCircle} />
            <StatRow label="Active Campaigns" value={activeCampaigns.length} color="text-green-600" icon={Clock} />
          </div>
        </div>
      </div>
    </div>
  );
}

function StatRow({ label, value, color, icon: Icon }: { label: string; value: string | number; color: string; icon?: React.ElementType }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <div className="flex items-center gap-2">
        {Icon && <Icon className={`h-3.5 w-3.5 ${color}`} />}
        <span className="text-muted">{label}</span>
      </div>
      <span className={`font-medium ${color}`}>{value}</span>
    </div>
  );
}