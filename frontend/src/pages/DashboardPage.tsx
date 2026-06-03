import { useQuery } from "@tanstack/react-query";
import { CitationBarChart } from "../components/CitationBarChart";
import { GapAnalysisTable } from "../components/GapAnalysisTable";
import { KpiStrip } from "../components/KpiStrip";
import { apiFetch } from "../lib/api";
import type { DashboardData } from "../types";

export function DashboardPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => apiFetch<DashboardData>("/api/reports/dashboard"),
    refetchInterval: 60000,
  });

  if (isLoading) return <p className="text-black/50">Loading dashboard…</p>;
  if (error) return <p className="text-orange">Failed to load dashboard: {(error as Error).message}</p>;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <KpiStrip data={data} />
      <div className="grid lg:grid-cols-2 gap-6">
        <CitationBarChart
          data={data.citation_by_brand}
          dataKey="brand_id"
          title="Citation Share by Brand"
        />
        <CitationBarChart
          data={data.citation_by_category}
          dataKey="category"
          title="Citation Share by Category"
        />
      </div>
      <GapAnalysisTable gaps={data.gap_queries} />
    </div>
  );
}
