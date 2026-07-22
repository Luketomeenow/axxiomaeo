import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Pagination, usePaged } from "../components/Pagination";
import { apiFetch } from "../lib/api";
import type { Brand, PublishedContent } from "../types";

const PAGE_SIZE = 10;

type SortKey = "title" | "brand_id" | "content_type" | "word_count" | "published_at";

const SORT_LABELS: { key: SortKey; label: string }[] = [
  { key: "title", label: "Title" },
  { key: "brand_id", label: "Brand" },
  { key: "content_type", label: "Type" },
  { key: "word_count", label: "Words" },
  { key: "published_at", label: "Published" },
];

function compareBy(key: SortKey, a: PublishedContent, b: PublishedContent): number {
  if (key === "word_count") return (a.word_count ?? 0) - (b.word_count ?? 0);
  if (key === "published_at")
    return (a.published_at ?? "").localeCompare(b.published_at ?? "");
  return String(a[key] ?? "").localeCompare(String(b[key] ?? ""), undefined, {
    sensitivity: "base",
  });
}

export function PublishedContentPage() {
  const [brandFilter, setBrandFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("published_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const queryClient = useQueryClient();

  const returnToReview = useMutation({
    mutationFn: (pieceId: number) =>
      apiFetch(`/api/content/published/${pieceId}/return-to-review`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["published-content"] });
      queryClient.invalidateQueries({ queryKey: ["drafts"] });
    },
  });

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

  const contentTypes = useMemo(
    () => [...new Set((data ?? []).map((i) => i.content_type).filter(Boolean))].sort() as string[],
    [data],
  );

  const items = useMemo(() => {
    const q = search.trim().toLowerCase();
    const filtered = (data ?? []).filter((item) => {
      if (typeFilter !== "all" && item.content_type !== typeFilter) return false;
      if (!q) return true;
      return [item.title, item.target_query, item.slug, item.wp_post_url]
        .some((f) => (f ?? "").toLowerCase().includes(q));
    });
    const dir = sortDir === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => dir * compareBy(sortKey, a, b));
  }, [data, search, typeFilter, sortKey, sortDir]);

  const paged = usePaged(items, PAGE_SIZE);

  const toggleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      // Dates and word counts read best biggest-first; text A→Z.
      setSortDir(key === "published_at" || key === "word_count" ? "desc" : "asc");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm text-muted">
            Live posts on WordPress from Approve &amp; Publish. Open links to view on the site.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search title, query, slug, URL…"
            aria-label="Search published posts"
            className="text-sm border border-border rounded px-3 py-2 bg-panel-elevated w-64 placeholder:text-muted focus:outline-none focus:border-cyan/50"
          />
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            aria-label="Filter by content type"
            className="text-sm border border-border rounded px-3 py-2 bg-panel-elevated"
          >
            <option value="all">All types</option>
            {contentTypes.map((t) => (
              <option key={t} value={t}>
                {t.replace(/_/g, " ")}
              </option>
            ))}
          </select>
          <select
            value={brandFilter}
            onChange={(e) => setBrandFilter(e.target.value)}
            aria-label="Filter by brand"
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
      </div>

      {isError && (
        <div className="bg-warning/10 border border-warning/25 rounded px-4 py-3 text-sm text-warning">
          {(error as Error)?.message ?? "Failed to load published content"}
        </div>
      )}

      <div className="aeo-panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted">
                {SORT_LABELS.map(({ key, label }) => (
                  <th key={key} className="px-4 py-3 font-medium">
                    <button
                      type="button"
                      onClick={() => toggleSort(key)}
                      className={`inline-flex items-center gap-1 hover:text-ink ${
                        sortKey === key ? "text-ink" : ""
                      }`}
                      title={`Sort by ${label.toLowerCase()}`}
                    >
                      {label}
                      <span className="text-[10px]">
                        {sortKey === key ? (sortDir === "asc" ? "▲" : "▼") : "↕"}
                      </span>
                    </button>
                  </th>
                ))}
                <th className="px-4 py-3 font-medium">Live URL</th>
                <th className="px-4 py-3 font-medium"></th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-muted/80">
                    Loading published content…
                  </td>
                </tr>
              ) : paged.slice.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-muted/80">
                    {search || typeFilter !== "all" || brandFilter !== "all" ? (
                      "No posts match the current search/filters."
                    ) : (
                      <>
                        No published content yet. Approve a draft in{" "}
                        <Link to="/content/review" className="text-ink hover:text-cyan font-medium">
                          Content Review
                        </Link>
                        .
                      </>
                    )}
                  </td>
                </tr>
              ) : (
                paged.slice.map((item) => (
                  <tr key={item.id} className="border-t border-border hover:bg-panel-hover">
                    <td className="px-4 py-3 font-medium text-ink">{item.title ?? "—"}</td>
                    <td className="px-4 py-3 text-muted">
                      {brandsById[item.brand_id] ?? item.brand_id}
                    </td>
                    <td className="px-4 py-3 text-muted">
                      {item.content_type ? item.content_type.replace(/_/g, " ") : "—"}
                    </td>
                    <td className="px-4 py-3 text-muted tabular-nums">
                      {item.word_count ? item.word_count.toLocaleString() : "—"}
                    </td>
                    <td className="px-4 py-3 text-muted text-xs whitespace-nowrap">
                      {item.published_at ? new Date(item.published_at).toLocaleString() : "—"}
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
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => returnToReview.mutate(item.id)}
                        disabled={returnToReview.isPending}
                        title="Set the WordPress post back to draft and return this to Content Review"
                        className="px-3 py-1.5 border border-warning/40 text-warning rounded text-xs font-medium hover:bg-warning/5 disabled:opacity-50"
                      >
                        {returnToReview.isPending && returnToReview.variables === item.id
                          ? "Returning…"
                          : "Return to Review"}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <Pagination
          page={paged.page}
          pageSize={PAGE_SIZE}
          total={paged.total}
          onPage={paged.setPage}
          label="posts"
        />
      </div>

      {!isLoading && (data?.length ?? 0) > 0 && (
        <p className="text-xs text-muted/80">
          {items.length === (data?.length ?? 0)
            ? `${items.length} published post(s)`
            : `${items.length} of ${data?.length} post(s) match`}
        </p>
      )}
    </div>
  );
}
