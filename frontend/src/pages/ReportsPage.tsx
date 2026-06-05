import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../lib/api";

interface MonthlyReport {
  id?: number;
  message?: string;
  report_month?: string;
  overall_citation_share?: number;
  ai_referred_sessions?: number;
  content_pieces_published?: number;
  schema_coverage_pct?: number;
  gap_queries?: { query: string; competitor_cited: string }[];
  created_at?: string;
}

export function ReportsPage() {
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ["latest-report"],
    queryFn: () => apiFetch<MonthlyReport>("/api/reports/latest"),
  });

  const generate = useMutation({
    mutationFn: () => apiFetch<MonthlyReport>("/api/reports/generate", { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["latest-report"] }),
  });

  const handlePrint = () => window.print();

  const isEmpty = data?.message === "No reports generated yet";

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4 print:hidden">
        <h2 className="font-display text-xl font-bold text-navy">Monthly Report</h2>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => generate.mutate()}
            disabled={generate.isPending}
            className="px-4 py-2 bg-orange text-white rounded text-sm hover:bg-orange/90 disabled:opacity-50"
          >
            {generate.isPending ? "Generating…" : isEmpty ? "Generate Report Now" : "Refresh snapshot"}
          </button>
          {!isEmpty && data && !data.message && (
            <button
              type="button"
              onClick={handlePrint}
              className="px-4 py-2 bg-navy text-white rounded text-sm hover:bg-navy/90"
            >
              Download PDF (Print)
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 text-sm px-4 py-3 rounded">
          Failed to load report: {(error as Error).message}
        </div>
      )}

      {generate.isError && (
        <div className="bg-orange/10 border border-orange/30 text-orange text-sm px-4 py-3 rounded">
          {(generate.error as Error).message}
        </div>
      )}

      {isLoading ? (
        <p className="text-black/50">Loading report…</p>
      ) : isEmpty ? (
        <div className="bg-white rounded border border-black/8 p-8 space-y-3">
          <p className="text-black/60">No monthly report has been generated yet.</p>
          <p className="text-sm text-black/45">
            Reports are normally created automatically on the last day of each month. Click{" "}
            <strong>Generate Report Now</strong> to snapshot current dashboard KPIs, or wait for
            citation audits (1st &amp; 15th) and content publishing to populate the metrics.
          </p>
        </div>
      ) : (
        <div className="bg-white rounded border border-black/8 p-8 space-y-6" id="report">
          <div className="border-b border-black/10 pb-6">
            <h1 className="font-display text-2xl font-bold text-navy">Axxiom AEO Monthly Report</h1>
            <p className="text-sm text-black/50 mt-1">
              {data?.report_month ? `Period: ${data.report_month}` : ""}
              {data?.created_at ? ` · Generated ${new Date(data.created_at).toLocaleString()}` : ""}
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

          {(data?.overall_citation_share ?? 0) === 0 &&
            (data?.content_pieces_published ?? 0) === 0 && (
              <p className="text-sm text-black/45">
                KPIs are zero until citation audits run and content is published. Run a citation
                audit from Citations, or approve content in Content Review.
              </p>
            )}

          {Array.isArray(data?.gap_queries) && data.gap_queries.length > 0 && (
            <div>
              <h3 className="font-display font-bold text-navy mb-3">Top Gap Queries</h3>
              <ul className="space-y-2 text-sm">
                {data.gap_queries.slice(0, 10).map((g, i) => (
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
