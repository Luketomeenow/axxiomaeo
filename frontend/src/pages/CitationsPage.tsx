import { useMutation, useQuery } from "@tanstack/react-query";
import { GapAnalysisTable } from "../components/GapAnalysisTable";
import { apiFetch } from "../lib/api";
import type { DashboardData } from "../types";

interface CitationRecord {
  id: number;
  brand_id: string;
  query: string;
  query_category: string;
  platform: string;
  is_cited: boolean;
  competitor_cited: string;
  checked_at: string;
}

export function CitationsPage() {
  const audit = useMutation({
    mutationFn: () => apiFetch("/api/citations/audit", { method: "POST" }),
  });

  const { data: citations, isLoading } = useQuery({
    queryKey: ["citations"],
    queryFn: () => apiFetch<CitationRecord[]>("/api/citations/latest"),
    refetchInterval: 60000,
  });

  const { data: gaps } = useQuery({
    queryKey: ["gaps"],
    queryFn: () => apiFetch<DashboardData["gap_queries"]>("/api/citations/gaps"),
  });

  const cited = citations?.filter((c) => c.is_cited).length ?? 0;
  const total = citations?.length ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-xl font-bold text-navy">Citation Monitoring</h2>
          <p className="text-sm text-black/50 mt-1">
            {total > 0 ? `${cited}/${total} queries cited (${Math.round((cited / total) * 100)}%)` : "No audit data yet"}
          </p>
        </div>
        <button
          onClick={() => audit.mutate()}
          disabled={audit.isPending}
          className="px-4 py-2 bg-navy text-white rounded text-sm hover:bg-navy/90 disabled:opacity-50"
        >
          {audit.isPending ? "Running audit…" : "Run Citation Audit"}
        </button>
      </div>

      {gaps && <GapAnalysisTable gaps={gaps} />}

      <div className="bg-white rounded border border-black/8 overflow-hidden">
        <div className="px-5 py-4 border-b border-black/8">
          <h3 className="font-display text-base font-bold text-navy">Latest Citation Results</h3>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-black/8 text-left text-black/50">
              <th className="px-4 py-3">Query</th>
              <th className="px-4 py-3">Brand</th>
              <th className="px-4 py-3">Platform</th>
              <th className="px-4 py-3">Cited</th>
              <th className="px-4 py-3">Competitor</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-black/40">
                  Loading…
                </td>
              </tr>
            ) : (
              citations?.slice(0, 50).map((c) => (
                <tr key={c.id} className="border-t border-black/5">
                  <td className="px-4 py-3">{c.query}</td>
                  <td className="px-4 py-3 text-black/60">{c.brand_id}</td>
                  <td className="px-4 py-3 text-black/60">{c.platform}</td>
                  <td className="px-4 py-3">
                    {c.is_cited ? (
                      <span className="text-green-700">✓</span>
                    ) : (
                      <span className="text-orange">✗</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-black/60">{c.competitor_cited || "—"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
