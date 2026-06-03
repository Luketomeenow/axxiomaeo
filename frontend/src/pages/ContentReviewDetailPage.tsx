import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiFetch } from "../lib/api";
import type { ContentDraftDetail } from "../types";

export function ContentReviewDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [rejectNotes, setRejectNotes] = useState("");
  const [showReject, setShowReject] = useState(false);

  const { data: draft, isLoading } = useQuery({
    queryKey: ["draft", id],
    queryFn: () => apiFetch<ContentDraftDetail>(`/api/content/drafts/${id}`),
    enabled: !!id,
  });

  const approve = useMutation({
    mutationFn: () =>
      apiFetch(`/api/content/drafts/${id}/approve`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["drafts"] });
      navigate("/content/review");
    },
  });

  const reject = useMutation({
    mutationFn: () =>
      apiFetch(`/api/content/drafts/${id}/reject`, {
        method: "POST",
        body: JSON.stringify({ notes: rejectNotes }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["drafts"] });
      navigate("/content/review");
    },
  });

  const regenerate = useMutation({
    mutationFn: () =>
      apiFetch(`/api/content/drafts/${id}/regenerate`, { method: "POST" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["draft", id] });
    },
  });

  if (isLoading) return <p className="text-black/50">Loading…</p>;
  if (!draft) return <p className="text-orange">Draft not found</p>;

  const wordCount = draft.html_content
    ? draft.html_content.replace(/<[^>]+>/g, " ").split(/\s+/).filter(Boolean).length
    : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="font-display text-xl font-bold text-navy">{draft.title}</h2>
          <p className="text-sm text-black/50 mt-1">
            {draft.brand_id} · {draft.content_type} · {wordCount} words
          </p>
          {draft.validation_result && (
            <p
              className={`text-xs mt-2 ${draft.validation_result.valid ? "text-green-700" : "text-orange"}`}
            >
              Validation: {draft.validation_result.valid ? "Passed" : draft.validation_result.reason}
            </p>
          )}
        </div>
        <div className="flex gap-2 shrink-0">
          <button
            onClick={() => regenerate.mutate()}
            disabled={regenerate.isPending}
            className="px-4 py-2 border border-navy text-navy rounded text-sm hover:bg-navy/5"
          >
            Regenerate
          </button>
          <button
            onClick={() => setShowReject(true)}
            className="px-4 py-2 border border-orange text-orange rounded text-sm hover:bg-orange/5"
          >
            Reject
          </button>
          <button
            onClick={() => approve.mutate()}
            disabled={approve.isPending}
            className="px-4 py-2 bg-navy text-white rounded text-sm hover:bg-navy/90 disabled:opacity-50"
          >
            {approve.isPending ? "Publishing…" : "Approve & Publish"}
          </button>
        </div>
      </div>

      {showReject && (
        <div className="bg-white border border-orange/30 rounded p-4 space-y-3">
          <textarea
            value={rejectNotes}
            onChange={(e) => setRejectNotes(e.target.value)}
            placeholder="Rejection notes (optional)"
            className="w-full border border-black/15 rounded px-3 py-2 text-sm h-20"
          />
          <div className="flex gap-2">
            <button
              onClick={() => reject.mutate()}
              disabled={reject.isPending}
              className="px-4 py-2 bg-orange text-white rounded text-sm"
            >
              Confirm Reject
            </button>
            <button onClick={() => setShowReject(false)} className="px-4 py-2 text-sm text-black/50">
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="grid lg:grid-cols-2 gap-6">
        <div className="bg-white rounded border border-black/8 overflow-hidden">
          <div className="px-4 py-3 border-b border-black/8 bg-cream">
            <h3 className="text-sm font-medium text-navy">Content Preview</h3>
          </div>
          <div
            className="p-6 prose prose-sm max-w-none overflow-auto max-h-[600px]"
            dangerouslySetInnerHTML={{ __html: draft.html_content || "<p>No content</p>" }}
          />
        </div>
        <div className="bg-white rounded border border-black/8 overflow-hidden">
          <div className="px-4 py-3 border-b border-black/8 bg-cream">
            <h3 className="text-sm font-medium text-navy">Schema JSON-LD</h3>
          </div>
          <pre className="p-4 text-xs overflow-auto max-h-[600px] bg-gray-50 text-navy">
            {draft.schema_json
              ? (() => {
                  try {
                    return JSON.stringify(JSON.parse(draft.schema_json), null, 2);
                  } catch {
                    return draft.schema_json;
                  }
                })()
              : "No schema generated"}
          </pre>
        </div>
      </div>
    </div>
  );
}
