import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { DashboardData } from "../types";
import { apiFetch } from "../lib/api";

const PRIORITY_ORDER: Record<string, number> = {
  emergency: 1,
  research_evaluation: 2,
  compliance_regulatory: 3,
  vertical_specific: 4,
};

export function GapAnalysisTable({ gaps }: { gaps: DashboardData["gap_queries"] }) {
  const queryClient = useQueryClient();
  const [queued, setQueued] = useState<number | null>(null);

  const addToQueue = useMutation({
    mutationFn: (gap: DashboardData["gap_queries"][0]) =>
      apiFetch("/api/content/queue/from-gap", {
        method: "POST",
        body: JSON.stringify({
          brand_id: gap.brand_id,
          target_query: gap.query,
          content_type: "faq_hub",
          title: gap.query,
          priority: PRIORITY_ORDER[gap.category] ?? 3,
        }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["content-queue"] });
    },
  });

  const sorted = [...gaps].sort(
    (a, b) => (PRIORITY_ORDER[a.category] ?? 99) - (PRIORITY_ORDER[b.category] ?? 99)
  );

  return (
    <div className="bg-white rounded border border-black/8 overflow-hidden">
      <div className="px-5 py-4 border-b border-black/8">
        <h3 className="font-display text-base font-bold text-navy">Gap Analysis</h3>
        <p className="text-xs text-black/50 mt-0.5">
          Queries where competitors are cited instead of Axxiom — add to Content Queue to close gaps
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-red-50 text-left">
              <th className="px-4 py-2 font-medium text-orange">Query</th>
              <th className="px-4 py-2 font-medium text-orange">Brand</th>
              <th className="px-4 py-2 font-medium text-orange">Category</th>
              <th className="px-4 py-2 font-medium text-orange">Competitor Cited</th>
              <th className="px-4 py-2 font-medium text-orange"></th>
            </tr>
          </thead>
          <tbody>
            {sorted.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-black/40">
                  No gaps detected — run a citation audit when the tracker is configured
                </td>
              </tr>
            ) : (
              sorted.map((g, i) => (
                <tr key={i} className="border-t border-black/5 hover:bg-cream/50">
                  <td className="px-4 py-3">{g.query}</td>
                  <td className="px-4 py-3 text-black/60">{g.brand_id}</td>
                  <td className="px-4 py-3">
                    <span className="text-xs bg-orange/10 text-orange px-2 py-0.5 rounded">
                      {g.category?.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-black/60">{g.competitor_cited || "—"}</td>
                  <td className="px-4 py-3 text-right">
                    <button
                      type="button"
                      disabled={addToQueue.isPending}
                      onClick={() => {
                        setQueued(i);
                        addToQueue.mutate(g, {
                          onSettled: () => setTimeout(() => setQueued(null), 2000),
                        });
                      }}
                      className="text-xs text-navy hover:text-orange font-medium disabled:opacity-50"
                    >
                      {queued === i && addToQueue.isPending ? "Adding…" : "Add to queue"}
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
