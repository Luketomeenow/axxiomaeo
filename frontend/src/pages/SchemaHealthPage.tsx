import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../lib/api";

interface SchemaHealthRow {
  brand_id: string;
  brand_name: string;
  total_pages: number;
  valid_schema: number;
  errors: number;
  last_validation: string | null;
}

export function SchemaHealthPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["schema-health"],
    queryFn: () => apiFetch<SchemaHealthRow[]>("/api/schema/health"),
    refetchInterval: 60000,
  });

  return (
    <div className="space-y-4">
      <h2 className="font-display text-xl font-bold text-navy">Schema Health</h2>
      <div className="bg-white rounded border border-black/8 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-black/8 text-left text-black/50">
              <th className="px-4 py-3">Brand</th>
              <th className="px-4 py-3">Pages Tracked</th>
              <th className="px-4 py-3">Valid Schema</th>
              <th className="px-4 py-3">Errors</th>
              <th className="px-4 py-3">Coverage</th>
              <th className="px-4 py-3">Last Validation</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-black/40">
                  Loading…
                </td>
              </tr>
            ) : (
              data?.map((row) => {
                const coverage =
                  row.total_pages > 0
                    ? Math.round((row.valid_schema / row.total_pages) * 100)
                    : 0;
                return (
                  <tr key={row.brand_id} className="border-t border-black/5">
                    <td className="px-4 py-3 font-medium">{row.brand_name}</td>
                    <td className="px-4 py-3">{row.total_pages}</td>
                    <td className="px-4 py-3 text-green-700">{row.valid_schema}</td>
                    <td className="px-4 py-3 text-orange">{row.errors}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 bg-gray-100 rounded-full h-2 max-w-[100px]">
                          <div
                            className="bg-navy h-2 rounded-full"
                            style={{ width: `${coverage}%` }}
                          />
                        </div>
                        <span className="text-xs">{coverage}%</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-black/60 text-xs">
                      {row.last_validation
                        ? new Date(row.last_validation).toLocaleDateString()
                        : "Never"}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
