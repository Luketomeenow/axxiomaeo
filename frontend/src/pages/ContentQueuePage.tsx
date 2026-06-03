import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../lib/api";
import type { ContentQueueItem } from "../types";

const PRIORITY_LABEL: Record<number, string> = {
  1: "CRITICAL",
  3: "HIGH",
  5: "MEDIUM",
};

export function ContentQueuePage() {
  const { data, isLoading } = useQuery({
    queryKey: ["content-queue"],
    queryFn: () => apiFetch<ContentQueueItem[]>("/api/content/queue"),
    refetchInterval: 60000,
  });

  return (
    <div className="space-y-4">
      <h2 className="font-display text-xl font-bold text-navy">Content Queue</h2>
      <div className="bg-white rounded border border-black/8 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-black/8 text-left text-black/50">
              <th className="px-4 py-3">Title</th>
              <th className="px-4 py-3">Brand</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Priority</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Scheduled</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-black/40">
                  Loading…
                </td>
              </tr>
            ) : !data?.length ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-black/40">
                  Queue is empty
                </td>
              </tr>
            ) : (
              data.map((item) => (
                <tr key={item.id} className="border-t border-black/5">
                  <td className="px-4 py-3 font-medium">{item.title}</td>
                  <td className="px-4 py-3 text-black/60">{item.brand_id}</td>
                  <td className="px-4 py-3 text-black/60">{item.content_type}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`text-xs px-2 py-0.5 rounded font-medium ${
                        item.priority === 1
                          ? "bg-red-100 text-red-700"
                          : item.priority === 3
                            ? "bg-yellow-100 text-yellow-800"
                            : "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {PRIORITY_LABEL[item.priority] || "MEDIUM"}
                    </span>
                  </td>
                  <td className="px-4 py-3">{item.status}</td>
                  <td className="px-4 py-3 text-black/60">{item.scheduled_for || "—"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
