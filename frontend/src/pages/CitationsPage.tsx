import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { CitationBarChart } from "../components/CitationBarChart";
import { GapAnalysisTable } from "../components/GapAnalysisTable";
import { QueryStatus } from "../components/QueryStatus";
import { apiFetch } from "../lib/api";
import type { DashboardData } from "../types";

interface CitationRecord {
  id: number;
  brand_id: string;
  query: string;
  query_category: string;
  platform: string;
  is_cited: boolean;
  is_mentioned?: boolean;
  is_url_cited?: boolean;
  visibility_pct?: number;
  sample_runs?: number;
  parent_query?: string | null;
  funnel_stage?: string | null;
  competitor_cited: string;
  checked_at: string;
}

interface AuditResponse {
  status: string;
  message?: string;
}

export function CitationsPage() {
  const queryClient = useQueryClient();
  const [auditMsg, setAuditMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  const audit = useMutation({
    mutationFn: () => apiFetch<AuditResponse>("/api/citations/audit", { method: "POST" }),
    onSuccess: (data) => {
      if (data.status === "audit_started") {
        setAuditMsg({
          type: "ok",
          text: "Citation audit started in the background. Results will appear here in a few minutes.",
        });
        setTimeout(() => {
          queryClient.invalidateQueries({ queryKey: ["citations"] });
          queryClient.invalidateQueries({ queryKey: ["dashboard-citations"] });
          queryClient.invalidateQueries({ queryKey: ["gaps"] });
        }, 5000);
      } else {
        setAuditMsg({
          type: "err",
          text:
            data.message ||
            "Citation provider unavailable. Start GEO/AEO Tracker on port 3000 or set CITATION_PROVIDER=none in backend/.env.",
        });
      }
    },
    onError: (err: Error) => {
      setAuditMsg({
        type: "err",
        text: err.message.includes("Failed to fetch")
          ? "Cannot reach the backend — start it with: cd backend && venv\\Scripts\\uvicorn.exe app.main:app --reload --port 8000"
          : err.message,
      });
    },
  });

  const {
    data: dashboard,
    isLoading: loadingDashboard,
    isError: dashboardError,
    error: dashboardErr,
  } = useQuery({
    queryKey: ["dashboard-citations"],
    queryFn: () => apiFetch<DashboardData>("/api/reports/dashboard"),
    retry: 1,
  });

  const {
    data: citations,
    isLoading,
    isError: citationsError,
    error: citationsErr,
  } = useQuery({
    queryKey: ["citations"],
    queryFn: () => apiFetch<CitationRecord[]>("/api/citations/latest"),
    refetchInterval: 60000,
    retry: 1,
  });

  const { data: gaps } = useQuery({
    queryKey: ["gaps"],
    queryFn: () => apiFetch<DashboardData["gap_queries"]>("/api/citations/gaps"),
    retry: 1,
  });

  const cited = citations?.filter((c) => c.is_cited).length ?? 0;
  const total = citations?.length ?? 0;
  const listError = dashboardError || citationsError;
  const listErr = (dashboardErr || citationsErr) as Error | null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-ink">Citation Monitoring</h2>
          <p className="text-sm text-muted mt-1">
            {total > 0
              ? `${cited}/${total} checks cited · probabilistic visibility across Perplexity, ChatGPT & Google AI`
              : "No audit data yet — run audit after GEO/AEO Tracker is up"}
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setAuditMsg(null);
            audit.mutate();
          }}
          disabled={audit.isPending}
          className="aeo-btn-primary shrink-0"
        >
          {audit.isPending ? "Running audit…" : "Run Citation Audit"}
        </button>
      </div>

      {auditMsg && (
        <div
          className={`text-sm px-4 py-3 rounded border ${
            auditMsg.type === "ok"
              ? "bg-success/10 border-success/25 text-success"
              : "bg-warning/10 border-warning/25 text-warning"
          }`}
        >
          {auditMsg.text}
        </div>
      )}

      <QueryStatus
        isLoading={loadingDashboard || isLoading}
        isError={listError}
        error={listErr}
        loadingText="Loading citation data…"
      >
        <>
          {dashboard && (
            <div className="grid lg:grid-cols-2 gap-6">
              <CitationBarChart
                data={dashboard.citation_by_brand}
                dataKey="brand_id"
                title="Citation Share by Brand"
              />
              <CitationBarChart
                data={dashboard.citation_by_category}
                dataKey="category"
                title="Citation Share by Category"
              />
              {dashboard.visibility_by_platform && dashboard.visibility_by_platform.length > 0 && (
                <CitationBarChart
                  data={dashboard.visibility_by_platform}
                  dataKey="platform"
                  title="Visibility by AI Platform"
                />
              )}
              {dashboard.citation_by_funnel && dashboard.citation_by_funnel.length > 0 && (
                <CitationBarChart
                  data={dashboard.citation_by_funnel}
                  dataKey="funnel_stage"
                  title="Citation Share by Funnel Stage"
                />
              )}
            </div>
          )}

          {gaps && <GapAnalysisTable gaps={gaps} />}

          <div className="aeo-panel overflow-hidden">
            <div className="px-5 py-4 border-b border-border">
              <h3 className="aeo-title text-ink">Latest Citation Results</h3>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted">
                  <th className="px-4 py-3">Query</th>
                  <th className="px-4 py-3">Brand</th>
                  <th className="px-4 py-3">Platform</th>
                  <th className="px-4 py-3">Visibility</th>
                  <th className="px-4 py-3">Mention / URL</th>
                  <th className="px-4 py-3">Competitor</th>
                </tr>
              </thead>
              <tbody>
                {!citations?.length ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-muted/80">
                      No citation results yet. Run an audit once GEO/AEO Tracker is running on port 3000.
                    </td>
                  </tr>
                ) : (
                  citations.slice(0, 50).map((c) => (
                    <tr key={c.id} className="border-t border-border">
                      <td className="px-4 py-3">{c.query}</td>
                      <td className="px-4 py-3 text-muted">{c.brand_id}</td>
                      <td className="px-4 py-3 text-muted">{c.platform}</td>
                      <td className="px-4 py-3">
                        {c.visibility_pct != null ? (
                          <span className={c.is_cited ? "text-success" : "text-warning"}>
                            {c.visibility_pct}%
                            {c.sample_runs && c.sample_runs > 1 ? ` (${c.sample_runs} runs)` : ""}
                          </span>
                        ) : c.is_cited ? (
                          <span className="text-success">✓</span>
                        ) : (
                          <span className="text-warning">✗</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs text-muted">
                        {c.is_mentioned ? "mention" : "—"}
                        {c.is_url_cited ? " · url" : ""}
                      </td>
                      <td className="px-4 py-3 text-muted">{c.competitor_cited || "—"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      </QueryStatus>
    </div>
  );
}
