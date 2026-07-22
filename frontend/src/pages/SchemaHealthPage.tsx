import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useState } from "react";
import { apiFetch } from "../lib/api";

interface SchemaErrorPage {
  wp_post_url: string | null;
  wp_post_id: number | null;
  error_details: string | null;
  schema_types: string[];
  validated_at: string | null;
}

interface SchemaHealthRow {
  brand_id: string;
  brand_name: string;
  total_pages: number;
  valid_schema: number;
  errors: number;
  last_validation: string | null;
  error_pages?: SchemaErrorPage[];
}

export function SchemaHealthPage() {
  const queryClient = useQueryClient();
  const [msg, setMsg] = useState("");
  const [expandedBrand, setExpandedBrand] = useState<string | null>(null);

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
          <h2 className="text-xl font-bold text-ink">Schema Health</h2>
          <p className="text-sm text-muted mt-1">
            Crawls live pages and shows the latest JSON-LD check per page. The{" "}
            <a
              href="https://github.com/Luketomeenow/axxiomaeo/blob/main/wordpress/README.md"
              className="aeo-link"
              target="_blank"
              rel="noreferrer"
            >
              AEO Schema mu-plugin
            </a>{" "}
            is installed on all 5 brand sites.
          </p>
        </div>
        <div className="flex flex-wrap gap-3 items-center">
          <Link to="/schema/review" className="text-sm text-ink hover:text-cyan font-medium">
            Schema Review →
          </Link>
          <Link to="/schema/published" className="text-sm text-ink hover:text-cyan font-medium">
            Published Schema →
          </Link>
        </div>
      </div>

      {msg && (
        <div className="bg-void border border-border text-sm px-4 py-3 rounded text-ink">
          {msg}
        </div>
      )}

      <div className="aeo-panel rounded overflow-hidden text-sm">
        <div className="px-4 py-3 border-b border-border bg-void">
          <h3 className="font-medium text-ink">How validation works</h3>
        </div>
        <div className="px-4 py-4 space-y-3 text-ink/80">
          <div>
            <p className="font-medium text-ink mb-1">What gets checked</p>
            <p className="text-xs sm:text-sm">
              Every <strong>published blog post</strong> plus every{" "}
              <strong>approved brand-schema carrier page</strong> for the brand — that&apos;s the{" "}
              <em>Pages Tracked</em> count. For each URL the validator fetches the live page the way
              a browser would (following redirects) and looks for an{" "}
              <code className="text-xs text-cyan">&lt;script type=&quot;application/ld+json&quot;&gt;</code>{" "}
              block in the rendered HTML — the JSON-LD that AI engines and Google actually read.
            </p>
          </div>
          <div>
            <p className="font-medium text-ink mb-1">What the columns mean</p>
            <ul className="list-disc list-inside space-y-1 text-xs sm:text-sm">
              <li>
                <strong>Valid Schema</strong> — pages whose live HTML contains a JSON-LD block.
              </li>
              <li>
                <strong>Errors</strong> — pages that loaded without JSON-LD, <em>or</em> pages the
                validator couldn&apos;t fetch (deleted, or the crawler was blocked by the site&apos;s
                bot protection). A blocked fetch is a measurement failure, not proof schema is
                missing.
              </li>
              <li>
                <strong>Coverage</strong> — Valid ÷ Pages Tracked, using only each page&apos;s{" "}
                <em>latest</em> check. Re-running validation replaces a page&apos;s result; it never
                double-counts.
              </li>
            </ul>
          </div>
          <div>
            <p className="font-medium text-ink mb-1">When it runs &amp; self-healing</p>
            <p className="text-xs sm:text-sm">
              Automatically once a month, or on demand with <strong>Run validation</strong> (per
              brand — results land within a minute or two). The monthly run also self-heals: a post
              that loads fine but has no JSON-LD gets its schema rebuilt from the stored draft and
              queued in{" "}
              <Link to="/schema/review" className="aeo-link">
                Schema Review
              </Link>{" "}
              as &quot;Regenerated schema&quot; — nothing republishes without your approval.
            </p>
          </div>
        </div>
      </div>

      {isError && (
        <div className="bg-warning/10 border border-warning/30 text-warning text-sm px-4 py-3 rounded">
          {(error as Error).message}
        </div>
      )}

      <div className="aeo-panel p-4 flex flex-wrap gap-2 items-end">
        <div>
          <label className="block text-xs font-medium text-muted mb-1">Brand actions</label>
          <select
            id="schema-brand-pick"
            className="bg-panel border border-border rounded-md px-3 py-2 text-sm text-ink min-w-[200px] focus:outline-none focus:border-cyan/50"
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
          className="aeo-btn-primary text-sm"
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
          className="aeo-btn-secondary text-sm"
          disabled={validate.isPending || deploySchema.isPending}
          onClick={() => {
            const el = document.getElementById("schema-brand-pick") as HTMLSelectElement;
            if (el?.value) deploySchema.mutate(el.value);
          }}
        >
          Queue brand schema
        </button>
      </div>

      <div className="aeo-panel overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-muted">
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
                <td colSpan={6} className="px-4 py-8 text-center text-muted/80">
                  Loading…
                </td>
              </tr>
            ) : (
              data?.map((row) => {
                const coverage =
                  row.total_pages > 0
                    ? Math.round((row.valid_schema / row.total_pages) * 100)
                    : 0;
                const barColor =
                  row.errors > 0
                    ? "bg-warning"
                    : coverage === 100 && row.total_pages > 0
                      ? "bg-success"
                      : "bg-cyan";
                const expanded = expandedBrand === row.brand_id;
                return (
                  <>
                    <tr key={row.brand_id} className="border-t border-border">
                      <td className="px-4 py-3 font-medium">{row.brand_name}</td>
                      <td className="px-4 py-3">{row.total_pages}</td>
                      <td className="px-4 py-3 text-success">{row.valid_schema}</td>
                      <td className="px-4 py-3">
                        {row.errors > 0 ? (
                          <button
                            type="button"
                            onClick={() => setExpandedBrand(expanded ? null : row.brand_id)}
                            className="text-danger font-medium hover:text-warning inline-flex items-center gap-1"
                            title="Show which pages failed and why"
                          >
                            {row.errors}
                            <span className="text-[10px]">{expanded ? "▲" : "▼"}</span>
                          </button>
                        ) : (
                          <span className="text-muted">0</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="flex-1 bg-white/10 rounded-full h-2 max-w-[100px]">
                            <div
                              className={`${barColor} h-2 rounded-full transition-all`}
                              style={{ width: `${coverage}%` }}
                            />
                          </div>
                          <span className="text-xs tabular-nums text-muted">{coverage}%</span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-muted text-xs">
                        {row.last_validation
                          ? new Date(row.last_validation).toLocaleDateString()
                          : "Never"}
                      </td>
                    </tr>
                    {expanded && (row.error_pages?.length ?? 0) > 0 && (
                      <tr key={`${row.brand_id}-errors`} className="border-t border-border bg-void/60">
                        <td colSpan={6} className="px-4 py-3">
                          <p className="text-xs text-muted mb-2">
                            Failing pages — latest check each. <em>HTTP 404</em> usually means the
                            post was deleted or its permalink changed; <em>no application/ld+json
                            block</em> means the page loads but carries no schema (the monthly sweep
                            queues a regenerated schema for review); <em>bot-blocked</em> is a
                            measurement failure, not missing schema.
                          </p>
                          <ul className="space-y-1.5">
                            {row.error_pages?.map((ep, i) => (
                              <li key={i} className="text-xs flex flex-wrap items-baseline gap-x-2">
                                {ep.wp_post_url ? (
                                  <a
                                    href={ep.wp_post_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-ink hover:text-cyan font-mono break-all"
                                  >
                                    {ep.wp_post_url.replace(/^https?:\/\//, "")}
                                  </a>
                                ) : (
                                  <span className="text-muted font-mono">post #{ep.wp_post_id ?? "?"}</span>
                                )}
                                <span className="text-warning">{ep.error_details || "unknown error"}</span>
                                {ep.validated_at && (
                                  <span className="text-muted/60">
                                    checked {new Date(ep.validated_at).toLocaleString()}
                                  </span>
                                )}
                              </li>
                            ))}
                          </ul>
                        </td>
                      </tr>
                    )}
                  </>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
