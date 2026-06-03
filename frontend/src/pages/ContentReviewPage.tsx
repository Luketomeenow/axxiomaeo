import { useQuery } from "@tanstack/react-query";
import { ApprovalInbox } from "../components/ApprovalInbox";
import { apiFetch } from "../lib/api";
import type { ContentDraft } from "../types";

export function ContentReviewPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["drafts", "review"],
    queryFn: () =>
      apiFetch<ContentDraft[]>("/api/content/drafts?status=pending_review"),
    refetchInterval: 30000,
  });

  const needsReview = useQuery({
    queryKey: ["drafts", "needs_review"],
    queryFn: () =>
      apiFetch<ContentDraft[]>("/api/content/drafts?status=needs_review"),
  });

  const allDrafts = [...(data ?? []), ...(needsReview.data ?? [])];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-display text-xl font-bold text-navy">Content Approval Inbox</h2>
          <p className="text-sm text-black/50 mt-1">
            Review and approve content before publishing to WordPress
          </p>
        </div>
        <span className="text-sm bg-orange/10 text-orange px-3 py-1 rounded-full font-medium">
          {allDrafts.length} pending
        </span>
      </div>
      {isLoading ? (
        <p className="text-black/50">Loading drafts…</p>
      ) : (
        <ApprovalInbox drafts={allDrafts} />
      )}
    </div>
  );
}
