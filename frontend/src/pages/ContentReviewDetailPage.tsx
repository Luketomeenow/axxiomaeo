import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ContentPreview } from "../components/ContentPreview";
import { SchemaPreview } from "../components/SchemaPreview";
import { ValidationPanel } from "../components/ValidationPanel";
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
    refetchInterval: (query) =>
      query.state.data?.status === "generating" ? 5000 : false,
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

  if (draft.status === "generating") {
    return (
      <div className="space-y-4">
        <h2 className="font-display text-xl font-bold text-navy">{draft.title || "Generating…"}</h2>
        <div className="bg-navy/5 border border-navy/15 rounded px-4 py-6 text-sm text-navy">
          <p className="font-medium">Claude is writing this draft (usually 1–2 minutes).</p>
          <p className="text-black/50 mt-2">This page will refresh automatically when the preview is ready.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="font-display text-xl font-bold text-navy">{draft.title}</h2>
          <p className="text-sm text-black/50 mt-1">
            {draft.brand_id} · {draft.content_type}
          </p>
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

      <ValidationPanel
        validationResult={draft.validation_result}
        validationAttempts={draft.validation_attempts}
        targetQuery={draft.target_query}
      />

      <div className="grid lg:grid-cols-2 gap-6 min-h-[500px]">
        <ContentPreview html={draft.html_content} validationResult={draft.validation_result} />
        <SchemaPreview schemaJson={draft.schema_json} />
      </div>
    </div>
  );
}
