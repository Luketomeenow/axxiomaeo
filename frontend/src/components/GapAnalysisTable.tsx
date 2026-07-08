import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { DashboardData } from "../types";
import { apiFetch } from "../lib/api";
import { Pagination, usePaged } from "./Pagination";

const PAGE_SIZE = 8;

const PRIORITY_ORDER: Record<string, number> = {
  emergency: 1,
  research_evaluation: 2,
  compliance_regulatory: 3,
  vertical_specific: 4,
};

const CONTENT_TYPE_BY_CATEGORY: Record<string, string> = {
  emergency: "faq_hub",
  research_evaluation: "faq_hub",
  compliance_regulatory: "data_stats",
  vertical_specific: "vertical_page",
  comparison_decision: "comparison",
  data_statistics: "data_stats",
  custom: "faq_hub",
};

export function GapAnalysisTable({ gaps }: { gaps: DashboardData["gap_queries"] }) {
  const queryClient = useQueryClient();
  const [queued, setQueued] = useState<string | null>(null);

  const addToQueue = useMutation({
    mutationFn: (gap: DashboardData["gap_queries"][0]) =>
      apiFetch("/api/content/queue/from-gap", {
        method: "POST",
        body: JSON.stringify({
          brand_id: gap.brand_id,
          target_query: gap.query,
          content_type:
            gap.recommended_content_type ||
            CONTENT_TYPE_BY_CATEGORY[gap.category] ||
            "faq_hub",
          title: gap.query,
          priority: PRIORITY_ORDER[gap.category] ?? 3,
          citation_record_id: gap.id ?? null,
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["content-queue"] });
    },
  });

  const sorted = [...gaps].sort(
    (a, b) => (PRIORITY_ORDER[a.category] ?? 99) - (PRIORITY_ORDER[b.category] ?? 99)
  );
  const { page, setPage, slice, total } = usePaged(sorted, PAGE_SIZE);
  const gapKey = (g: DashboardData["gap_queries"][0]) => `${g.brand_id}:${g.query}`;

  return (
    <div className="aeo-panel overflow-hidden">
      <div className="px-5 py-4 border-b border-border">
        <h3 className="aeo-title text-ink">Gap Analysis</h3>
        <p className="text-xs text-muted mt-0.5">
          Queries where competitors win AI citations — queue content matched to gap type (FAQ, comparison, vertical, etc.)
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-panel border-b border-border text-left">
              <th className="px-4 py-2 aeo-table-head">Query</th>
              <th className="px-4 py-2 aeo-table-head">Brand</th>
              <th className="px-4 py-2 aeo-table-head">Category</th>
              <th className="px-4 py-2 aeo-table-head">Competitor Cited</th>
              <th className="px-4 py-2 aeo-table-head"></th>
            </tr>
          </thead>
          <tbody>
            {sorted.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-muted/80">
                  No gaps detected — run a citation audit to populate this
                </td>
              </tr>
            ) : (
              slice.map((g) => {
                const key = gapKey(g);
                return (
                  <tr key={key} className="border-t border-border hover:bg-panel-hover">
                    <td className="px-4 py-3">{g.query}</td>
                    <td className="px-4 py-3 text-muted">{g.brand_id}</td>
                    <td className="px-4 py-3">
                      <span className="aeo-badge-warning">
                        {g.category?.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted">
                      {g.competitor_cited || (g.invisible ? "Not cited (invisible)" : "—")}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        disabled={addToQueue.isPending}
                        onClick={() => {
                          setQueued(key);
                          addToQueue.mutate(g, {
                            onSettled: () => setTimeout(() => setQueued(null), 2000),
                          });
                        }}
                        className="text-xs text-ink hover:text-cyan font-medium disabled:opacity-50"
                      >
                        {queued === key && addToQueue.isPending ? "Adding…" : "Add to queue"}
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      <Pagination page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} label="gaps" />
    </div>
  );
}
