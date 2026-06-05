import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { SchemaPreview } from "../components/SchemaPreview";
import { apiFetch } from "../lib/api";
import type { SchemaDeployment } from "../types";

export function SchemaReviewPage() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<SchemaDeployment | null>(null);
  const [detail, setDetail] = useState<{ schema_json: string } | null>(null);
  const [deployMsg, setDeployMsg] = useState("");

  const { data: brands } = useQuery({
    queryKey: ["brands"],
    queryFn: () => apiFetch<{ id: string; name: string }[]>("/api/brands"),
  });

  const { data, isLoading } = useQuery({
    queryKey: ["schema-deployments"],
    queryFn: () => apiFetch<SchemaDeployment[]>("/api/schema/deployments?status=pending_review"),
    refetchInterval: 30000,
  });

  const deployBrand = useMutation({
    mutationFn: (brandId: string) =>
      apiFetch(`/api/schema/deploy/${brandId}`, { method: "POST" }),
    onSuccess: (res: { count?: number }) => {
      setDeployMsg(`Queued ${res.count ?? ""} schema deployments for review.`);
      queryClient.invalidateQueries({ queryKey: ["schema-deployments"] });
    },
    onError: (e: Error) => setDeployMsg(e.message),
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
    setDetail(null);
    const d = await apiFetch<{ schema_json: string }>(`/api/schema/deployments/${dep.id}`);
    setDetail(d);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h2 className="font-display text-xl font-bold text-navy">Schema Approval Inbox</h2>
        <div className="flex flex-wrap gap-2 items-center">
          <select
            id="schema-deploy-brand"
            className="border border-black/15 rounded px-3 py-2 text-sm"
            defaultValue=""
          >
            <option value="" disabled>
              Queue schema for brand…
            </option>
            {brands?.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            disabled={deployBrand.isPending}
            onClick={() => {
              const el = document.getElementById("schema-deploy-brand") as HTMLSelectElement;
              if (el?.value) deployBrand.mutate(el.value);
            }}
            className="px-3 py-2 bg-orange text-white rounded text-sm disabled:opacity-50"
          >
            {deployBrand.isPending ? "Queuing…" : "Queue brand schema"}
          </button>
        </div>
      </div>

      {deployMsg && (
        <p className="text-sm text-navy bg-cream px-4 py-2 rounded border border-black/8">
          {deployMsg}
        </p>
      )}

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
                    <p>No schema deployments pending.</p>
                    <p className="text-xs mt-2">
                      Use <strong>Queue brand schema</strong> above or{" "}
                      <Link to="/schema/health" className="text-navy hover:text-orange">
                        Schema Health
                      </Link>
                      .
                    </p>
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
          <div className="space-y-4">
            <SchemaPreview schemaJson={detail?.schema_json} />
            <div className="flex gap-2">
              <button
                onClick={() => approve.mutate(selected.id)}
                disabled={approve.isPending || !detail}
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
