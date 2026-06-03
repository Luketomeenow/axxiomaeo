import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../lib/api";

export function ReportsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["latest-report"],
    queryFn: () => apiFetch<Record<string, unknown>>("/api/reports/latest"),
  });

  const handlePrint = () => window.print();

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between print:hidden">
        <h2 className="font-display text-xl font-bold text-navy">Monthly Report</h2>
        <button
          onClick={handlePrint}
          className="px-4 py-2 bg-navy text-white rounded text-sm hover:bg-navy/90"
        >
          Download PDF (Print)
        </button>
      </div>

      {isLoading ? (
        <p className="text-black/50">Loading report…</p>
      ) : data?.message ? (
        <p className="text-black/50">{data.message as string}</p>
      ) : (
        <div className="bg-white rounded border border-black/8 p-8 space-y-6" id="report">
          <div className="border-b border-black/10 pb-6">
            <h1 className="font-display text-2xl font-bold text-navy">Axxiom AEO Monthly Report</h1>
            <p className="text-sm text-black/50 mt-1">
              {data?.report_month ? `Period: ${data.report_month}` : ""}
            </p>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: "Citation Share", value: `${data?.overall_citation_share ?? 0}%` },
              { label: "AI Sessions", value: data?.ai_referred_sessions ?? 0 },
              { label: "Content Published", value: data?.content_pieces_published ?? 0 },
              { label: "Schema Coverage", value: `${data?.schema_coverage_pct ?? 0}%` },
            ].map((kpi) => (
              <div key={kpi.label} className="border border-black/8 rounded p-4">
                <p className="text-xs text-black/50 uppercase">{kpi.label}</p>
                <p className="font-display text-2xl font-bold text-navy mt-1">{kpi.value}</p>
              </div>
            ))}
          </div>

          {Array.isArray(data?.gap_queries) && (data.gap_queries as unknown[]).length > 0 && (
            <div>
              <h3 className="font-display font-bold text-navy mb-3">Top Gap Queries</h3>
              <ul className="space-y-2 text-sm">
                {(data.gap_queries as { query: string; competitor_cited: string }[])
                  .slice(0, 10)
                  .map((g, i) => (
                    <li key={i} className="flex justify-between border-b border-black/5 pb-2">
                      <span>{g.query}</span>
                      <span className="text-orange text-xs">{g.competitor_cited}</span>
                    </li>
                  ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
