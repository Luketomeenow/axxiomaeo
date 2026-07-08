import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { CitationBarChart } from "../components/CitationBarChart";
import { CitationInsightsPanel } from "../components/CitationInsightsPanel";
import { GapAnalysisTable } from "../components/GapAnalysisTable";
import { Pagination, usePaged } from "../components/Pagination";
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

const RESULTS_PAGE_SIZE = 10;

const GLOSSARY: { term: string; def: string }[] = [
  { term: "Citation share", def: "Share of AI answers that cite the brand (higher is better)." },
  { term: "Visibility", def: "How often the brand shows up for a query across sampled runs — the answers vary, so this is probabilistic." },
  { term: "Share of voice", def: "Brand citations vs. competitor citations on the same queries." },
  { term: "Gap", def: "A query where the brand isn't cited — often a competitor is cited instead. These feed the Recommendations inbox." },
  { term: "Mention / URL", def: "“mention” = the brand is named in the answer text; “url” = the brand's website is linked as a source." },
  { term: "Funnel stage", def: "Where the query sits in the buyer journey (awareness → consideration → decision)." },
];

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
        active ? "border-cyan text-cyan" : "border-transparent text-muted hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}

export function CitationsPage() {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"monitoring" | "insights">("monitoring");
  const [auditMsg, setAuditMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  const audit = useMutation({
    mutationFn: () => apiFetch<AuditResponse>("/api/citations/audit", { method: "POST" }),
    onSuccess: (data) => {
      if (data.status === "audit_started") {
        setAuditMsg({
          type: "ok",
          text: "Citation audit started in the background. Results will appear here in a few minutes (it polls each AI engine).",
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
            "Citation provider unavailable — check CITATION_PROVIDER and its API key in your backend environment.",
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

  const { page, setPage, slice: pagedCitations } = usePaged(citations ?? [], RESULTS_PAGE_SIZE);

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-ink">Citation Monitoring</h2>
          <p className="text-sm text-muted mt-1 max-w-2xl">
            Tracks whether AI answer engines (ChatGPT, Gemini, Perplexity) cite your brands when
            people ask elevator questions.{" "}
            {total > 0
              ? `Latest audit: ${cited}/${total} checks cited.`
              : "No audit data yet — click Run Citation Audit to collect it."}
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

      <div className="flex gap-1 border-b border-border">
        <TabButton active={tab === "monitoring"} onClick={() => setTab("monitoring")}>
          Monitoring
        </TabButton>
        <TabButton active={tab === "insights"} onClick={() => setTab("insights")}>
          AI Recommendations
        </TabButton>
      </div>

      {tab === "insights" ? (
        <CitationInsightsPanel enabled={tab === "insights"} />
      ) : (
        <QueryStatus
          isLoading={loadingDashboard || isLoading}
          isError={listError}
          error={listErr}
          loadingText="Loading citation data…"
        >
          <div className="space-y-5">
            <details className="aeo-panel px-4 py-3 text-sm">
              <summary className="cursor-pointer text-muted hover:text-ink select-none">
                What do these metrics mean?
              </summary>
              <dl className="mt-3 grid sm:grid-cols-2 gap-x-6 gap-y-2">
                {GLOSSARY.map((g) => (
                  <div key={g.term} className="text-xs">
                    <dt className="font-semibold text-ink inline">{g.term}: </dt>
                    <dd className="text-muted inline">{g.def}</dd>
                  </div>
                ))}
              </dl>
            </details>

            {dashboard && (
              <div>
                <p className="text-xs text-muted mb-2">
                  Share of AI answers citing the brand, broken down four ways. Taller bars = more
                  citations won.
                </p>
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
              </div>
            )}

            {gaps && <GapAnalysisTable gaps={gaps} />}

            <div className="aeo-panel overflow-hidden">
              <div className="px-5 py-4 border-b border-border">
                <h3 className="aeo-title text-ink">Latest Citation Results</h3>
                <p className="text-xs text-muted mt-0.5">
                  Every query checked in the latest audit, one row per AI engine — whether the brand
                  was cited, its visibility, and any competitor cited instead.
                </p>
              </div>
              <div className="overflow-x-auto">
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
                          No citation results yet — click Run Citation Audit above. If it reports the
                          provider is unavailable, set CITATION_PROVIDER and its API key, then retry.
                        </td>
                      </tr>
                    ) : (
                      pagedCitations.map((c) => (
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
              <Pagination
                page={page}
                pageSize={RESULTS_PAGE_SIZE}
                total={citations?.length ?? 0}
                onPage={setPage}
                label="checks"
              />
            </div>
          </div>
        </QueryStatus>
      )}
    </div>
  );
}
