import type { DashboardData } from "../types";

const PRIORITY_ORDER: Record<string, number> = {
  emergency: 1,
  research_evaluation: 2,
  compliance_regulatory: 3,
  vertical_specific: 4,
};

export function GapAnalysisTable({ gaps }: { gaps: DashboardData["gap_queries"] }) {
  const sorted = [...gaps].sort(
    (a, b) => (PRIORITY_ORDER[a.category] ?? 99) - (PRIORITY_ORDER[b.category] ?? 99)
  );

  return (
    <div className="bg-white rounded border border-black/8 overflow-hidden">
      <div className="px-5 py-4 border-b border-black/8">
        <h3 className="font-display text-base font-bold text-navy">Gap Analysis</h3>
        <p className="text-xs text-black/50 mt-0.5">Queries where competitors are cited instead of Axxiom</p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-red-50 text-left">
              <th className="px-4 py-2 font-medium text-orange">Query</th>
              <th className="px-4 py-2 font-medium text-orange">Brand</th>
              <th className="px-4 py-2 font-medium text-orange">Category</th>
              <th className="px-4 py-2 font-medium text-orange">Competitor Cited</th>
            </tr>
          </thead>
          <tbody>
            {sorted.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-black/40">
                  No gaps detected — great work!
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
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
