import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { apiFetch } from "../lib/api";
import type { AdvisorImprovement, AdvisorReportPayload, AdvisorResponse } from "../types";

const PRIORITY_STYLE: Record<string, string> = {
  high: "bg-red-100 text-red-700",
  medium: "bg-yellow-100 text-yellow-800",
  low: "bg-gray-100 text-gray-600",
};

const PRIORITY_ORDER = ["high", "medium", "low"];

function fmtDate(iso: string | null): string {
  if (!iso) return "unknown";
  return new Date(iso.endsWith("Z") ? iso : iso + "Z").toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function ImprovementCard({ item }: { item: AdvisorImprovement }) {
  return (
    <div className="aeo-panel p-4">
      <div className="flex items-center gap-2 flex-wrap mb-1">
        <span
          className={`text-[11px] px-2 py-0.5 rounded font-medium ${
            PRIORITY_STYLE[item.priority?.toLowerCase()] ?? PRIORITY_STYLE.low
          }`}
        >
          {(item.priority || "").toUpperCase() || "ACTION"}
        </span>
        {item.category && (
          <span className="text-[11px] px-2 py-0.5 rounded bg-cyan/10 text-cyan">
            {item.category}
          </span>
        )}
        {item.brand_id && (
          <span className="text-[11px] px-2 py-0.5 rounded bg-void border border-border text-muted">
            {item.brand_id}
          </span>
        )}
        {item.effort && (
          <span className="text-[11px] px-2 py-0.5 rounded bg-void border border-border text-muted">
            effort: {item.effort}
          </span>
        )}
        <span className="font-medium text-ink">{item.title}</span>
      </div>
      <p className="text-sm text-muted">{item.why}</p>
    </div>
  );
}

export function AdvisorPage() {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const { data, isLoading, isFetching, isError, error, refetch } = useQuery({
    queryKey: ["advisor-latest"],
    queryFn: () => apiFetch<AdvisorResponse>("/api/advisor/latest"),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
  const { data: historyResp } = useQuery({
    queryKey: ["advisor-history"],
    queryFn: () => apiFetch<{ reports: AdvisorReportPayload[] }>("/api/advisor/history?limit=10"),
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });

  const regenerate = () =>
    apiFetch<AdvisorResponse>("/api/advisor/latest?refresh=1").then(() => {
      setSelectedId(null);
      refetch();
    });

  if (isLoading || (isFetching && !data)) {
    return (
      <div className="aeo-panel px-4 py-10 text-center text-muted">
        Analyzing platform data with AI… the first run takes ~30 seconds.
      </div>
    );
  }
  if (isError) {
    return (
      <div className="bg-warning/10 border border-warning/25 text-warning text-sm px-4 py-3 rounded">
        {(error as Error)?.message ?? "Failed to load the advisor report."}
      </div>
    );
  }
  if (!data || data.status === "no_data") {
    return (
      <div className="aeo-panel px-4 py-10 text-center text-muted/80">
        {data?.message ?? "Not enough data yet for the advisor to analyze."}
      </div>
    );
  }
  if (data.status === "error") {
    return (
      <div className="bg-warning/10 border border-warning/25 text-warning text-sm px-4 py-3 rounded flex items-center justify-between gap-4">
        <span>{data.message ?? "Generation failed."}</span>
        <button
          type="button"
          onClick={regenerate}
          className="px-3 py-1.5 border border-warning/40 rounded text-sm hover:border-warning"
        >
          Try again
        </button>
      </div>
    );
  }

  const history = historyResp?.reports ?? [];
  const report: AdvisorReportPayload | undefined =
    (selectedId != null && history.find((r) => r.id === selectedId)) || data.report;
  if (!report) return null;

  const improvements = report.improvements ?? [];
  const byPriority = PRIORITY_ORDER.map((p) => ({
    priority: p,
    items: improvements.filter((i) => (i.priority || "medium").toLowerCase() === p),
  })).filter((g) => g.items.length);
  const viewingOld = selectedId != null && selectedId !== data.report?.id;

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-xl font-bold text-ink">Improvement Advisor</h2>
          <p className="text-sm text-muted mt-1 max-w-2xl">
            AI analysis of the whole platform — KPIs, citations, posting cadence, pipeline
            health, and costs — turned into prioritized improvements with the data behind
            each one. Regenerates every Monday 7am, or on demand.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {history.length > 1 && (
            <select
              value={selectedId ?? data.report?.id ?? ""}
              onChange={(e) => setSelectedId(Number(e.target.value))}
              className="bg-panel border border-border rounded px-3 py-1.5 text-sm text-ink focus:outline-none focus:border-cyan/50"
              aria-label="Report history"
            >
              {history.map((r) => (
                <option key={r.id} value={r.id}>
                  {fmtDate(r.created_at)} ({r.trigger})
                </option>
              ))}
            </select>
          )}
          <button
            type="button"
            onClick={regenerate}
            disabled={isFetching}
            className="px-3 py-1.5 border border-border text-ink rounded text-sm hover:border-cyan disabled:opacity-50"
          >
            {isFetching ? "Regenerating…" : "Regenerate"}
          </button>
        </div>
      </div>

      {viewingOld && (
        <div className="bg-cyan/10 border border-cyan/25 text-cyan text-xs px-4 py-2 rounded">
          Viewing an older report from {fmtDate(report.created_at)} — pick the newest entry in
          the dropdown to return.
        </div>
      )}

      {report.summary && (
        <div className="aeo-panel border-l-2 border-l-cyan px-5 py-4">
          <p className="text-sm text-ink leading-relaxed">{report.summary}</p>
        </div>
      )}

      {!!report.quick_wins?.length && (
        <div className="aeo-panel p-4">
          <h3 className="text-sm font-semibold text-success mb-2">Quick wins this week</h3>
          <ul className="space-y-1.5">
            {report.quick_wins.map((w, i) => (
              <li key={i} className="text-sm text-muted flex gap-2">
                <span className="text-success">→</span>
                {w}
              </li>
            ))}
          </ul>
        </div>
      )}

      {byPriority.map((group) => (
        <div key={group.priority}>
          <h3 className="aeo-title text-ink mb-2 capitalize">{group.priority} priority</h3>
          <div className="space-y-2">
            {group.items.map((item, i) => (
              <ImprovementCard key={i} item={item} />
            ))}
          </div>
        </div>
      ))}

      <p className="text-[11px] text-muted/70">
        Report generated {fmtDate(report.created_at)} ({report.trigger}).{" "}
        {data.cached && !viewingOld ? "Loaded from history — Regenerate for a fresh analysis." : ""}
        {" "}AI analysis can be imperfect — verify before acting.
      </p>
    </div>
  );
}
