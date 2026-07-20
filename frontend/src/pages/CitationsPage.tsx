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
  audit_run_id?: string | null;
  checked_at: string;
}

interface AuditRun {
  audit_run_id: string;
  started_at: string | null;
  finished_at: string | null;
  total_checks: number;
  cited_checks: number;
}

interface RecordsResponse {
  records: CitationRecord[];
  total: number;
  truncated: boolean;
}

interface AuditResponse {
  status: string;
  message?: string;
}

const RESULTS_PAGE_SIZE = 10;

function fmtDay(iso: string | null): string {
  if (!iso) return "unknown date";
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

/** Citation share per distinct value of `pick`, sorted best-first. */
function shareBy(
  records: CitationRecord[],
  pick: (r: CitationRecord) => string | null | undefined
): { label: string; citation_share: number }[] {
  const acc = new Map<string, { total: number; cited: number }>();
  for (const r of records) {
    const key = (pick(r) || "").trim();
    if (!key) continue;
    const cur = acc.get(key) ?? { total: 0, cited: 0 };
    cur.total += 1;
    if (r.is_cited) cur.cited += 1;
    acc.set(key, cur);
  }
  return [...acc.entries()]
    .map(([label, v]) => ({
      label,
      citation_share: Math.round((v.cited / v.total) * 1000) / 10,
    }))
    .sort((a, b) => b.citation_share - a.citation_share);
}

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

  // Audit scope: "latest" | "all" | "range" | "run:<audit_run_id>"
  const [scope, setScope] = useState("latest");
  const [rangeStart, setRangeStart] = useState("");
  const [rangeEnd, setRangeEnd] = useState("");

  const { data: runs } = useQuery({
    queryKey: ["citation-runs"],
    queryFn: () => apiFetch<AuditRun[]>("/api/citations/runs"),
    retry: 1,
  });

  const latestRunId = runs?.[0]?.audit_run_id ?? null;
  const params = new URLSearchParams();
  if (scope === "latest" && latestRunId) params.set("run_id", latestRunId);
  else if (scope.startsWith("run:")) params.set("run_id", scope.slice(4));
  else if (scope === "range") {
    if (rangeStart) params.set("start", rangeStart);
    if (rangeEnd) params.set("end", rangeEnd);
  }

  const {
    data: recordsResp,
    isLoading,
    isError: citationsError,
    error: citationsErr,
  } = useQuery({
    queryKey: ["citations", scope, rangeStart, rangeEnd, latestRunId],
    queryFn: () =>
      apiFetch<RecordsResponse>(
        `/api/citations/records${params.toString() ? `?${params.toString()}` : ""}`
      ),
    // For "latest" wait for the runs list so the query filters by the newest
    // run id instead of falling back to full history.
    enabled: scope !== "latest" || runs !== undefined,
    refetchInterval: 60000,
    retry: 1,
  });
  const citations = recordsResp?.records;

  const { data: gaps } = useQuery({
    queryKey: ["gaps"],
    queryFn: () => apiFetch<DashboardData["gap_queries"]>("/api/citations/gaps"),
    retry: 1,
  });

  const cited = citations?.filter((c) => c.is_cited).length ?? 0;
  const total = citations?.length ?? 0;
  const listError = citationsError;
  const listErr = citationsErr as Error | null;

  const scopeLabel =
    scope === "all"
      ? "All audits"
      : scope === "range"
        ? "Selected range"
        : scope.startsWith("run:")
          ? `Audit of ${fmtDay(
              runs?.find((r) => r.audit_run_id === scope.slice(4))?.finished_at ?? null
            )}`
          : "Latest audit";

  const byBrand = shareBy(citations ?? [], (r) => r.brand_id);
  const byCategory = shareBy(citations ?? [], (r) => r.query_category);
  const byPlatform = shareBy(citations ?? [], (r) => r.platform);
  const byFunnel = shareBy(citations ?? [], (r) => r.funnel_stage);

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
              ? `${scopeLabel}: ${cited}/${total} checks cited.`
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
          isLoading={isLoading}
          isError={listError}
          error={listErr}
          loadingText="Loading citation data…"
        >
          <div className="space-y-5">
            <div className="aeo-panel p-4 flex flex-wrap items-end gap-3">
              <div>
                <label className="block text-xs font-medium text-muted mb-1">Audit scope</label>
                <select
                  value={scope}
                  onChange={(e) => setScope(e.target.value)}
                  className="bg-panel border border-border rounded-md px-3 py-2 text-sm text-ink focus:outline-none focus:border-cyan/50"
                  aria-label="Audit scope"
                >
                  <option value="latest">
                    Latest audit{runs?.[0] ? ` — ${fmtDay(runs[0].finished_at)}` : ""}
                  </option>
                  <option value="all">All history</option>
                  <option value="range">Custom date range…</option>
                  {runs && runs.length > 0 && (
                    <optgroup label="Past audits">
                      {runs.map((r) => (
                        <option key={r.audit_run_id} value={`run:${r.audit_run_id}`}>
                          {fmtDay(r.finished_at)} · {r.total_checks} checks ·{" "}
                          {r.total_checks
                            ? Math.round((r.cited_checks / r.total_checks) * 100)
                            : 0}
                          % cited
                        </option>
                      ))}
                    </optgroup>
                  )}
                </select>
              </div>
              {scope === "range" && (
                <>
                  <div>
                    <label className="block text-xs font-medium text-muted mb-1">From</label>
                    <input
                      type="date"
                      value={rangeStart}
                      onChange={(e) => setRangeStart(e.target.value)}
                      className="bg-panel border border-border rounded-md px-3 py-1.5 text-sm text-ink focus:outline-none focus:border-cyan/50"
                      aria-label="Range start date"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-muted mb-1">To</label>
                    <input
                      type="date"
                      value={rangeEnd}
                      onChange={(e) => setRangeEnd(e.target.value)}
                      className="bg-panel border border-border rounded-md px-3 py-1.5 text-sm text-ink focus:outline-none focus:border-cyan/50"
                      aria-label="Range end date"
                    />
                  </div>
                </>
              )}
              <p className="text-sm text-muted ml-auto pb-1.5">
                {total > 0 ? (
                  <>
                    <span className="text-ink font-medium">{total.toLocaleString()}</span> checks ·{" "}
                    <span className="text-success font-medium">{cited.toLocaleString()}</span> cited (
                    {Math.round((cited / total) * 100)}%)
                    {recordsResp?.truncated
                      ? ` · showing newest ${citations?.length.toLocaleString()} of ${recordsResp.total.toLocaleString()}`
                      : ""}
                  </>
                ) : (
                  "No checks in this scope"
                )}
              </p>
            </div>

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

            {byBrand.length > 0 && (
              <div>
                <p className="text-xs text-muted mb-2">
                  Share of AI answers citing the brand within the selected scope, broken down four
                  ways. Taller bars = more citations won.
                </p>
                <div className="grid lg:grid-cols-2 gap-6">
                  <CitationBarChart
                    data={byBrand}
                    dataKey="label"
                    title={`Citation Share by Brand — ${scopeLabel}`}
                  />
                  {byCategory.length > 0 && (
                    <CitationBarChart
                      data={byCategory}
                      dataKey="label"
                      title={`Citation Share by Category — ${scopeLabel}`}
                    />
                  )}
                  {byPlatform.length > 0 && (
                    <CitationBarChart
                      data={byPlatform}
                      dataKey="label"
                      title={`Citation Share by AI Platform — ${scopeLabel}`}
                    />
                  )}
                  {byFunnel.length > 0 && (
                    <CitationBarChart
                      data={byFunnel}
                      dataKey="label"
                      title={`Citation Share by Funnel Stage — ${scopeLabel}`}
                    />
                  )}
                </div>
              </div>
            )}

            {gaps && (
              <div>
                <p className="text-xs text-muted mb-2">
                  Gap analysis always reflects the <strong>latest</strong> audit — it feeds the
                  Recommendations inbox regardless of the scope selected above.
                </p>
                <GapAnalysisTable gaps={gaps} />
              </div>
            )}

            <div className="aeo-panel overflow-hidden">
              <div className="px-5 py-4 border-b border-border">
                <h3 className="aeo-title text-ink">Citation Results — {scopeLabel}</h3>
                <p className="text-xs text-muted mt-0.5">
                  Every check in the selected scope, one row per query × AI engine — whether the
                  brand was cited, its visibility, and any competitor cited instead.
                  {scope === "all" || scope === "range" ? " Newest first." : ""}
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
                      <th className="px-4 py-3">Checked</th>
                    </tr>
                  </thead>
                  <tbody>
                    {!citations?.length ? (
                      <tr>
                        <td colSpan={7} className="px-4 py-8 text-center text-muted/80">
                          {scope === "range"
                            ? "No checks in this date range — widen the range or pick an audit from the dropdown."
                            : "No citation results yet — click Run Citation Audit above. If it reports the provider is unavailable, set CITATION_PROVIDER and its API key, then retry."}
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
                          <td className="px-4 py-3 text-muted text-xs whitespace-nowrap">
                            {c.checked_at ? fmtDay(c.checked_at) : "—"}
                          </td>
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
