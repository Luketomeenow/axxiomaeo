import { Link } from "react-router-dom";
import type { ContentDraft } from "../types";

export function ApprovalInbox({
  drafts,
  linkPrefix = "/content/review",
}: {
  drafts: ContentDraft[];
  linkPrefix?: string;
}) {
  return (
    <div className="bg-white rounded border border-black/8 overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-black/8 text-left text-black/50">
            <th className="px-4 py-3 font-medium">Title</th>
            <th className="px-4 py-3 font-medium">Brand</th>
            <th className="px-4 py-3 font-medium">Type</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">Validation</th>
            <th className="px-4 py-3 font-medium"></th>
          </tr>
        </thead>
        <tbody>
          {drafts.length === 0 ? (
            <tr>
              <td colSpan={6} className="px-4 py-8 text-center text-black/40">
                No items awaiting review
              </td>
            </tr>
          ) : (
            drafts.map((d) => (
              <tr key={d.id} className="border-t border-black/5 hover:bg-cream/50">
                <td className="px-4 py-3 font-medium">{d.title}</td>
                <td className="px-4 py-3 text-black/60">{d.brand_id}</td>
                <td className="px-4 py-3 text-black/60">{d.content_type}</td>
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
                    <span className="text-green-700 text-xs">✓ Valid</span>
                  ) : (
                    <span className="text-orange text-xs">⚠ Needs attention</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <Link
                    to={`${linkPrefix}/${d.id}`}
                    className="text-navy text-xs font-medium hover:text-orange"
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
  );
}
