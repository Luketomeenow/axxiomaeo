import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../lib/api";
import type { Recommendation, RecommendationsResponse } from "../types";

const CONTENT_TYPE_LABEL: Record<string, string> = {
  faq_hub: "FAQ Hub",
  local_page: "Local Page",
  vertical_page: "Vertical Page",
  comparison: "Comparison",
  data_stats: "Data & Statistics",
};

function priorityBadge(priority: number) {
  if (priority === 1) return { label: "CRITICAL", className: "bg-red-100 text-red-700" };
  if (priority === 3) return { label: "HIGH", className: "bg-yellow-100 text-yellow-800" };
  return { label: "MEDIUM", className: "bg-gray-100 text-gray-600" };
}

export function RecommendationsPage() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [pendingKey, setPendingKey] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["recommendations"],
    queryFn: () => apiFetch<RecommendationsResponse>("/api/recommendations"),
    refetchInterval: 60000,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["recommendations"] });

  const approve = useMutation({
    mutationFn: (key: string) =>
      apiFetch<{ queue_id: number }>(`/api/recommendations/${encodeURIComponent(key)}/approve`, {
        method: "POST",
      }),
    onMutate: (key) => setPendingKey(key),
    onSettled: () => setPendingKey(null),
    onSuccess: () => {
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["content-queue"] });
      // The draft is generating — hand off to Content Review, which live-polls
      // generating drafts and is where it gets approved for publish. The row is
      // created by a background task moments after this response, so refetch
      // again shortly after landing or the page idles 30s before showing it.
      queryClient.invalidateQueries({ queryKey: ["drafts"] });
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ["drafts"] }), 4000);
      navigate("/content/review");
    },
  });

  const dismiss = useMutation({
    mutationFn: (key: string) =>
      apiFetch(`/api/recommendations/${encodeURIComponent(key)}/dismiss`, { method: "POST" }),
    onMutate: (key) => setPendingKey(key),
    onSettled: () => setPendingKey(null),
    onSuccess: () => invalidate(),
  });

  const recs = data?.recommendations ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-ink">Recommendations</h2>
          <p className="text-sm text-muted mt-0.5">
            Ranked from live AI-citation gaps. Approve to generate a draft — it lands in Content
            Review for your sign-off before anything publishes.
          </p>
        </div>
      </div>

      {(approve.isError || dismiss.isError) && (
        <div className="bg-warning/10 border border-warning/30 text-warning text-sm px-4 py-3 rounded">
          {((approve.error || dismiss.error) as Error | null)?.message ?? "Action failed"}
        </div>
      )}

      {isLoading ? (
        <div className="aeo-panel px-4 py-8 text-center text-muted/80">Loading…</div>
      ) : !recs.length ? (
        <div className="aeo-panel px-4 py-10 text-center text-muted/80">
          No open recommendations — every current citation gap is already queued, drafted, or
          published. New gaps appear here after the next citation audit.
        </div>
      ) : (
        <div className="space-y-3">
          {recs.map((rec: Recommendation) => {
            const badge = priorityBadge(rec.priority);
            const busy = pendingKey === rec.key && (approve.isPending || dismiss.isPending);
            return (
              <div key={rec.key} className="aeo-panel p-4 flex items-start justify-between gap-4">
                <div className="min-w-0 space-y-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`text-xs px-2 py-0.5 rounded font-medium ${badge.className}`}>
                      {badge.label}
                    </span>
                    <span className="text-xs text-muted">{rec.brand_name}</span>
                    <span className="text-xs text-muted/70">
                      · {CONTENT_TYPE_LABEL[rec.content_type] ?? rec.content_type}
                    </span>
                  </div>
                  <p className="font-medium text-ink">{rec.title || rec.query}</p>
                  <p className="text-sm text-muted">{rec.why}</p>
                  <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
                    {rec.engines_missing.map((engine) => (
                      <span
                        key={engine}
                        className="text-[11px] px-1.5 py-0.5 rounded bg-red-100 text-red-700"
                        title="Brand not cited on this engine for the query"
                      >
                        {engine}
                      </span>
                    ))}
                    {(rec.competitors?.length
                      ? rec.competitors
                      : rec.competitor_cited
                        ? ["competitor cited"]
                        : []
                    )
                      .slice(0, 2)
                      .map((name) => (
                        <span
                          key={name}
                          className="text-[11px] px-1.5 py-0.5 rounded bg-orange-100 text-orange-700"
                          title="Cited for this query instead of the brand"
                        >
                          vs {name}
                        </span>
                      ))}
                  </div>
                </div>
                <div className="flex flex-col items-end gap-2 shrink-0">
                  <button
                    type="button"
                    onClick={() => approve.mutate(rec.key)}
                    disabled={busy}
                    className="px-4 py-1.5 bg-cyan text-void rounded text-sm font-medium hover:bg-cyan/90 disabled:opacity-50"
                  >
                    {pendingKey === rec.key && approve.isPending ? "Approving…" : "Approve"}
                  </button>
                  <button
                    type="button"
                    onClick={() => dismiss.mutate(rec.key)}
                    disabled={busy}
                    className="px-4 py-1.5 border border-border text-muted rounded text-sm hover:border-warning hover:text-warning disabled:opacity-50"
                  >
                    {pendingKey === rec.key && dismiss.isPending ? "Dismissing…" : "Dismiss"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
