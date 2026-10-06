import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { apiFetch } from "../lib/api";
import type { CtaRefreshResult } from "../types";

function fmtNumber(d10: string): string {
  return d10.length === 10 ? `${d10.slice(0, 3)}-${d10.slice(3, 6)}-${d10.slice(6)}` : d10;
}

/** Brings the call box and phone number on a brand's published posts in line
 * with Brand Settings: check first (read-only), then update on WordPress in
 * batches after an explicit confirmation. */
export function CtaRefreshPanel({ brandId, unsavedPhone }: { brandId: string; unsavedPhone: boolean }) {
  const [preview, setPreview] = useState<CtaRefreshResult | null>(null);
  const [extraNumbers, setExtraNumbers] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [progress, setProgress] = useState<{ updated: number; total: number; errors: string[] } | null>(
    null,
  );
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  const oldNumbers = extraNumbers
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  const call = (apply: boolean) =>
    apiFetch<CtaRefreshResult>(`/api/brands/${brandId}/cta-refresh`, {
      method: "POST",
      body: JSON.stringify({ apply, limit: 20, old_numbers: oldNumbers }),
    });

  const check = useMutation({
    mutationFn: () => call(false),
    onSuccess: (r) => {
      setPreview(r);
      setProgress(null);
      setError("");
    },
    onError: (e: Error) => setError(e.message),
  });

  const apply = async () => {
    if (!preview) return;
    setConfirming(false);
    setRunning(true);
    setError("");
    const total = preview.posts_to_update;
    let updated = 0;
    const errors: string[] = [];
    try {
      // Each call updates up to 20 posts; stop when nothing is left or a
      // batch makes no progress (the same posts keep failing).
      for (let i = 0; i < 100; i++) {
        const r = await call(true);
        updated += r.updated;
        errors.push(...r.errors.map((e) => `${e.title ?? "post"}: ${e.error}`));
        setProgress({ updated, total, errors: [...errors] });
        if (r.remaining === 0 || r.updated === 0) break;
      }
      setPreview(await call(false));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRunning(false);
    }
  };

  const found = Object.entries(preview?.old_numbers ?? {});

  return (
    <div className="aeo-panel p-6 space-y-3">
      <div>
        <h3 className="text-sm font-semibold text-ink">Phone number and call box on published posts</h3>
        <p className="text-xs text-muted mt-1">
          Each post's call box is written with the phone saved at the time. After changing the phone
          above, check the posts, then update them so every call button uses the current number and
          the brand's contact page. Other numbers in the articles are left alone.
        </p>
      </div>
      <div>
        <label className="block text-xs font-medium text-muted mb-1">
          Also replace these old numbers (optional, comma-separated)
        </label>
        <input
          type="text"
          value={extraNumbers}
          onChange={(e) => setExtraNumbers(e.target.value)}
          placeholder="Only needed for a number that appears outside the call box"
          className="w-full border border-border rounded px-3 py-2 text-sm"
        />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => check.mutate()}
          disabled={check.isPending || running || unsavedPhone}
          title={unsavedPhone ? "Save the new phone first" : undefined}
          className="px-3 py-2 border border-border rounded text-xs text-ink hover:border-cyan disabled:opacity-50"
        >
          {check.isPending ? "Checking posts…" : "Check posts"}
        </button>
        {unsavedPhone && <span className="text-xs text-warning">Save the phone change first.</span>}
      </div>
      {error && <p className="text-xs text-red-400">{error}</p>}

      {preview && (
        <div className="text-xs space-y-2 bg-void border border-border rounded p-3">
          <p className="text-ink">
            {preview.posts_to_update === 0
              ? `All ${preview.published_posts} published posts are current.`
              : `${preview.posts_to_update} of ${preview.published_posts} published posts need an update.`}
          </p>
          {!!found.length && (
            <p className="text-muted">
              Old numbers found:{" "}
              {found.map(([d, n]) => `${fmtNumber(d)} (${n} post${n === 1 ? "" : "s"})`).join(", ")} → will
              become {preview.phone || "no number (call buttons removed)"}.
            </p>
          )}
          <p className="text-muted">
            Quote link: {preview.contact_url ? preview.contact_url : "no contact page found, so none is added"}.
          </p>
          {!!preview.posts_without_stored_html && (
            <p className="text-muted">
              {preview.posts_without_stored_html} post(s) have no stored HTML and are skipped; edit those in
              WordPress.
            </p>
          )}
          {!!preview.samples.length && (
            <ul className="text-muted list-disc pl-4">
              {preview.samples.map((s, i) => (
                <li key={i}>
                  {s.url ? (
                    <a href={s.url} target="_blank" rel="noreferrer" className="text-cyan hover:underline">
                      {s.title || s.url}
                    </a>
                  ) : (
                    s.title
                  )}
                </li>
              ))}
            </ul>
          )}
          {preview.posts_to_update > 0 && !confirming && !running && (
            <button
              type="button"
              onClick={() => setConfirming(true)}
              className="px-3 py-1.5 rounded bg-cyan/15 text-cyan border border-cyan/30 hover:bg-cyan/25"
            >
              Update {preview.posts_to_update} posts on WordPress
            </button>
          )}
          {confirming && (
            <div className="border border-cyan/30 rounded p-2 space-y-2">
              <p className="text-ink">
                This rewrites the call box (and the old numbers) in {preview.posts_to_update} live posts
                on the brand's WordPress site, plus each post's schema. It runs in batches of 20.
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={apply}
                  className="px-3 py-1.5 rounded font-medium bg-cyan text-void hover:opacity-90"
                >
                  Confirm and update
                </button>
                <button
                  type="button"
                  onClick={() => setConfirming(false)}
                  className="px-3 py-1.5 rounded border border-border text-muted hover:text-ink"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
          {progress && (
            <p className={running ? "text-cyan" : "text-success"}>
              {running ? "Updating… " : "Done: "}
              {progress.updated} of {progress.total} posts updated
              {progress.errors.length ? `, ${progress.errors.length} failed` : ""}.
            </p>
          )}
          {!!progress?.errors.length && (
            <ul className="text-red-400 list-disc pl-4">
              {progress.errors.slice(0, 5).map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
