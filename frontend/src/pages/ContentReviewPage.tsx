import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApprovalInbox } from "../components/ApprovalInbox";
import { QueryStatus } from "../components/QueryStatus";
import { apiFetch } from "../lib/api";
import type { ContentDraft } from "../types";

const STALE_GENERATING_MS = 3 * 60 * 1000;

function isStaleGenerating(draft: ContentDraft): boolean {
  if (draft.status !== "generating" || !draft.created_at) return false;
  return Date.now() - new Date(draft.created_at).getTime() > STALE_GENERATING_MS;
}

export function ContentReviewPage() {
  const queryClient = useQueryClient();

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["drafts"],
    queryFn: () => apiFetch<ContentDraft[]>("/api/content/drafts"),
    refetchInterval: (query) => {
      const drafts = query.state.data ?? [];
      return drafts.some((d) => d.status === "generating") ? 5000 : 30000;
    },
    retry: 1,
  });

  const retry = useMutation({
    mutationFn: (draftId: number) =>
      apiFetch(`/api/content/drafts/${draftId}/regenerate`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["drafts"] });
    },
  });

  const generating = (data ?? []).filter((d) => d.status === "generating");
  const staleGenerating = generating.filter(isStaleGenerating);
  const activeGenerating = generating.filter((d) => !isStaleGenerating(d));
  const reviewable = (data ?? []).filter((d) =>
    ["pending_review", "needs_review"].includes(d.status)
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-ink">Content Approval Inbox</h2>
          <p className="text-sm text-muted mt-1">
            Review and approve content before publishing to WordPress
          </p>
        </div>
        <span className="text-sm bg-warning/10 text-warning px-3 py-1 rounded-full font-medium">
          {reviewable.length} pending
          {activeGenerating.length > 0 ? ` · ${activeGenerating.length} generating` : ""}
        </span>
      </div>

      {activeGenerating.length > 0 && (
        <div className="bg-navy/5 border border-navy/15 rounded px-4 py-3 text-sm text-ink">
          <p className="font-medium">
            Claude is writing {activeGenerating.length} draft
            {activeGenerating.length === 1 ? "" : "s"}…
          </p>
          <p className="text-muted mt-1">
            Usually 2–4 minutes each (text + images).{" "}
            {activeGenerating.map((d) => d.title || d.target_query).join(" · ")}
          </p>
        </div>
      )}

      {staleGenerating.length > 0 && (
        <div className="bg-warning/10 border border-warning/25 rounded px-4 py-3 text-sm text-warning space-y-2">
          <p className="font-medium">
            {staleGenerating.length} draft(s) appear stuck (generation was interrupted).
          </p>
          <p className="text-muted">
            Refresh the page to move them to the inbox, or retry below.
          </p>
          <div className="flex flex-wrap gap-2">
            {staleGenerating.map((d) => (
              <button
                key={d.id}
                type="button"
                onClick={() => retry.mutate(d.id)}
                disabled={retry.isPending}
                className="px-3 py-1.5 bg-cyan text-void rounded text-xs font-medium hover:bg-cyan/90 disabled:opacity-50"
              >
                Retry: {d.title || d.target_query}
              </button>
            ))}
          </div>
          {retry.isError && (
            <p className="text-xs">{(retry.error as Error).message}</p>
          )}
        </div>
      )}

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
