import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { SchemaPreview } from "../components/SchemaPreview";
import { apiFetch } from "../lib/api";
import type { SchemaDeployment } from "../types";

function validateSchemaJson(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed) return "Schema JSON cannot be empty";
  try {
    const parsed = JSON.parse(trimmed);
    if (typeof parsed !== "object" || parsed === null) {
      return "Schema must be a JSON object or array";
    }
    return null;
  } catch {
    return "Invalid JSON — fix syntax before saving or deploying";
  }
}

export function SchemaReviewPage() {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<SchemaDeployment | null>(null);
  const [detail, setDetail] = useState<{ schema_json: string } | null>(null);
  const [editedSchema, setEditedSchema] = useState("");
  const [deployMsg, setDeployMsg] = useState("");
  const [actionMsg, setActionMsg] = useState("");

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

  const saveSchema = useMutation({
    mutationFn: ({ id, schema_json }: { id: number; schema_json: string }) =>
      apiFetch(`/api/schema/deployments/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ schema_json }),
      }),
    onSuccess: (_res, vars) => {
      setDetail({ schema_json: vars.schema_json });
      setActionMsg("Schema saved.");
      queryClient.invalidateQueries({ queryKey: ["schema-deployments"] });
    },
    onError: (e: Error) => setActionMsg(e.message),
  });

  const approve = useMutation({
    mutationFn: ({ id, schema_json }: { id: number; schema_json: string }) =>
      apiFetch(`/api/schema/deployments/${id}/approve`, {
        method: "POST",
        body: JSON.stringify({ schema_json }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schema-deployments"] });
      queryClient.invalidateQueries({ queryKey: ["published-schema"] });
      setSelected(null);
      setDetail(null);
      setEditedSchema("");
      setActionMsg("");
    },
    onError: (e: Error) => setActionMsg(e.message),
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
    setEditedSchema("");
    setActionMsg("");
    const d = await apiFetch<{ schema_json: string }>(`/api/schema/deployments/${dep.id}`);
    setDetail(d);
    setEditedSchema(d.schema_json ?? "");
  };

  const parseError = useMemo(() => validateSchemaJson(editedSchema), [editedSchema]);
  const isDirty = !!detail && editedSchema !== (detail.schema_json ?? "");

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-ink">Schema Approval Inbox</h2>
          <p className="text-sm text-muted mt-1">
            Review brand-level JSON-LD before it goes live on WordPress
          </p>
        </div>
        <div className="flex flex-wrap gap-2 items-center">
          <Link
            to="/schema/published"
            className="text-sm text-ink hover:text-cyan font-medium px-2"
          >
            Published Schema →
          </Link>
          <select
            id="schema-deploy-brand"
            className="border border-border rounded px-3 py-2 text-sm"
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
            className="px-3 py-2 bg-cyan text-void rounded text-sm disabled:opacity-50"
          >
            {deployBrand.isPending ? "Queuing…" : "Queue brand schema"}
          </button>
        </div>
      </div>

      {deployMsg && (
        <p className="text-sm text-ink bg-void px-4 py-2 rounded border border-border">
          {deployMsg}
        </p>
      )}

      <div className="aeo-panel rounded overflow-hidden text-sm">
        <div className="px-4 py-3 border-b border-border bg-void">
          <h3 className="font-medium text-ink">How Schema Review works</h3>
        </div>
        <div className="px-4 py-4 space-y-4 text-ink/80">
          <p>
            This inbox is separate from{" "}
            <Link to="/content/review" className="text-ink hover:text-cyan font-medium">
              Content Review
            </Link>
            . Content drafts ship FAQ/article schema on blog posts. Here you approve{" "}
            <strong className="text-ink">brand-level structured data</strong> built from each
            brand&apos;s settings (name, URL, markets, phone).
          </p>

          <div>
            <p className="font-medium text-ink mb-2">What gets queued per brand</p>
            <ul className="list-disc list-inside space-y-1 text-xs sm:text-sm">
              <li>
                <strong>Organization</strong> — company entity for the brand
              </li>
              <li>
                <strong>LocalBusiness</strong> — location / service-area signals
              </li>
              <li>
                <strong>Service</strong> (×5) — Maintenance, Repair, Modernization, Installation,
                Inspection
              </li>
            </ul>
            <p className="text-xs text-muted mt-2">
              Click <strong>Queue brand schema</strong> above, or use{" "}
              <Link to="/schema/health" className="text-ink hover:text-cyan">
                Schema Health
              </Link>{" "}
              — 7 deployments per brand land here as <code className="text-xs">pending_review</code>
              .
            </p>
          </div>

          <div>
            <p className="font-medium text-ink mb-2">Approval workflow</p>
            <ol className="list-decimal list-inside space-y-1 text-xs sm:text-sm">
              <li>Select a row → preview the JSON-LD on the right</li>
              <li>
                Edit the JSON-LD on the right if needed, then <strong>Save</strong> or go straight
                to <strong>Approve &amp; Deploy</strong>
              </li>
              <li>
                <strong>Approve &amp; Deploy</strong> — creates or updates a hidden WordPress{" "}
                <em>page</em> (schema carrier) and stores JSON-LD in post meta (
                <code className="text-xs">aeo_schema_json</code>). The MU plugin prints it in that
                page&apos;s <code className="text-xs">&lt;head&gt;</code> — not in your blog posts
                or site header globally.
              </li>
              <li>
                Install <code className="text-xs">wordpress/axxiom-aeo-schema.php</code> as a
                must-use plugin on each brand site (one-time SFTP step)
              </li>
              <li>
                <strong>Reject</strong> — skips deploy; nothing changes on the live site
              </li>
            </ol>
          </div>

          <p className="text-xs text-muted border-t border-border pt-3">
            Nothing deploys without your approval. After publish, use Schema Health to crawl live URLs
            and confirm <code className="text-xs">application/ld+json</code> is present.
          </p>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-6">
        <div className="aeo-panel overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted">
                <th className="px-4 py-3">Title</th>
                <th className="px-4 py-3">Brand</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-muted/80">
                    Loading…
                  </td>
                </tr>
              ) : !data?.length ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-muted/80">
                    <p>No schema deployments pending.</p>
                    <p className="text-xs mt-2">
                      Use <strong>Queue brand schema</strong> above or{" "}
                      <Link to="/schema/health" className="text-ink hover:text-cyan">
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
                    className={`border-t border-border cursor-pointer hover:bg-panel-hover ${
                      selected?.id === d.id ? "bg-void" : ""
                    }`}
                    onClick={() => loadDetail(d)}
                  >
                    <td className="px-4 py-3 font-medium">{d.title}</td>
                    <td className="px-4 py-3 text-muted">{d.brand_id}</td>
                    <td className="px-4 py-3 text-muted">{d.schema_type}</td>
                    <td className="px-4 py-3 text-ink text-xs">View →</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {selected && (
          <div className="space-y-4">
            <SchemaPreview
              schemaJson={detail?.schema_json}
              editable
              value={editedSchema}
              onChange={setEditedSchema}
              parseError={parseError}
            />
            {actionMsg && (
              <p className="text-sm text-ink bg-void px-3 py-2 rounded border border-border">
                {actionMsg}
              </p>
            )}
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() =>
                  saveSchema.mutate({ id: selected.id, schema_json: editedSchema.trim() })
                }
                disabled={saveSchema.isPending || !detail || !!parseError || !isDirty}
                className="px-4 py-2 border border-navy text-ink rounded text-sm disabled:opacity-50"
              >
                {saveSchema.isPending ? "Saving…" : "Save changes"}
              </button>
              <button
                type="button"
                onClick={() =>
                  approve.mutate({ id: selected.id, schema_json: editedSchema.trim() })
                }
                disabled={approve.isPending || !detail || !!parseError}
                className="px-4 py-2 bg-cyan text-void rounded text-sm disabled:opacity-50"
              >
                Approve & Deploy
              </button>
              <button
                type="button"
                onClick={() => reject.mutate({ id: selected.id, notes: "" })}
                disabled={reject.isPending}
                className="px-4 py-2 border border-warning/40 text-warning rounded text-sm"
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
