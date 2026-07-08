import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { CitationBarChart } from "../components/CitationBarChart";
import { Pagination, usePaged } from "../components/Pagination";
import { QueryStatus } from "../components/QueryStatus";
import { ReportTrendChart } from "../components/ReportTrendChart";
import { apiFetch } from "../lib/api";
import { downloadCsv } from "../lib/exportCsv";
import type {
  MonthlyReportDetail,
  ReportListItem,
  ReportsListResponse,
  ReportSummary,
} from "../types";

const TABLE_PAGE_SIZE = 8;

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
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

function KpiCard({
  label,
  value,
  sub,
  delta,
  deltaUnit = "",
}: {
  label: string;
  value: string | number;
  sub?: string;
  delta?: number;
  deltaUnit?: string;
}) {
  return (
    <div className="aeo-panel p-5">
      <p className="text-[10px] text-muted uppercase tracking-widest mb-2">{label}</p>
      <p className="aeo-kpi-value">{value}</p>
      {sub && <p className="text-xs text-muted mt-2">{sub}</p>}
      {delta !== undefined && delta !== 0 && (
        <p className={`text-xs mt-2 font-medium ${delta >= 0 ? "text-success" : "text-warning"}`}>
          {delta >= 0 ? "↑" : "↓"} {Math.abs(delta).toFixed(deltaUnit === "pts" ? 1 : 0)}
          {deltaUnit ? ` ${deltaUnit}` : ""} vs prev
        </p>
      )}
    </div>
  );
}

function SummaryPanel({ id, enabled }: { id: number; enabled: boolean }) {
  const { data, isFetching } = useQuery({
    queryKey: ["report-summary", id],
    queryFn: () => apiFetch<ReportSummary>(`/api/reports/${id}/summary`),
    enabled,
    staleTime: 10 * 60 * 1000,
    retry: 1,
  });

  if (isFetching && !data) {
    return (
      <div className="aeo-panel px-4 py-6 text-center text-muted text-sm">
        Writing the AI executive summary…
      </div>
    );
  }
  if (!data || data.status === "no_data" || !data.summary) {
    return null;
  }

  const List = ({ title, items, mark }: { title: string; items?: string[]; mark: string }) =>
    items && items.length ? (
      <div>
        <h4 className="text-xs font-semibold text-ink mb-1.5">{title}</h4>
        <ul className="space-y-1">
          {items.map((s, i) => (
            <li key={i} className="text-sm text-muted flex gap-2">
              <span>{mark}</span>
              {s}
            </li>
          ))}
        </ul>
      </div>
    ) : null;

  return (
    <div className="aeo-panel border-l-2 border-l-cyan p-5 space-y-4">
      <div>
        <h3 className="aeo-title text-ink mb-1">Executive summary</h3>
        <p className="text-sm text-ink leading-relaxed">{data.summary}</p>
      </div>
      <div className="grid md:grid-cols-3 gap-4">
        <List title="Highlights" items={data.highlights} mark="✓" />
        <List title="Watch-outs" items={data.watch_outs} mark="!" />
        <List title="Next steps" items={data.next_steps} mark="→" />
      </div>
    </div>
  );
}

export function ReportsPage() {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"report" | "trends">("report");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const {
    data: list,
    isLoading: loadingList,
    isError: listIsError,
    error: listError,
  } = useQuery({
    queryKey: ["reports-list"],
    queryFn: () => apiFetch<ReportsListResponse>("/api/reports?limit=60"),
    retry: 1,
  });

  const reports = list?.reports ?? [];
  const effectiveId = selectedId ?? reports[0]?.id ?? null;
  const selectedIndex = reports.findIndex((r) => r.id === effectiveId);
  const previous: ReportListItem | undefined =
    selectedIndex >= 0 ? reports[selectedIndex + 1] : undefined;

  const { data: report } = useQuery({
    queryKey: ["report", effectiveId],
    queryFn: () => apiFetch<MonthlyReportDetail>(`/api/reports/${effectiveId}`),
    enabled: effectiveId != null,
    retry: 1,
  });

  const generate = useMutation({
    mutationFn: () => apiFetch<MonthlyReportDetail>("/api/reports/generate", { method: "POST" }),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["reports-list"] });
      if (res?.id) {
        setSelectedId(res.id);
        queryClient.invalidateQueries({ queryKey: ["report", res.id] });
        queryClient.invalidateQueries({ queryKey: ["report-summary", res.id] });
      }
    },
  });

  const full = report?.full_report_json ?? {};
  const brandRows = report?.brand_breakdown ? Object.values(report.brand_breakdown) : [];
  const topQueries = usePaged(report?.top_performing_queries ?? [], TABLE_PAGE_SIZE);
  const gapQueries = usePaged(report?.gap_queries ?? [], TABLE_PAGE_SIZE);

  const exportCsv = () => {
    if (!report) return;
    const rows: (string | number | null | undefined)[][] = [
      ["Axxiom AEO Report", report.report_month ?? ""],
      [],
      ["Metric", "Value"],
      ["Citation share %", report.overall_citation_share ?? 0],
      ["AI-referred sessions", report.ai_referred_sessions ?? 0],
      ["Content published", report.content_pieces_published ?? 0],
      ["Schema coverage %", report.schema_coverage_pct ?? 0],
      [],
      ["Top performing queries"],
      ["Query", "Brand", "Platform"],
      ...(report.top_performing_queries ?? []).map((q) => [q.query, q.brand_id, q.platform]),
      [],
      ["Gap queries (competitor cited)"],
      ["Query", "Brand", "Competitor", "Platform"],
      ...(report.gap_queries ?? []).map((g) => [g.query, g.brand_id, g.competitor_cited, g.platform]),
    ];
    downloadCsv(`aeo-report-${report.report_month ?? "latest"}.csv`, rows);
  };

  const isEmpty = !loadingList && reports.length === 0;

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4 print:hidden">
        <div>
          <h2 className="text-xl font-bold text-ink">Reports</h2>
          <p className="text-sm text-muted mt-1 max-w-2xl">
            Monthly AEO snapshots — citation share, AI traffic, content output, and gaps — with
            month-over-month trends. Auto-generated on the last day of each month; generate one
            anytime.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {reports.length > 0 && (
            <select
              value={effectiveId ?? ""}
              onChange={(e) => setSelectedId(Number(e.target.value))}
              className="aeo-input w-auto"
              aria-label="Select report period"
            >
              {reports.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.report_month ?? `Report #${r.id}`}
                </option>
              ))}
            </select>
          )}
          <button
            type="button"
            onClick={() => generate.mutate()}
            disabled={generate.isPending}
            className="aeo-btn-primary"
          >
            {generate.isPending ? "Generating…" : "Generate report"}
          </button>
          {report && tab === "report" && (
            <>
              <button type="button" onClick={exportCsv} className="aeo-btn-secondary">
                Export CSV
              </button>
              <button type="button" onClick={() => window.print()} className="aeo-btn-secondary">
                Print / PDF
              </button>
            </>
          )}
        </div>
      </div>

      {generate.isError && (
        <div className="bg-warning/10 border border-warning/30 text-warning text-sm px-4 py-3 rounded print:hidden">
          {(generate.error as Error).message}
        </div>
      )}

      <QueryStatus
        isLoading={loadingList}
        isError={listIsError}
        error={listError as Error | null}
        loadingText="Loading reports…"
      >
        {isEmpty ? (
          <div className="aeo-panel p-8 space-y-3">
            <p className="text-muted">No reports yet.</p>
            <p className="text-sm text-muted">
              Reports are created automatically on the last day of each month. Click{" "}
              <strong>Generate report</strong> to snapshot the current KPIs now — once citation
              audits have run and content is publishing, the numbers fill in.
            </p>
          </div>
        ) : (
          <>
            <div className="flex gap-1 border-b border-border print:hidden">
              <TabButton active={tab === "report"} onClick={() => setTab("report")}>
                Report
              </TabButton>
              <TabButton active={tab === "trends"} onClick={() => setTab("trends")}>
                Trends
              </TabButton>
            </div>

            {tab === "trends" ? (
              <div className="space-y-5">
                <ReportTrendChart reports={reports} />
                <div className="aeo-panel overflow-hidden">
                  <div className="px-5 py-4 border-b border-border">
                    <h3 className="aeo-title text-ink">Report history</h3>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-border text-left text-muted">
                          <th className="px-4 py-3">Month</th>
                          <th className="px-4 py-3">Citation share</th>
                          <th className="px-4 py-3">AI sessions</th>
                          <th className="px-4 py-3">Content</th>
                          <th className="px-4 py-3">Schema</th>
                          <th className="px-4 py-3 text-right">Open</th>
                        </tr>
                      </thead>
                      <tbody>
                        {reports.map((r) => (
                          <tr key={r.id} className="border-t border-border">
                            <td className="px-4 py-3">{r.report_month ?? `#${r.id}`}</td>
                            <td className="px-4 py-3">{r.overall_citation_share}%</td>
                            <td className="px-4 py-3 text-muted">{r.ai_referred_sessions ?? 0}</td>
                            <td className="px-4 py-3 text-muted">{r.content_pieces_published ?? 0}</td>
                            <td className="px-4 py-3 text-muted">{r.schema_coverage_pct}%</td>
                            <td className="px-4 py-3 text-right">
                              <button
                                type="button"
                                onClick={() => {
                                  setSelectedId(r.id);
                                  setTab("report");
                                }}
                                className="text-xs text-ink hover:text-cyan font-medium"
                              >
                                View →
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            ) : (
              <div id="report" className="space-y-5">
                <div className="border-b border-border pb-4">
                  <h1 className="text-2xl font-bold text-ink">Axxiom AEO Report</h1>
                  <p className="text-sm text-muted mt-1">
                    {report?.report_month ? `Period: ${report.report_month}` : ""}
                    {report?.created_at
                      ? ` · Generated ${new Date(report.created_at).toLocaleDateString()}`
                      : ""}
                  </p>
                </div>

                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <KpiCard
                    label="Citation Share"
                    value={`${report?.overall_citation_share ?? 0}%`}
                    sub="AI answers citing us"
                    delta={
                      previous
                        ? (report?.overall_citation_share ?? 0) - previous.overall_citation_share
                        : undefined
                    }
                    deltaUnit="pts"
                  />
                  <KpiCard
                    label="AI-Referred Sessions"
                    value={report?.ai_referred_sessions ?? 0}
                    sub="Traffic from AI assistants"
                    delta={
                      previous
                        ? (report?.ai_referred_sessions ?? 0) - (previous.ai_referred_sessions ?? 0)
                        : undefined
                    }
                  />
                  <KpiCard
                    label="Content Published"
                    value={report?.content_pieces_published ?? 0}
                    sub="Posts this period"
                    delta={
                      previous
                        ? (report?.content_pieces_published ?? 0) -
                          (previous.content_pieces_published ?? 0)
                        : undefined
                    }
                  />
                  <KpiCard
                    label="Schema Coverage"
                    value={`${report?.schema_coverage_pct ?? 0}%`}
                    sub="Valid structured data"
                    delta={
                      previous
                        ? (report?.schema_coverage_pct ?? 0) - previous.schema_coverage_pct
                        : undefined
                    }
                    deltaUnit="pts"
                  />
                </div>

                {effectiveId != null && (
                  <SummaryPanel id={effectiveId} enabled={tab === "report"} />
                )}

                {(brandRows.length > 0 || (full.by_category?.length ?? 0) > 0) && (
                  <div className="grid lg:grid-cols-2 gap-6">
                    {brandRows.length > 0 && (
                      <CitationBarChart
                        data={brandRows.map((b) => ({
                          brand_id: b.brand_id,
                          citation_share: b.citation_share ?? 0,
                        }))}
                        dataKey="brand_id"
                        title="Citation Share by Brand"
                      />
                    )}
                    {full.by_category && full.by_category.length > 0 && (
                      <CitationBarChart
                        data={full.by_category}
                        dataKey="category"
                        title="Citation Share by Category"
                      />
                    )}
                  </div>
                )}

                <div className="grid lg:grid-cols-2 gap-6">
                  <div className="aeo-panel overflow-hidden">
                    <div className="px-5 py-4 border-b border-border">
                      <h3 className="aeo-title text-ink">Top Performing Queries</h3>
                      <p className="text-xs text-muted mt-0.5">Where we already win AI citations.</p>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-border text-left text-muted">
                            <th className="px-4 py-3">Query</th>
                            <th className="px-4 py-3">Brand</th>
                            <th className="px-4 py-3">Platform</th>
                          </tr>
                        </thead>
                        <tbody>
                          {topQueries.slice.length === 0 ? (
                            <tr>
                              <td colSpan={3} className="px-4 py-6 text-center text-muted/80">
                                No cited queries recorded in this report.
                              </td>
                            </tr>
                          ) : (
                            topQueries.slice.map((q, i) => (
                              <tr key={i} className="border-t border-border">
                                <td className="px-4 py-3">{q.query}</td>
                                <td className="px-4 py-3 text-muted">{q.brand_id ?? "—"}</td>
                                <td className="px-4 py-3 text-muted">{q.platform ?? "—"}</td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </div>
                    <Pagination
                      page={topQueries.page}
                      pageSize={TABLE_PAGE_SIZE}
                      total={topQueries.total}
                      onPage={topQueries.setPage}
                      label="queries"
                    />
                  </div>

                  <div className="aeo-panel overflow-hidden">
                    <div className="px-5 py-4 border-b border-border">
                      <h3 className="aeo-title text-ink">Top Gap Queries</h3>
                      <p className="text-xs text-muted mt-0.5">Where competitors win instead of us.</p>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-border text-left text-muted">
                            <th className="px-4 py-3">Query</th>
                            <th className="px-4 py-3">Brand</th>
                            <th className="px-4 py-3">Competitor</th>
                          </tr>
                        </thead>
                        <tbody>
                          {gapQueries.slice.length === 0 ? (
                            <tr>
                              <td colSpan={3} className="px-4 py-6 text-center text-muted/80">
                                No gaps recorded in this report.
                              </td>
                            </tr>
                          ) : (
                            gapQueries.slice.map((g, i) => (
                              <tr key={i} className="border-t border-border">
                                <td className="px-4 py-3">{g.query}</td>
                                <td className="px-4 py-3 text-muted">{g.brand_id ?? "—"}</td>
                                <td className="px-4 py-3 text-warning text-xs">
                                  {g.competitor_cited ?? "—"}
                                </td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </div>
                    <Pagination
                      page={gapQueries.page}
                      pageSize={TABLE_PAGE_SIZE}
                      total={gapQueries.total}
                      onPage={gapQueries.setPage}
                      label="gaps"
                    />
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </QueryStatus>
    </div>
  );
}
