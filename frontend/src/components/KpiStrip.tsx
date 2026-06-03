import type { DashboardData } from "../types";

interface Props {
  data: DashboardData;
}

function KpiCard({
  label,
  value,
  sub,
  trend,
}: {
  label: string;
  value: string | number;
  sub?: string;
  trend?: number;
}) {
  return (
    <div className="bg-white rounded border border-black/8 p-5">
      <p className="text-xs text-black/50 uppercase tracking-wide mb-1">{label}</p>
      <p className="font-display text-3xl font-bold text-navy">{value}</p>
      {sub && <p className="text-xs text-black/40 mt-1">{sub}</p>}
      {trend !== undefined && (
        <p className={`text-xs mt-1 font-medium ${trend >= 0 ? "text-green-700" : "text-orange"}`}>
          {trend >= 0 ? "↑" : "↓"} {Math.abs(trend).toFixed(1)}% vs last month
        </p>
      )}
    </div>
  );
}

export function KpiStrip({ data }: Props) {
  const lastUpdated = data.last_updated
    ? new Date(data.last_updated).toLocaleTimeString()
    : "—";

  return (
    <div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-2">
        <KpiCard
          label="AI Citation Share"
          value={`${data.citation_share}%`}
          sub={`Previous month: ${data.citation_share_prev}%`}
          trend={data.citation_trend}
        />
        <KpiCard label="AI-Referred Sessions" value={data.ai_referred_sessions} sub="Month to date" />
        <KpiCard label="Content Published" value={data.content_published_mtd} sub="Month to date" />
        <KpiCard label="Schema Coverage" value={`${data.schema_coverage_pct}%`} />
      </div>
      <p className="text-xs text-black/40 text-right">Last updated: {lastUpdated}</p>
    </div>
  );
}
