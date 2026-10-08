import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Pagination, usePaged } from "../components/Pagination";
import { apiFetch } from "../lib/api";
import type { Brand, CallQuestionScanResult, CustomerQuestion } from "../types";

const PAGE_SIZE = 20;

function fmtDate(iso?: string | null): string {
  if (!iso) return "—";
  return new Date(iso.endsWith("Z") ? iso : iso + "Z").toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

export function CustomerQuestionsPage() {
  const queryClient = useQueryClient();
  const [brandId, setBrandId] = useState("");
  const [search, setSearch] = useState("");
  const [scan, setScan] = useState<CallQuestionScanResult | null>(null);

  const { data: brands } = useQuery({
    queryKey: ["brands"],
    queryFn: () => apiFetch<Brand[]>("/api/brands"),
  });
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["customer-questions", brandId],
    queryFn: () =>
      apiFetch<{ questions: CustomerQuestion[] }>(
        `/api/customer-questions${brandId ? `?brand_id=${encodeURIComponent(brandId)}` : ""}`,
      ),
  });

  const [backfillStarted, setBackfillStarted] = useState(false);
  const backfill = useMutation({
    mutationFn: () => apiFetch("/api/customer-questions/scan?days=30", { method: "POST" }),
    onSuccess: () => setBackfillStarted(true),
  });
  const runScan = useMutation({
    mutationFn: () =>
      apiFetch<CallQuestionScanResult>("/api/customer-questions/scan", { method: "POST" }),
    onSuccess: (result) => {
      setScan(result);
      queryClient.invalidateQueries({ queryKey: ["customer-questions"] });
    },
  });
  const remove = useMutation({
    mutationFn: (id: number) => apiFetch(`/api/customer-questions/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["customer-questions"] }),
  });

  const rows = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (data?.questions ?? []).filter((q) => !term || q.question.toLowerCase().includes(term));
  }, [data, search]);
  const paged = usePaged(rows, PAGE_SIZE);
  const setPage = paged.setPage;

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-xl font-bold text-ink">Customer Questions</h2>
          <p className="text-sm text-muted mt-1 max-w-2xl">
            Questions real customers asked on phone calls (from CallRail's call summaries, scanned
            every morning at 7:15) and any sent in from chats and forms. Names, numbers and
            addresses are removed and each question is reworded in general terms. Topic discovery
            picks these first, ahead of Search Console, and the weekly AI audit checks whether
            ChatGPT, Gemini and Perplexity cite us for them. Remove any that shouldn't be used.
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          <button
            type="button"
            onClick={() => backfill.mutate()}
            disabled={backfill.isPending || backfillStarted}
            title="One-time: read the last 30 days of call summaries in the background"
            className="px-3 py-1.5 border border-border text-muted rounded text-sm hover:border-cyan hover:text-ink disabled:opacity-50"
          >
            {backfillStarted ? "Backfill running…" : "Backfill 30 days"}
          </button>
          <button
            type="button"
            onClick={() => runScan.mutate()}
            disabled={runScan.isPending}
            className="px-3 py-1.5 border border-border text-ink rounded text-sm hover:border-cyan disabled:opacity-50"
          >
            {runScan.isPending ? "Scanning calls…" : "Scan calls now"}
          </button>
        </div>
      </div>

      {backfillStarted && (
        <p className="text-xs text-muted">
          Reading the last 30 days of call summaries in the background. It takes a few minutes; the
          result appears in Notifications, then refresh this page.
        </p>
      )}
      {backfill.isError && <p className="text-sm text-red-400">{(backfill.error as Error).message}</p>}

      {runScan.isError && (
        <p className="text-sm text-red-400">{(runScan.error as Error).message}</p>
      )}
      {scan && (
        <div className="text-xs bg-void border border-border rounded px-3 py-2 text-muted">
          {scan.status === "ok" ? (
            <>
              Read {scan.calls_scanned ?? 0} new call summar{scan.calls_scanned === 1 ? "y" : "ies"}{" "}
              ({scan.already_scanned ?? 0} already scanned) and found {scan.questions_found ?? 0}{" "}
              question(s): {scan.stored ?? 0} new, {scan.duplicates ?? 0} already known
              {scan.out_of_market ? `, ${scan.out_of_market} outside the brand's markets` : ""}.
            </>
          ) : (
            <span className="text-warning">{scan.message}</span>
          )}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <select
          value={brandId}
          onChange={(e) => {
            setBrandId(e.target.value);
            setPage(1);
          }}
          className="bg-panel border border-border rounded px-3 py-1.5 text-sm text-ink focus:outline-none focus:border-cyan/50"
          aria-label="Brand"
        >
          <option value="">All brands</option>
          {(brands ?? []).map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
            </option>
          ))}
        </select>
        <input
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          placeholder="Search questions"
          className="bg-panel border border-border rounded px-3 py-1.5 text-sm text-ink focus:outline-none focus:border-cyan/50 w-64"
        />
      </div>

      <div className="aeo-panel overflow-hidden">
        {isLoading ? (
          <p className="px-5 py-8 text-sm text-muted text-center">Loading questions…</p>
        ) : isError ? (
          <p className="px-5 py-6 text-sm text-warning">{(error as Error)?.message}</p>
        ) : rows.length === 0 ? (
          <p className="px-5 py-8 text-sm text-muted/80 text-center">
            No customer questions yet. Click "Scan calls now" or wait for the 7:15am scan.
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted">
                <th className="px-4 py-3">Question</th>
                <th className="px-4 py-3">Brand</th>
                <th className="px-4 py-3">From</th>
                <th className="px-4 py-3">Asked</th>
                <th className="px-4 py-3">Topic</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {paged.slice.map((q) => (
                <tr key={q.id} className="border-t border-border align-top">
                  <td className="px-4 py-2.5 text-ink">
                    {q.question}
                    {q.intent && <span className="ml-2 text-[11px] text-muted">{q.intent}</span>}
                  </td>
                  <td className="px-4 py-2.5 text-muted">{q.brand_id}</td>
                  <td className="px-4 py-2.5 text-muted">
                    {q.source ?? "—"}
                    {q.call_source && <span className="block text-[11px]">{q.call_source}</span>}
                  </td>
                  <td className="px-4 py-2.5 text-muted tabular-nums">{fmtDate(q.asked_at ?? q.created_at)}</td>
                  <td className="px-4 py-2.5 text-muted">
                    {q.topic ? (
                      <Link to="/content/queue" className="text-cyan hover:underline">
                        {q.topic.status}
                      </Link>
                    ) : (
                      "not yet"
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <button
                      type="button"
                      onClick={() => remove.mutate(q.id)}
                      disabled={remove.isPending}
                      className="px-2 py-1 border border-border rounded text-xs text-muted hover:text-red-400 hover:border-red-500/40 disabled:opacity-50"
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <Pagination page={paged.page} pageSize={paged.pageSize} total={paged.total} onPage={setPage} label="questions" />
    </div>
  );
}
