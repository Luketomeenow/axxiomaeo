import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { SchemaPreview } from "../components/SchemaPreview";
import { ValidationPanel } from "../components/ValidationPanel";
import { apiFetch } from "../lib/api";
import type { ApprovePublishResponse, Brand, ContentDraftDetail } from "../types";

type PublishMode = "draft" | "selected" | "all";

export function ContentReviewDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [rejectNotes, setRejectNotes] = useState("");
  const [showReject, setShowReject] = useState(false);
  const [publishMode, setPublishMode] = useState<PublishMode>("draft");
  const [selectedBrandId, setSelectedBrandId] = useState("");
  const [publishResults, setPublishResults] = useState<{ brand_id: string; url: string }[]>([]);
  const [editedHtml, setEditedHtml] = useState("");
  const [htmlDirty, setHtmlDirty] = useState(false);
  const [saveHtmlMsg, setSaveHtmlMsg] = useState("");
  const [regenMsg, setRegenMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);

  const { data: brands } = useQuery({
    queryKey: ["brands"],
    queryFn: () => apiFetch<Brand[]>("/api/brands"),
  });

  const { data: draft, isLoading } = useQuery({
    queryKey: ["draft", id],
    queryFn: () => apiFetch<ContentDraftDetail>(`/api/content/drafts/${id}`),
    enabled: !!id,
    refetchInterval: (query) =>
      query.state.data?.status === "generating" ? 5000 : false,
  });

  const configuredBrands = useMemo(
    () => brands?.filter((b) => b.wp_publish_configured) ?? [],
    [brands],
  );

  const draftBrand = brands?.find((b) => b.id === draft?.brand_id);

  const approve = useMutation({
    mutationFn: () => {
      const body =
        publishMode === "all"
          ? { publish_all: true }
          : publishMode === "selected"
            ? { brand_ids: [selectedBrandId || draft?.brand_id] }
            : {};

      return apiFetch<ApprovePublishResponse>(`/api/content/drafts/${id}/approve`, {
        method: "POST",
        body: JSON.stringify(body),
      });
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["drafts"] });
      queryClient.invalidateQueries({ queryKey: ["published-content"] });
      const lines = data.results
        .filter((r) => !r.error && r.post_url)
        .map((r) => ({ brand_id: r.brand_id, url: r.post_url! }));
      setPublishResults(lines);
      const failures = data.results.filter((r) => r.error);
      if (failures.length === 0) {
        setTimeout(() => navigate("/content/published"), 4000);
      }
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
      setHtmlDirty(false);
      setEditedHtml("");
      setRegenMsg({
        type: "ok",
        text: "Regeneration started — this page updates automatically (usually 2–4 minutes).",
      });
      // Optimistically flip to "generating" so the progress view + 5s polling
      // start immediately instead of racing the background task's status update
      // (which is why it could look like nothing happened).
      queryClient.setQueryData<ContentDraftDetail>(["draft", id], (old) =>
        old ? { ...old, status: "generating" } : old,
      );
      queryClient.invalidateQueries({ queryKey: ["drafts"] });
    },
    onError: (e: Error) => setRegenMsg({ type: "err", text: e.message || "Regenerate failed." }),
  });

  const saveHtml = useMutation({
    mutationFn: (html: string) =>
      apiFetch(`/api/content/drafts/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ html_content: html }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["draft", id] });
      setHtmlDirty(false);
      setSaveHtmlMsg("Content saved and re-validated.");
      setTimeout(() => setSaveHtmlMsg(""), 3000);
    },
    onError: (e: Error) => setSaveHtmlMsg(e.message),
  });


  if (isLoading) return <p className="text-muted">Loading…</p>;
  if (!draft) return <p className="text-warning">Draft not found</p>;

  const canPublish =
    draft.validation_result?.valid !== false &&
    ((publishMode === "draft" && !!draftBrand?.wp_publish_configured) ||
      (publishMode === "selected" &&
        !!selectedBrandId &&
        !!brands?.find((b) => b.id === selectedBrandId)?.wp_publish_configured) ||
      (publishMode === "all" && configuredBrands.length > 0));

  const displayHtml = htmlDirty ? editedHtml : (draft.html_content ?? "");

  if (draft.status === "generating") {
    return (
      <div className="space-y-4">
        <h2 className="text-xl font-bold text-ink">{draft.title || "Generating…"}</h2>
        <div className="bg-navy/5 border border-navy/15 rounded px-4 py-6 text-sm text-ink">
          <p className="font-medium">Claude is writing this draft (usually 2–4 minutes with images).</p>
          <p className="text-muted mt-2">This page will refresh automatically when the preview is ready.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-ink">{draft.title}</h2>
          <p className="text-sm text-muted mt-1">
            Draft brand: {draftBrand?.name ?? draft.brand_id} · {draft.content_type}
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          <button
            type="button"
            onClick={() => regenerate.mutate()}
            disabled={regenerate.isPending}
            className="aeo-btn-secondary"
          >
            {regenerate.isPending ? "Regenerating…" : "Regenerate"}
          </button>
          <button
            onClick={() => setShowReject(true)}
            className="px-4 py-2 border border-warning/40 text-warning rounded text-sm hover:bg-warning/5"
          >
            Reject
          </button>
          <button
            type="button"
            onClick={() => approve.mutate()}
            disabled={approve.isPending || !canPublish}
            className="px-4 py-2 bg-cyan text-void rounded text-sm hover:bg-cyan/90 disabled:opacity-50"
          >
            {approve.isPending ? "Publishing…" : "Approve & Publish"}
          </button>
        </div>
      </div>

      {regenMsg && (
        <div
          className={`text-sm px-4 py-3 rounded border ${
            regenMsg.type === "ok"
              ? "bg-success/10 border-success/25 text-success"
              : "bg-warning/10 border-warning/30 text-warning"
          }`}
        >
          {regenMsg.text}
        </div>
      )}

      <div className="bg-panel-elevated border border-black/10 rounded p-4 space-y-3">
        <p className="text-sm font-medium text-ink">Publish destination</p>
        <div className="flex flex-col gap-2 text-sm">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="publishMode"
              checked={publishMode === "draft"}
              onChange={() => setPublishMode("draft")}
            />
            <span>
              Draft brand — {draftBrand?.name ?? draft.brand_id}
              {!draftBrand?.wp_publish_configured && (
                <span className="text-warning ml-1">(no WP credentials in backend)</span>
              )}
            </span>
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="publishMode"
              checked={publishMode === "selected"}
              onChange={() => {
                setPublishMode("selected");
                if (!selectedBrandId && configuredBrands[0]) {
                  setSelectedBrandId(configuredBrands[0].id);
                }
              }}
            />
            <span>Choose brand</span>
          </label>
          {publishMode === "selected" && (
            <select
              value={selectedBrandId}
              onChange={(e) => setSelectedBrandId(e.target.value)}
              className="ml-6 border border-border rounded px-3 py-2 text-sm max-w-xs"
            >
              <option value="">Select brand…</option>
              {brands?.map((b) => (
                <option key={b.id} value={b.id} disabled={!b.wp_publish_configured}>
                  {b.name}
                  {!b.wp_publish_configured ? " (not configured)" : ""}
                </option>
              ))}
            </select>
          )}
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name="publishMode"
              checked={publishMode === "all"}
              onChange={() => setPublishMode("all")}
            />
            <span>
              All configured brands ({configuredBrands.length})
              {configuredBrands.length === 0 && (
                <span className="text-warning ml-1">— add WP app passwords in backend .env</span>
              )}
            </span>
          </label>
        </div>
        <p className="text-xs text-muted">
          Use “Choose brand” to test on Quality Elevator while the draft was generated for another brand.
          Schema and phone numbers are adjusted for each target site.
        </p>
      </div>

      {approve.isError && (
        <div className="bg-warning/10 border border-warning/25 rounded px-4 py-3 text-sm text-warning">
          {(approve.error as Error)?.message ?? "Publish failed"}
        </div>
      )}

      {publishResults.length > 0 && (
        <div className="bg-success/10 border border-success/25 rounded px-4 py-3 text-sm space-y-2">
          <p className="font-medium text-ink">Published successfully</p>
          <ul className="space-y-1">
            {publishResults.map((r) => (
              <li key={r.brand_id}>
                <span className="text-muted">{r.brand_id}: </span>
                <a
                  href={r.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-ink hover:text-cyan font-medium break-all"
                >
                  {r.url}
                </a>
              </li>
            ))}
          </ul>
          <p className="text-xs text-muted">
            Redirecting to{" "}
            <Link to="/content/published" className="text-ink hover:text-cyan font-medium">
              Published Content
            </Link>
            …
          </p>
        </div>
      )}

      {showReject && (
        <div className="bg-panel-elevated border border-warning/25 rounded p-4 space-y-3">
          <textarea
            value={rejectNotes}
            onChange={(e) => setRejectNotes(e.target.value)}
            placeholder="Rejection notes (optional)"
            className="aeo-input h-20"
          />
          <div className="flex gap-2">
            <button
              onClick={() => reject.mutate()}
              disabled={reject.isPending}
              className="px-4 py-2 bg-cyan text-void rounded text-sm"
            >
              Confirm Reject
            </button>
            <button onClick={() => setShowReject(false)} className="px-4 py-2 text-sm text-muted">
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

      {draft.images_json && draft.images_json.length > 0 && (
        <div className="aeo-panel p-4 space-y-3">
          <h3 className="aeo-title">Generated images</h3>
          <p className="text-xs text-muted">
            Uploaded to WordPress media library with AEO alt text and captions.
          </p>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {draft.images_json.map((img) => (
              <div key={img.slot} className="border border-border rounded-lg overflow-hidden bg-panel">
                <img
                  src={img.url}
                  alt={img.alt}
                  title={img.title}
                  className="w-full h-36 object-cover"
                />
                <div className="p-3 space-y-1 text-xs">
                  <p className="aeo-badge-info inline-block">{img.slot}</p>
                  <p className="text-muted">
                    <span className="font-medium text-ink/80">Alt:</span> {img.alt}
                  </p>
                  <p className="text-muted">
                    <span className="font-medium text-ink/80">Caption:</span> {img.caption}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {saveHtmlMsg && (
        <p className="text-sm text-ink bg-void px-3 py-2 rounded border border-border">{saveHtmlMsg}</p>
      )}

      {draft.validation_result?.valid === false && (
        <p className="text-sm text-warning bg-orange/10 px-3 py-2 rounded border border-warning/20">
          Validation failed — edit content below or regenerate before publishing.
        </p>
      )}

      <div className="grid lg:grid-cols-2 gap-6 min-h-[500px]">
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-medium text-ink">HTML content (editable)</h3>
            <button
              type="button"
              disabled={!htmlDirty || saveHtml.isPending}
              onClick={() => saveHtml.mutate(editedHtml)}
              className="text-xs px-3 py-1 border border-navy text-ink rounded disabled:opacity-50"
            >
              {saveHtml.isPending ? "Saving…" : "Save HTML"}
            </button>
          </div>
          <textarea
            className="aeo-code-editor min-h-[500px]"
            value={displayHtml}
            onChange={(e) => {
              setEditedHtml(e.target.value);
              setHtmlDirty(true);
            }}
            spellCheck={false}
          />
        </div>
        <SchemaPreview schemaJson={draft.schema_json} />
      </div>
    </div>
  );
}
