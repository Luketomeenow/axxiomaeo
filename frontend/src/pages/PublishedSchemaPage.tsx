import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Pagination, usePaged } from "../components/Pagination";
import { SchemaPreview } from "../components/SchemaPreview";
import { apiFetch } from "../lib/api";
import type { Brand, PublishedSchema, PublishedSchemaDetail } from "../types";

const PUBLISHED_PAGE_SIZE = 8;

const SOURCE_LABELS: Record<PublishedSchema["source"], string> = {
  brand_schema: "Brand schema",
  content: "Content post",
};

export function PublishedSchemaPage() {
  const [brandFilter, setBrandFilter] = useState("all");
  const [sourceFilter, setSourceFilter] = useState<"all" | PublishedSchema["source"]>("all");
  const [selected, setSelected] = useState<PublishedSchema | null>(null);
  const [detail, setDetail] = useState<PublishedSchemaDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const { data: brands } = useQuery({
    queryKey: ["brands"],
    queryFn: () => apiFetch<Brand[]>("/api/brands"),
  });

  const brandsById = useMemo(
    () => Object.fromEntries((brands ?? []).map((b) => [b.id, b.name])),
    [brands],
  );

  const queryParams = useMemo(() => {
    const params = new URLSearchParams();
    if (brandFilter !== "all") params.set("brand_id", brandFilter);
    if (sourceFilter !== "all") params.set("source", sourceFilter);
    const qs = params.toString();
    return qs ? `?${qs}` : "";
  }, [brandFilter, sourceFilter]);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["published-schema", brandFilter, sourceFilter],
    queryFn: () => apiFetch<PublishedSchema[]>(`/api/schema/published${queryParams}`),
    refetchInterval: 60000,
  });

  const items = data ?? [];
  const paged = usePaged(items, PUBLISHED_PAGE_SIZE);

  const loadDetail = async (item: PublishedSchema) => {
    setSelected(item);
    setDetail(null);
    setLoadingDetail(true);
    try {
      const d = await apiFetch<PublishedSchemaDetail>(
        `/api/schema/published/${item.source}/${item.id}`,
      );
      setDetail(d);
    } finally {
      setLoadingDetail(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm text-muted">
            Live JSON-LD from <strong className="text-ink">Schema Review</strong> (brand pages) and{" "}
            <strong className="text-ink">Content Review</strong> (blog posts). Open the live URL and
            view source to confirm <code className="text-xs">application/ld+json</code> on the site.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <select
            value={sourceFilter}
            onChange={(e) => {
              setSourceFilter(e.target.value as typeof sourceFilter);
              setSelected(null);
              setDetail(null);
            }}
            className="text-sm border border-border rounded px-3 py-2 bg-panel-elevated"
          >
            <option value="all">All sources</option>
            <option value="brand_schema">Brand schema only</option>
            <option value="content">Content posts only</option>
          </select>
          <select
            value={brandFilter}
            onChange={(e) => {
              setBrandFilter(e.target.value);
              setSelected(null);
              setDetail(null);
            }}
            className="text-sm border border-border rounded px-3 py-2 bg-panel-elevated"
          >
            <option value="all">All brands</option>
            {brands?.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
          <Link
            to="/schema/review"
            className="text-sm text-ink hover:text-cyan font-medium self-center px-2"
          >
            Schema Review →
          </Link>
        </div>
      </div>

      {isError && (
        <div className="bg-warning/10 border border-warning/25 rounded px-4 py-3 text-sm text-warning">
          {(error as Error)?.message ?? "Failed to load published schema"}
        </div>
      )}

      <div className="grid lg:grid-cols-2 gap-6">
        <div className="aeo-panel overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted">
                <th className="px-4 py-3">Title</th>
                <th className="px-4 py-3">Brand</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Source</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-muted/80">
                    Loading published schema…
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-muted/80">
                    <p>No published schema yet.</p>
                    <p className="text-xs mt-2">
                      Approve items in{" "}
                      <Link to="/schema/review" className="text-ink hover:text-cyan font-medium">
                        Schema Review
                      </Link>{" "}
                      or publish content from{" "}
                      <Link to="/content/review" className="text-ink hover:text-cyan font-medium">
                        Content Review
                      </Link>
                      .
                    </p>
                  </td>
                </tr>
              ) : (
                paged.slice.map((item) => (
                  <tr
                    key={`${item.source}-${item.id}`}
                    className={`border-t border-border cursor-pointer hover:bg-panel-hover ${
                      selected?.source === item.source && selected?.id === item.id ? "bg-void" : ""
                    }`}
                    onClick={() => loadDetail(item)}
                  >
                    <td className="px-4 py-3 font-medium text-ink">{item.title ?? "—"}</td>
                    <td className="px-4 py-3 text-muted">
                      {brandsById[item.brand_id] ?? item.brand_id}
                    </td>
                    <td className="px-4 py-3 text-muted text-xs">{item.schema_type ?? "—"}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`text-xs px-2 py-0.5 rounded ${
                          item.source === "brand_schema"
                            ? "bg-navy/10 text-ink"
                            : "bg-warning/10 text-warning"
                        }`}
                      >
                        {SOURCE_LABELS[item.source]}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-ink text-xs whitespace-nowrap">View →</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          <Pagination
            page={paged.page}
            pageSize={PUBLISHED_PAGE_SIZE}
            total={paged.total}
            onPage={paged.setPage}
            label="published schemas"
          />
        </div>

        {selected && (
          <div className="space-y-4">
            <div className="aeo-panel px-4 py-3 text-sm space-y-2">
              <p className="font-medium text-ink">{selected.title}</p>
              <p className="text-muted text-xs">
                {SOURCE_LABELS[selected.source]} · {selected.schema_type}
                {selected.published_at && (
                  <> · Published {new Date(selected.published_at).toLocaleString()}</>
                )}
              </p>
              {selected.wp_post_url && (
                <a
                  href={selected.wp_post_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-block text-ink text-xs font-medium hover:text-cyan"
                >
                  View live page ↗
                </a>
              )}
            </div>

            {loadingDetail ? (
              <p className="text-sm text-muted/80">Loading schema…</p>
            ) : detail?.schema_json ? (
              <SchemaPreview schemaJson={detail.schema_json} />
            ) : detail && selected.source === "content" ? (
              <div className="aeo-panel px-4 py-4 text-sm text-muted space-y-2">
                <p className="font-medium text-ink">Schema on live post</p>
                <p>
                  JSON-LD for content posts is stored on WordPress in post meta (
                  <code className="text-xs">aeo_schema_json</code>). This dashboard records schema
                  types: <strong>{detail?.schema_types.join(", ") ?? selected.schema_type}</strong>.
                </p>
                <p className="text-xs text-muted">
                  Open the live URL → View Page Source → search for{" "}
                  <code className="text-xs">application/ld+json</code>.
                </p>
              </div>
            ) : (
              <div className="aeo-panel px-4 py-4 text-sm text-muted">
                <p>Could not load schema from WordPress. Open the live URL and view source.</p>
              </div>
            )}
          </div>
        )}
      </div>

      {!isLoading && items.length > 0 && (
        <p className="text-xs text-muted/80">{items.length} published schema item(s)</p>
      )}
    </div>
  );
}
