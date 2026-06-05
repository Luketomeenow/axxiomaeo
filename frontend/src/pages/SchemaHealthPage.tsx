import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useState } from "react";
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
  const queryClient = useQueryClient();
  const [msg, setMsg] = useState("");

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["schema-health"],
    queryFn: () => apiFetch<SchemaHealthRow[]>("/api/schema/health"),
    refetchInterval: 60000,
  });

  const { data: brands } = useQuery({
    queryKey: ["brands"],
    queryFn: () => apiFetch<{ id: string; name: string }[]>("/api/brands"),
  });

  const validate = useMutation({
    mutationFn: (brandId: string) =>
      apiFetch(`/api/schema/validate/${brandId}`, { method: "POST" }),
    onSuccess: () => {
      setMsg("Validation started — refresh in a minute.");
      setTimeout(() => queryClient.invalidateQueries({ queryKey: ["schema-health"] }), 30000);
    },
    onError: (e: Error) => setMsg(e.message),
  });

  const deploySchema = useMutation({
    mutationFn: (brandId: string) =>
      apiFetch(`/api/schema/deploy/${brandId}`, { method: "POST" }),
    onSuccess: () => {
      setMsg("Schema deployments queued — check Schema Review.");
    },
    onError: (e: Error) => setMsg(e.message),
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="font-display text-xl font-bold text-navy">Schema Health</h2>
          <p className="text-sm text-black/50 mt-1">
            Requires JSON-LD in page source — install the{" "}
            <a
              href="https://github.com/Luketomeenow/axxiomaeo/blob/main/wordpress/README.md"
              className="text-orange hover:underline"
              target="_blank"
              rel="noreferrer"
            >
              WordPress mu-plugin
            </a>{" "}
            on each site.
          </p>
        </div>
        <Link to="/schema/review" className="text-sm text-navy hover:text-orange font-medium">
          Schema Review →
        </Link>
      </div>

      {msg && (
        <div className="bg-cream border border-black/10 text-sm px-4 py-3 rounded text-navy">
          {msg}
        </div>
      )}

      {isError && (
        <div className="bg-orange/10 border border-orange/30 text-orange text-sm px-4 py-3 rounded">
          {(error as Error).message}
        </div>
      )}

      <div className="bg-white rounded border border-black/8 p-4 flex flex-wrap gap-2 items-end">
        <div>
          <label className="block text-xs font-medium text-black/60 mb-1">Brand actions</label>
          <select
            id="schema-brand-pick"
            className="border border-black/15 rounded px-3 py-2 text-sm min-w-[200px]"
            defaultValue=""
          >
            <option value="" disabled>
              Select brand…
            </option>
            {brands?.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </div>
        <button
          type="button"
          className="px-3 py-2 bg-navy text-white rounded text-sm disabled:opacity-50"
          disabled={validate.isPending || deploySchema.isPending}
          onClick={() => {
            const el = document.getElementById("schema-brand-pick") as HTMLSelectElement;
            if (el?.value) validate.mutate(el.value);
          }}
        >
          Run validation
        </button>
        <button
          type="button"
          className="px-3 py-2 border border-navy text-navy rounded text-sm disabled:opacity-50"
          disabled={validate.isPending || deploySchema.isPending}
          onClick={() => {
            const el = document.getElementById("schema-brand-pick") as HTMLSelectElement;
            if (el?.value) deploySchema.mutate(el.value);
          }}
        >
          Queue brand schema
        </button>
      </div>

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
