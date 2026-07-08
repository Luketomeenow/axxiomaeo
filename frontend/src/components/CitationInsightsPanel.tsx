import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../lib/api";
import type { CitationInsights } from "../types";

const PRIORITY_STYLE: Record<string, string> = {
  high: "bg-red-100 text-red-700",
  medium: "bg-yellow-100 text-yellow-800",
  low: "bg-gray-100 text-gray-600",
};

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="aeo-panel px-4 py-3">
      <p className="text-[10px] uppercase tracking-wider text-muted">{label}</p>
      <p className="text-lg font-bold text-ink mt-0.5">{value}</p>
    </div>
  );
}

export function CitationInsightsPanel({ enabled }: { enabled: boolean }) {
  const { data, isLoading, isFetching, isError, error, refetch } = useQuery({
    queryKey: ["citation-insights"],
    queryFn: () => apiFetch<CitationInsights>("/api/citations/insights"),
    enabled,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });

  const regenerate = () =>
    apiFetch<CitationInsights>("/api/citations/insights?refresh=1").then(() => refetch());

  if (isLoading || (isFetching && !data)) {
    return (
      <div className="aeo-panel px-4 py-10 text-center text-muted">
        Analyzing your latest citation audit with AI… this takes a few seconds.
      </div>
    );
  }

  if (isError) {
    return (
      <div className="bg-warning/10 border border-warning/25 text-warning text-sm px-4 py-3 rounded">
        {(error as Error)?.message ?? "Failed to load AI recommendations."}
      </div>
    );
  }

  if (!data || data.status === "no_data") {
    return (
      <div className="aeo-panel px-4 py-10 text-center text-muted/80">
        {data?.message ??
          "No citation data yet. Run a citation audit first, then AI recommendations will appear here."}
      </div>
    );
  }

  const ds = data.data_summary;

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <p className="text-sm text-muted max-w-3xl">
          Claude analyzed your latest citation audit and grouped what it found into strengths, risks,
          per-engine patterns, and prioritized actions. Use this as the &ldquo;what should we do next&rdquo;
          read of the numbers on the Monitoring tab.
        </p>
        <button
          type="button"
          onClick={regenerate}
          disabled={isFetching}
          className="shrink-0 px-3 py-1.5 border border-border text-ink rounded text-sm hover:border-cyan disabled:opacity-50"
        >
          {isFetching ? "Regenerating…" : "Regenerate"}
        </button>
      </div>

      {ds && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <Stat label="Citation share" value={`${ds.citation_share_pct}%`} />
          <Stat label="Avg visibility" value={`${ds.avg_visibility_pct}%`} />
          <Stat label="Checks (latest audit)" value={`${ds.cited}/${ds.total_checks} cited`} />
          <Stat
            label="Top competitor"
            value={ds.top_competitors?.[0] ? ds.top_competitors[0].name : "—"}
          />
        </div>
      )}

      {data.summary && (
        <div className="aeo-panel border-l-2 border-l-cyan px-5 py-4">
          <p className="text-sm text-ink leading-relaxed">{data.summary}</p>
        </div>
      )}

      {!!data.recommendations?.length && (
        <div>
          <h3 className="aeo-title text-ink mb-2">Recommended actions</h3>
          <div className="space-y-2">
            {data.recommendations.map((r, i) => (
              <div key={i} className="aeo-panel p-4">
                <div className="flex items-center gap-2 flex-wrap mb-1">
                  <span
                    className={`text-[11px] px-2 py-0.5 rounded font-medium ${
                      PRIORITY_STYLE[r.priority?.toLowerCase()] ?? PRIORITY_STYLE.low
                    }`}
                  >
                    {(r.priority || "").toUpperCase() || "ACTION"}
                  </span>
                  {r.category && (
                    <span className="text-[11px] px-2 py-0.5 rounded bg-cyan/10 text-cyan">
                      {r.category}
                    </span>
                  )}
                  <span className="font-medium text-ink">{r.title}</span>
                </div>
                <p className="text-sm text-muted">{r.detail}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-4">
        {!!data.strengths?.length && (
          <div className="aeo-panel p-4">
            <h4 className="text-sm font-semibold text-success mb-2">What's working</h4>
            <ul className="space-y-1.5">
              {data.strengths.map((s, i) => (
                <li key={i} className="text-sm text-muted flex gap-2">
                  <span className="text-success">+</span>
                  {s}
                </li>
              ))}
            </ul>
          </div>
        )}
        {!!data.weaknesses?.length && (
          <div className="aeo-panel p-4">
            <h4 className="text-sm font-semibold text-warning mb-2">Gaps &amp; risks</h4>
            <ul className="space-y-1.5">
              {data.weaknesses.map((w, i) => (
                <li key={i} className="text-sm text-muted flex gap-2">
                  <span className="text-warning">!</span>
                  {w}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {!!data.platform_insights?.length && (
        <div className="aeo-panel p-4">
          <h4 className="text-sm font-semibold text-ink mb-2">By AI engine</h4>
          <div className="space-y-2">
            {data.platform_insights.map((p, i) => (
              <div key={i} className="text-sm">
                <span className="font-medium text-ink">{p.platform}:</span>{" "}
                <span className="text-muted">{p.insight}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {!!data.competitor_threats?.length && (
        <div className="aeo-panel p-4">
          <h4 className="text-sm font-semibold text-ink mb-2">Competitor threats</h4>
          <div className="space-y-2">
            {data.competitor_threats.map((c, i) => (
              <div key={i} className="text-sm">
                <span className="font-medium text-orange-700">{c.competitor}:</span>{" "}
                <span className="text-muted">{c.detail}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <p className="text-[11px] text-muted/70">
        {data.cached ? "Cached from the last analysis of this audit." : "Freshly generated."} AI
        analysis can be imperfect — verify before acting.
      </p>
    </div>
  );
}
