import { useQuery } from "@tanstack/react-query";
import { ApprovalInbox } from "../components/ApprovalInbox";
import { QueryStatus } from "../components/QueryStatus";
import { apiFetch } from "../lib/api";
import type { ContentDraft } from "../types";

export function ContentReviewPage() {
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["drafts"],
    queryFn: () => apiFetch<ContentDraft[]>("/api/content/drafts"),
    refetchInterval: 30000,
    retry: 1,
  });

  const reviewable = (data ?? []).filter((d) =>
    ["pending_review", "needs_review"].includes(d.status)
  );

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
          {reviewable.length} pending
        </span>
      </div>
      <QueryStatus
        isLoading={isLoading}
        isError={isError}
        error={error as Error | null}
        loadingText="Loading drafts…"
      >
        <ApprovalInbox drafts={reviewable} />
      </QueryStatus>
    </div>
  );
}
