import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { apiFetch } from "../lib/api";
import type { Brand, PublishedContent } from "../types";

export function PublishedContentPage() {
  const [brandFilter, setBrandFilter] = useState("all");

  const { data: brands } = useQuery({
    queryKey: ["brands"],
    queryFn: () => apiFetch<Brand[]>("/api/brands"),
  });

  const brandsById = useMemo(
    () => Object.fromEntries((brands ?? []).map((b) => [b.id, b.name])),
    [brands],
  );

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["published-content", brandFilter],
    queryFn: () => {
      const params = brandFilter !== "all" ? `?brand_id=${encodeURIComponent(brandFilter)}` : "";
      return apiFetch<PublishedContent[]>(`/api/content/published${params}`);
    },
    refetchInterval: 60000,
  });

  const items = data ?? [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm text-muted">
            Live posts on WordPress from Approve &amp; Publish. Open links to view on the site.
          </p>
        </div>
        <select
          value={brandFilter}
          onChange={(e) => setBrandFilter(e.target.value)}
          className="text-sm border border-border rounded px-3 py-2 bg-panel-elevated"
        >
          <option value="all">All brands</option>
          {brands?.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </select>
      </div>

      {isError && (
        <div className="bg-warning/10 border border-warning/25 rounded px-4 py-3 text-sm text-warning">
          {(error as Error)?.message ?? "Failed to load published content"}
        </div>
      )}

      <div className="aeo-panel overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-muted">
              <th className="px-4 py-3 font-medium">Title</th>
              <th className="px-4 py-3 font-medium">Brand</th>
              <th className="px-4 py-3 font-medium">Type</th>
              <th className="px-4 py-3 font-medium">Published</th>
              <th className="px-4 py-3 font-medium">Live URL</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-muted/80">
                  Loading published content…
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-muted/80">
                  No published content yet. Approve a draft in{" "}
                  <Link to="/content/review" className="text-ink hover:text-cyan font-medium">
                    Content Review
                  </Link>
                  .
                </td>
              </tr>
            ) : (
              items.map((item) => (
                <tr key={item.id} className="border-t border-border hover:bg-panel-hover">
                  <td className="px-4 py-3 font-medium text-ink">{item.title ?? "—"}</td>
                  <td className="px-4 py-3 text-muted">
                    {brandsById[item.brand_id] ?? item.brand_id}
                  </td>
                  <td className="px-4 py-3 text-muted">{item.content_type ?? "—"}</td>
                  <td className="px-4 py-3 text-muted text-xs whitespace-nowrap">
                    {item.published_at
                      ? new Date(item.published_at).toLocaleString()
                      : "—"}
                  </td>
                  <td className="px-4 py-3">
                    {item.wp_post_url ? (
                      <a
                        href={item.wp_post_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-ink text-xs font-medium hover:text-cyan break-all"
                      >
                        View on site ↗
                      </a>
                    ) : (
                      <span className="text-muted/50 text-xs">No URL</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {!isLoading && items.length > 0 && (
        <p className="text-xs text-muted/80">{items.length} published post(s)</p>
      )}
    </div>
  );
}
