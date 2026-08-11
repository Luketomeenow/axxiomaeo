import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { apiFetch } from "../lib/api";
import type { FlowHealth, FlowStage, WorkerErrorItem, WpTestResult } from "../types";

const STATUS_STYLE: Record<string, { dot: string; panel: string; label: string }> = {
  ok: { dot: "bg-success", panel: "border-success/25", label: "text-success" },
  warn: { dot: "bg-warning", panel: "border-warning/40", label: "text-warning" },
  fail: { dot: "bg-red-500", panel: "border-red-500/50", label: "text-red-400" },
};

function fmtTime(iso?: string | null): string {
  if (!iso) return "—";
  return new Date(iso.endsWith("Z") ? iso : iso + "Z").toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function MetricChips({ stage }: { stage: FlowStage }) {
  const m = stage.metrics ?? {};
  const chips: string[] = [];
  if (stage.key === "discovery") {
    chips.push(`${m.queued_today ?? 0} queued today`);
    for (const [src, n] of Object.entries(m.by_source ?? {})) chips.push(`${src}: ${n}`);
  }
  if (stage.key === "generation") {
    chips.push(`${m.drafts_today ?? 0} drafts today`);
    if (m.stuck_in_progress) chips.push(`${m.stuck_in_progress} stuck`);
    if (m.stranded?.length) chips.push(`${m.stranded.length} stranded`);
  }
  if (stage.key === "publish") {
    chips.push(`${m.published_today ?? 0} published today`);
    for (const [b, n] of Object.entries(m.by_brand ?? {})) chips.push(`${b}: ${n}`);
  }
  if (stage.key === "errors") chips.push(`${m.last_24h ?? 0} in 24h`);
  if (stage.key === "integrations") {
    chips.push(`GSC credential: ${m.gsc_credential ? "✓" : "✗"}`);
    chips.push(`Citation provider: ${m.citation_provider ? "✓" : "✗"}`);
    chips.push(`Discord: ${m.discord_webhook ? "✓" : "✗"}`);
  }
  if (!chips.length) return null;
  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {chips.map((c, i) => (
        <span key={i} className="text-[11px] px-2 py-0.5 rounded bg-void border border-border text-muted">
          {c}
        </span>
      ))}
    </div>
  );
}

function WpConnectionRow({ wp }: { wp: NonNullable<FlowStage["metrics"]["wordpress"]>[number] }) {
  const [result, setResult] = useState<WpTestResult | null>(null);
  const test = useMutation({
    mutationFn: () =>
      apiFetch<WpTestResult>(`/api/brands/${wp.brand_id}/test-connection`, { method: "POST" }),
    onSuccess: setResult,
  });
  const shown = result ?? wp;
  return (
    <tr className="border-t border-border">
      <td className="px-4 py-2.5 font-medium text-ink">{wp.brand_id}</td>
      <td className="px-4 py-2.5">
        {shown.ok ? (
          <span className="text-success">✓ connected</span>
        ) : (
          <span className="text-red-400">✗ {shown.status_code ?? "unreachable"}</span>
        )}
      </td>
      <td className="px-4 py-2.5 text-xs text-muted max-w-md">{shown.error || "—"}</td>
      <td className="px-4 py-2.5">
        <button
          type="button"
          onClick={() => test.mutate()}
          disabled={test.isPending}
          className="px-2.5 py-1 border border-border rounded text-xs text-ink hover:border-cyan disabled:opacity-50"
        >
          {test.isPending ? "Testing…" : "Test"}
        </button>
      </td>
    </tr>
  );
}

export function SystemHealthPage() {
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["flow-health"],
    queryFn: () => apiFetch<FlowHealth>("/api/health/flow"),
    staleTime: 60_000,
    retry: 1,
  });
  const { data: errorsResp } = useQuery({
    queryKey: ["worker-errors"],
    queryFn: () => apiFetch<{ errors: WorkerErrorItem[] }>("/api/worker-errors?limit=100"),
    staleTime: 60_000,
    retry: 1,
  });
  const [expandedWorker, setExpandedWorker] = useState<string | null>(null);

  if (isLoading) {
    return (
      <div className="aeo-panel px-4 py-10 text-center text-muted">
        Checking every pipeline stage (live WordPress probes take a few seconds)…
      </div>
    );
  }
  if (isError || !data) {
    return (
      <div className="bg-warning/10 border border-warning/25 text-warning text-sm px-4 py-3 rounded">
        {(error as Error)?.message ?? "Failed to load flow health."}
      </div>
    );
  }

  const overall = STATUS_STYLE[data.overall] ?? STATUS_STYLE.warn;
  const wpRows = data.stages.find((s) => s.key === "integrations")?.metrics.wordpress ?? [];
  const grouped = new Map<string, WorkerErrorItem[]>();
  for (const e of errorsResp?.errors ?? []) {
    grouped.set(e.worker_name, [...(grouped.get(e.worker_name) ?? []), e]);
  }

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-ink">System Health</h2>
          <p className="text-sm text-muted mt-1 max-w-2xl">
            Live diagnosis of the daily content flow: topics discovered → drafts generated →
            posts published, plus the integrations underneath. A daily 10:30am check alerts
            Discord when anything here fails.
          </p>
        </div>
        <button
          type="button"
          onClick={() => refetch()}
          disabled={isFetching}
          className="shrink-0 px-3 py-1.5 border border-border text-ink rounded text-sm hover:border-cyan disabled:opacity-50"
        >
          {isFetching ? "Checking…" : "Re-check now"}
        </button>
      </div>

      <div className={`aeo-panel border ${overall.panel} px-5 py-4 flex items-center gap-3`}>
        <span className={`w-3 h-3 rounded-full ${overall.dot}`} />
        <span className={`font-semibold uppercase text-sm ${overall.label}`}>
          {data.overall === "ok" ? "All systems healthy" : data.overall === "warn" ? "Degraded" : "Pipeline failing"}
        </span>
        <span className="text-xs text-muted ml-auto">checked {fmtTime(data.checked_at)}</span>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        {data.stages.map((stage) => {
          const style = STATUS_STYLE[stage.status] ?? STATUS_STYLE.warn;
          return (
            <div key={stage.key} className={`aeo-panel border ${style.panel} p-4`}>
              <div className="flex items-center gap-2">
                <span className={`w-2.5 h-2.5 rounded-full ${style.dot}`} />
                <h3 className="font-semibold text-ink text-sm">{stage.label}</h3>
                <span className={`text-[11px] uppercase font-medium ml-auto ${style.label}`}>
                  {stage.status}
                </span>
              </div>
              <p className="text-sm text-muted mt-2">{stage.detail}</p>
              <MetricChips stage={stage} />
              {stage.key === "generation" && !!stage.metrics.stranded?.length && (
                <div className="mt-2 text-xs text-muted space-y-1">
                  {stage.metrics.stranded.slice(0, 5).map((s) => (
                    <div key={s.draft_id}>
                      • {s.brand_id}: “{s.title || `draft ${s.draft_id}`}” waiting{" "}
                      {s.age_days ?? "?"} day(s) —{" "}
                      <a href={`/content/review/${s.draft_id}`} className="text-cyan hover:underline">
                        review
                      </a>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {!!wpRows.length && (
        <div className="aeo-panel overflow-hidden">
          <div className="px-5 py-4 border-b border-border">
            <h3 className="aeo-title text-ink">WordPress connections</h3>
            <p className="text-xs text-muted mt-0.5">
              Live auth check against each brand's site (results cached 10 min).
            </p>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted">
                <th className="px-4 py-3">Brand</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Detail</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {wpRows.map((wp) => (
                <WpConnectionRow key={wp.brand_id} wp={wp} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="aeo-panel overflow-hidden">
        <div className="px-5 py-4 border-b border-border">
          <h3 className="aeo-title text-ink">Worker errors (latest 100)</h3>
        </div>
        {grouped.size === 0 ? (
          <p className="px-5 py-6 text-sm text-muted/80">No recent worker errors.</p>
        ) : (
          <div className="divide-y divide-border">
            {[...grouped.entries()].map(([worker, errs]) => (
              <div key={worker}>
                <button
                  type="button"
                  onClick={() => setExpandedWorker(expandedWorker === worker ? null : worker)}
                  className="w-full px-5 py-3 flex items-center gap-3 text-left hover:bg-void/50"
                >
                  <span className="font-medium text-ink text-sm">{worker}</span>
                  <span className="text-[11px] px-2 py-0.5 rounded bg-warning/10 text-warning">
                    {errs.length}
                  </span>
                  <span className="text-xs text-muted truncate flex-1">
                    {errs[0]?.error_message?.slice(0, 100)}
                  </span>
                  <span className="text-xs text-muted shrink-0">{fmtTime(errs[0]?.created_at)}</span>
                </button>
                {expandedWorker === worker && (
                  <div className="px-5 pb-3 space-y-2">
                    {errs.slice(0, 20).map((e) => (
                      <div key={e.id} className="text-xs bg-void border border-border rounded p-2.5">
                        <span className="text-muted">{fmtTime(e.created_at)}</span>
                        <p className="text-ink mt-1 whitespace-pre-wrap break-words">
                          {e.error_message}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
