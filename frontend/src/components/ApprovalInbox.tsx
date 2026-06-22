import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../lib/api";
import type { Brand, ContentDraft } from "../types";

const PRIORITY_LABEL: Record<number, string> = {
  1: "CRITICAL",
  3: "HIGH",
  5: "MEDIUM",
};

const PRIORITY_CLASS: Record<number, string> = {
  1: "bg-red-100 text-red-700",
  3: "bg-yellow-100 text-yellow-800",
  5: "bg-gray-100 text-gray-600",
};

type StatusFilter = "all" | "pending_review" | "needs_review";

export function ApprovalInbox({
  drafts,
  linkPrefix = "/content/review",
}: {
  drafts: ContentDraft[];
  linkPrefix?: string;
}) {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [brandFilter, setBrandFilter] = useState<string>("all");

  const { data: brands } = useQuery({
    queryKey: ["brands"],
    queryFn: () => apiFetch<Brand[]>("/api/brands"),
  });

  const filtered = useMemo(() => {
    return drafts.filter((d) => {
      if (statusFilter !== "all" && d.status !== statusFilter) return false;
      if (brandFilter !== "all" && d.brand_id !== brandFilter) return false;
      return true;
    });
  }, [drafts, statusFilter, brandFilter]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex rounded border border-black/10 overflow-hidden text-xs">
          {(
            [
              ["all", "All"],
              ["pending_review", "Pending Review"],
              ["needs_review", "Needs Review"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => setStatusFilter(value)}
              className={`px-3 py-1.5 ${
                statusFilter === value ? "bg-cyan text-void" : "bg-panel-elevated text-muted hover:bg-void"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <select
          value={brandFilter}
          onChange={(e) => setBrandFilter(e.target.value)}
          className="text-xs border border-border rounded px-2 py-1.5 bg-panel-elevated"
        >
          <option value="all">All brands</option>
          {brands?.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </select>
        <span className="text-xs text-muted/80">{filtered.length} items</span>
      </div>

      <div className="aeo-panel overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-muted">
              <th className="px-4 py-3 font-medium">Title</th>
              <th className="px-4 py-3 font-medium">Brand</th>
              <th className="px-4 py-3 font-medium">Type</th>
              <th className="px-4 py-3 font-medium">Priority</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Validation</th>
              <th className="px-4 py-3 font-medium">Created</th>
              <th className="px-4 py-3 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-muted/80">
                  No items match filters
                </td>
              </tr>
            ) : (
              filtered.map((d) => (
                <tr key={d.id} className="border-t border-border hover:bg-panel-hover">
                  <td className="px-4 py-3 font-medium">{d.title}</td>
                  <td className="px-4 py-3 text-muted">{d.brand_id}</td>
                  <td className="px-4 py-3 text-muted">{d.content_type}</td>
                  <td className="px-4 py-3">
                    {d.priority ? (
                      <span
                        className={`text-xs px-2 py-0.5 rounded font-medium ${PRIORITY_CLASS[d.priority] || PRIORITY_CLASS[5]}`}
                      >
                        {PRIORITY_LABEL[d.priority] || "MEDIUM"}
                      </span>
                    ) : (
                      <span className="text-muted/50">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`text-xs px-2 py-0.5 rounded ${
                        d.status === "pending_review"
                          ? "bg-yellow-100 text-yellow-800"
                          : d.status === "needs_review"
                            ? "bg-red-100 text-red-700"
                            : "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {d.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {d.validation_result?.valid ? (
                      <span className="text-success text-xs">Valid</span>
                    ) : (
                      <span className="text-warning text-xs">Needs attention</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-muted text-xs">
                    {d.created_at ? new Date(d.created_at).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      to={`${linkPrefix}/${d.id}`}
                      className="text-ink text-xs font-medium hover:text-cyan"
                    >
                      Review →
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
