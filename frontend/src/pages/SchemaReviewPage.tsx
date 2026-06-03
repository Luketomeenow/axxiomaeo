import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiFetch } from "../lib/api";
import type { SchemaDeployment } from "../types";

export function SchemaReviewPage() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<SchemaDeployment | null>(null);
  const [detail, setDetail] = useState<{ schema_json: string } | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["schema-deployments"],
    queryFn: () => apiFetch<SchemaDeployment[]>("/api/schema/deployments?status=pending_review"),
    refetchInterval: 30000,
  });

  const approve = useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/api/schema/deployments/${id}/approve`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schema-deployments"] });
      setSelected(null);
      setDetail(null);
    },
  });

  const reject = useMutation({
    mutationFn: ({ id, notes }: { id: number; notes: string }) =>
      apiFetch(`/api/schema/deployments/${id}/reject`, {
        method: "POST",
        body: JSON.stringify({ notes }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schema-deployments"] });
      setSelected(null);
    },
  });

  const loadDetail = async (dep: SchemaDeployment) => {
    setSelected(dep);
    const d = await apiFetch<{ schema_json: string }>(`/api/schema/deployments/${dep.id}`);
    setDetail(d);
  };

  return (
    <div className="space-y-4">
      <h2 className="font-display text-xl font-bold text-navy">Schema Approval Inbox</h2>
      <div className="grid lg:grid-cols-2 gap-6">
        <div className="bg-white rounded border border-black/8 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-black/8 text-left text-black/50">
                <th className="px-4 py-3">Title</th>
                <th className="px-4 py-3">Brand</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-black/40">
                    Loading…
                  </td>
                </tr>
              ) : !data?.length ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-black/40">
                    No schema deployments pending
                  </td>
                </tr>
              ) : (
                data.map((d) => (
                  <tr
                    key={d.id}
                    className={`border-t border-black/5 cursor-pointer hover:bg-cream/50 ${
                      selected?.id === d.id ? "bg-cream" : ""
                    }`}
                    onClick={() => loadDetail(d)}
                  >
                    <td className="px-4 py-3 font-medium">{d.title}</td>
                    <td className="px-4 py-3 text-black/60">{d.brand_id}</td>
                    <td className="px-4 py-3 text-black/60">{d.schema_type}</td>
                    <td className="px-4 py-3 text-navy text-xs">View →</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {selected && (
          <div className="bg-white rounded border border-black/8 p-4 space-y-4">
            <h3 className="font-medium text-navy">{selected.title}</h3>
            <pre className="text-xs bg-gray-50 p-4 rounded overflow-auto max-h-80">
              {detail?.schema_json
                ? JSON.stringify(JSON.parse(detail.schema_json), null, 2)
                : "Loading…"}
            </pre>
            <div className="flex gap-2">
              <button
                onClick={() => approve.mutate(selected.id)}
                disabled={approve.isPending}
                className="px-4 py-2 bg-navy text-white rounded text-sm"
              >
                Approve & Deploy
              </button>
              <button
                onClick={() => reject.mutate({ id: selected.id, notes: "" })}
                disabled={reject.isPending}
                className="px-4 py-2 border border-orange text-orange rounded text-sm"
              >
                Reject
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
