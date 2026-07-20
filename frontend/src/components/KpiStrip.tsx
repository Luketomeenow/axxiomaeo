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
    <div className="aeo-panel p-5 relative overflow-hidden">
      <div className="absolute top-0 right-0 w-24 h-24 bg-cyan/5 rounded-full -translate-y-1/2 translate-x-1/2" />
      <p className="text-[10px] text-muted uppercase tracking-widest mb-2">{label}</p>
      <p className="aeo-kpi-value">{value}</p>
      {sub && <p className="text-xs text-muted mt-2">{sub}</p>}
      {trend !== undefined && (
        <p
          className={`text-xs mt-2 font-medium ${trend >= 0 ? "text-success" : "text-warning"}`}
        >
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
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-2">
        <KpiCard
          label="AI Visibility"
          value={`${data.avg_visibility_pct ?? data.citation_share}%`}
          sub={`${data.citation_share}% citation rate · 3× probabilistic runs`}
          trend={data.citation_trend}
        />
        <KpiCard
          label="Share of Voice"
          value={`${data.share_of_voice ?? 0}%`}
          sub="Your citations vs competitor wins"
        />
        <KpiCard
          label="Topic Coverage"
          value={`${data.topic_coverage_pct ?? 0}%`}
          sub={`${data.platform_consensus_pct ?? 0}% multi-platform consensus`}
        />
        <KpiCard
          label="AI-Referred Sessions"
          value={data.ai_referred_sessions}
          sub={`Schema ${data.schema_coverage_pct}% · ${data.content_published_mtd} posts MTD`}
        />
        <KpiCard
          label="AI Conversions"
          value={data.ai_referred_conversions ?? 0}
          sub={
            (data.ai_referred_conversions ?? 0) > 0
              ? `${data.ai_conversion_rate ?? 0}% of AI sessions convert (30d)`
              : "GA4 key events from AI visitors (30d)"
          }
        />
      </div>
      <p className="text-xs text-muted text-right font-mono">Last updated {lastUpdated}</p>
    </div>
  );
}
