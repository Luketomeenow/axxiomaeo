import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { apiFetch } from "../lib/api";
import type { OptimizerProposal, OptimizerRunResult, OptimizerStatus } from "../types";

const TABS = [
  { key: "decide", label: "Needs a decision", statuses: ["proposed", "failed"] },
  { key: "progress", label: "In progress", statuses: ["queued", "running", "pr_open", "accepted"] },
  { key: "done", label: "Done", statuses: ["merged", "done", "closed"] },
  { key: "rejected", label: "Rejected", statuses: ["rejected"] },
] as const;

const IN_FLIGHT = ["queued", "running", "pr_open"];

const STATUS_TEXT: Record<string, { label: string; style: string }> = {
  proposed: { label: "Awaiting your decision", style: "text-cyan" },
  queued: { label: "Starting the Claude Code agent…", style: "text-cyan" },
  running: { label: "Claude Code is implementing it", style: "text-cyan" },
  pr_open: { label: "Pull request ready for review", style: "text-success" },
  merged: { label: "Merged (deploy to make it live)", style: "text-success" },
  closed: { label: "Pull request closed without merging", style: "text-muted" },
  failed: { label: "Failed", style: "text-red-400" },
  accepted: { label: "Accepted: waiting for a person to do it", style: "text-warning" },
  done: { label: "Done", style: "text-success" },
  rejected: { label: "Rejected", style: "text-muted" },
};

const PRIORITY_STYLE: Record<string, string> = {
  high: "bg-red-500/15 text-red-400",
  medium: "bg-warning/15 text-warning",
  low: "bg-void border border-border text-muted",
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

function Chip({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <span className={`text-[11px] px-2 py-0.5 rounded ${className}`}>{children}</span>;
}

function SetupNotice({ status }: { status?: OptimizerStatus }) {
  if (!status) return null;
  if (!status.enabled) {
    return (
      <p className="text-xs text-warning">
        The optimization agent is off (OPTIMIZER_ENABLED=false). No new proposals are made.
      </p>
    );
  }
  if (!status.github_configured) {
    return (
      <p className="text-xs text-warning">
        Proposals only: the Claude Code agent is not connected yet (OPTIMIZER_GITHUB_TOKEN is not
        set). Manual changes can still be accepted. Setup: Documentation → Azure Setup →
        Optimization agent.
      </p>
    );
  }
  if (status.github_error) {
    return <p className="text-xs text-warning">GitHub check failed: {status.github_error}</p>;
  }
  if (status.workflow_registered === false) {
    return (
      <p className="text-xs text-warning">
        GitHub can't start the agent yet: {status.workflow} is not on the default branch of{" "}
        {status.repo}. Merge it to main, then approvals start the agent.
      </p>
    );
  }
  return (
    <p className="text-xs text-muted">
      Claude Code agent connected: {status.repo}, workflow {status.workflow}, pull requests
      against {status.base_branch}.
    </p>
  );
}

function ProposalCard({ p, status }: { p: OptimizerProposal; status?: OptimizerStatus }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(p.status === "proposed" && p.priority === "high");
  const [confirming, setConfirming] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [note, setNote] = useState("");
  const [instructions, setInstructions] = useState(p.instructions ?? "");
  const isCode = p.change_type === "code";

  const decide = useMutation({
    mutationFn: (action: "approve" | "reject" | "done" | "sync") =>
      apiFetch<OptimizerProposal>(`/api/optimizer/proposals/${p.id}/${action}`, {
        method: "POST",
        body:
          action === "sync"
            ? undefined
            : JSON.stringify({
                note: note.trim() || null,
                instructions:
                  action === "approve" && isCode && instructions !== (p.instructions ?? "")
                    ? instructions
                    : null,
              }),
      }),
    onSuccess: () => {
      setConfirming(false);
      setRejecting(false);
      queryClient.invalidateQueries({ queryKey: ["optimizer-proposals"] });
      queryClient.invalidateQueries({ queryKey: ["optimizer-status"] });
    },
  });

  const state = STATUS_TEXT[p.status] ?? { label: p.status, style: "text-muted" };
  const canDecide = p.status === "proposed" || p.status === "failed";
  const agentReady = !isCode || (status?.github_configured && status.workflow_registered !== false);

  return (
    <div className="aeo-panel p-4">
      <div className="flex items-start gap-2 flex-wrap">
        <Chip className={PRIORITY_STYLE[p.priority] ?? PRIORITY_STYLE.low}>
          {p.priority.toUpperCase()}
        </Chip>
        <Chip className="bg-cyan/10 text-cyan">{p.category}</Chip>
        {p.brand_id && <Chip className="bg-void border border-border text-muted">{p.brand_id}</Chip>}
        <Chip className="bg-void border border-border text-ink">
          {isCode ? "Code change · Claude Code" : "Manual change"}
        </Chip>
        <span className="text-[11px] text-muted ml-auto">
          #{p.id} · {fmtTime(p.created_at)}
        </span>
      </div>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="mt-2 text-left font-medium text-ink hover:text-cyan"
      >
        {p.title}
      </button>
      <p className={`text-xs mt-1 ${state.style}`}>
        {state.label}
        {p.decided_by && p.status !== "proposed" ? ` · decided ${fmtTime(p.decided_at)}` : ""}
      </p>

      {(p.run_url || p.pr_url || p.error) && (
        <div className="mt-2 text-xs space-y-1">
          {p.pr_url && (
            <a href={p.pr_url} target="_blank" rel="noreferrer" className="text-cyan hover:underline block">
              Pull request #{p.pr_number} ↗
            </a>
          )}
          {p.run_url && (
            <a href={p.run_url} target="_blank" rel="noreferrer" className="text-cyan hover:underline block">
              Claude Code run log ↗
            </a>
          )}
          {p.error && <p className="text-red-400">{p.error}</p>}
        </div>
      )}

      {open && (
        <div className="mt-3 space-y-3 text-sm">
          {p.problem && <p className="text-muted">{p.problem}</p>}
          {!!p.evidence.length && (
            <div>
              <h4 className="text-xs font-semibold text-ink mb-1">Evidence</h4>
              <ul className="space-y-1">
                {p.evidence.map((e, i) => (
                  <li key={i} className="text-xs text-muted flex gap-2">
                    <span
                      className={e.verified ? "text-success" : "text-warning"}
                      title={e.verified ? "Found in the platform's data" : "Not found in the platform's data"}
                    >
                      {e.verified ? "✓" : "⚠"}
                    </span>
                    <span>
                      <span className="text-ink">{e.label}:</span> {e.value}{" "}
                      <span className="text-muted/70">({e.source})</span>
                      {!e.verified && <span className="text-warning"> — not found in the data, check it</span>}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {p.proposed_change && (
            <div>
              <h4 className="text-xs font-semibold text-ink mb-1">Proposed change</h4>
              <p className="text-muted whitespace-pre-wrap">{p.proposed_change}</p>
            </div>
          )}
          <div className="grid md:grid-cols-3 gap-3 text-xs">
            {p.expected_impact && (
              <div>
                <h4 className="font-semibold text-ink mb-0.5">Expected impact</h4>
                <p className="text-muted">{p.expected_impact}</p>
              </div>
            )}
            {p.acceptance && (
              <div>
                <h4 className="font-semibold text-ink mb-0.5">Done when</h4>
                <p className="text-muted">{p.acceptance}</p>
              </div>
            )}
            {p.risk && (
              <div>
                <h4 className="font-semibold text-ink mb-0.5">Risk</h4>
                <p className="text-muted">{p.risk}</p>
              </div>
            )}
          </div>
          {isCode && (
            <div>
              <h4 className="text-xs font-semibold text-ink mb-1">
                Task for the Claude Code agent{canDecide ? " (you can edit it before approving)" : ""}
              </h4>
              {canDecide ? (
                <textarea
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                  rows={8}
                  className="w-full bg-void border border-border rounded p-2.5 text-xs text-ink font-mono focus:outline-none focus:border-cyan/50"
                />
              ) : (
                <pre className="bg-void border border-border rounded p-2.5 text-xs text-muted whitespace-pre-wrap">
                  {p.instructions}
                </pre>
              )}
              {!!p.files_hint.length && (
                <p className="text-[11px] text-muted mt-1">Likely files: {p.files_hint.join(", ")}</p>
              )}
            </div>
          )}
          {p.decision_note && <p className="text-xs text-muted">Note: {p.decision_note}</p>}
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {canDecide && !confirming && !rejecting && (
          <>
            <button
              type="button"
              onClick={() => (isCode ? setConfirming(true) : decide.mutate("approve"))}
              disabled={decide.isPending || !agentReady}
              title={agentReady ? undefined : "Connect the Claude Code agent first (see the note above)"}
              className="px-3 py-1.5 rounded text-xs font-medium bg-cyan/15 text-cyan border border-cyan/30 hover:bg-cyan/25 disabled:opacity-50"
            >
              {isCode ? (p.status === "failed" ? "Retry with Claude Code" : "Approve: Claude Code opens a PR") : "Accept: we'll do it"}
            </button>
            <button
              type="button"
              onClick={() => setRejecting(true)}
              disabled={decide.isPending}
              className="px-3 py-1.5 rounded text-xs border border-border text-muted hover:text-ink disabled:opacity-50"
            >
              Reject
            </button>
          </>
        )}
        {confirming && (
          <div className="w-full bg-void border border-cyan/30 rounded p-3 text-xs space-y-2">
            <p className="text-ink">
              Claude Code will implement this task on a new branch of {status?.repo ?? "the repo"} and
              open a pull request. It can only edit files; nothing is merged or deployed until a
              person merges the PR and deploys.
            </p>
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Note (optional)"
              className="w-full bg-panel border border-border rounded px-2 py-1 text-ink focus:outline-none focus:border-cyan/50"
            />
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => decide.mutate("approve")}
                disabled={decide.isPending}
                className="px-3 py-1.5 rounded font-medium bg-cyan text-void hover:opacity-90 disabled:opacity-50"
              >
                {decide.isPending ? "Starting…" : "Confirm and start"}
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
        {rejecting && (
          <div className="w-full bg-void border border-border rounded p-3 text-xs space-y-2">
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Why not? (optional; the agent won't propose it again)"
              className="w-full bg-panel border border-border rounded px-2 py-1 text-ink focus:outline-none focus:border-cyan/50"
            />
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => decide.mutate("reject")}
                disabled={decide.isPending}
                className="px-3 py-1.5 rounded border border-red-500/40 text-red-400 hover:bg-red-500/10 disabled:opacity-50"
              >
                {decide.isPending ? "Rejecting…" : "Reject proposal"}
              </button>
              <button
                type="button"
                onClick={() => setRejecting(false)}
                className="px-3 py-1.5 rounded border border-border text-muted hover:text-ink"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
        {p.status === "accepted" && (
          <button
            type="button"
            onClick={() => decide.mutate("done")}
            disabled={decide.isPending}
            className="px-3 py-1.5 rounded text-xs border border-success/40 text-success hover:bg-success/10 disabled:opacity-50"
          >
            Mark done
          </button>
        )}
        {IN_FLIGHT.includes(p.status) && (
          <button
            type="button"
            onClick={() => decide.mutate("sync")}
            disabled={decide.isPending}
            className="px-3 py-1.5 rounded text-xs border border-border text-muted hover:text-ink disabled:opacity-50"
          >
            {decide.isPending ? "Checking GitHub…" : "Refresh from GitHub"}
          </button>
        )}
        {decide.isError && <span className="text-xs text-red-400">{(decide.error as Error).message}</span>}
      </div>
    </div>
  );
}

export function OptimizerPanel() {
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<(typeof TABS)[number]["key"]>("decide");
  const [lastRun, setLastRun] = useState<OptimizerRunResult | null>(null);

  const { data: status } = useQuery({
    queryKey: ["optimizer-status"],
    queryFn: () => apiFetch<OptimizerStatus>("/api/optimizer/status"),
    staleTime: 60_000,
    retry: 1,
  });
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["optimizer-proposals"],
    queryFn: () => apiFetch<{ proposals: OptimizerProposal[] }>("/api/optimizer/proposals"),
    staleTime: 15_000,
    retry: 1,
    // Follow running changes until their pull request appears.
    refetchInterval: (query) =>
      query.state.data?.proposals.some((p) => IN_FLIGHT.includes(p.status)) ? 30_000 : false,
  });
  const run = useMutation({
    mutationFn: () => apiFetch<OptimizerRunResult>("/api/optimizer/run", { method: "POST" }),
    onSuccess: (result) => {
      setLastRun(result);
      setTab("decide");
      queryClient.invalidateQueries({ queryKey: ["optimizer-proposals"] });
      queryClient.invalidateQueries({ queryKey: ["optimizer-status"] });
    },
  });

  const proposals = data?.proposals ?? [];
  const current = TABS.find((t) => t.key === tab) ?? TABS[0];
  const shown = proposals.filter((p) => (current.statuses as readonly string[]).includes(p.status));
  const countFor = (statuses: readonly string[]) => proposals.filter((p) => statuses.includes(p.status)).length;

  return (
    <div className="aeo-panel overflow-hidden">
      <div className="px-5 py-4 border-b border-border space-y-2">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h3 className="aeo-title text-ink">Optimization agent</h3>
            <p className="text-xs text-muted mt-0.5 max-w-2xl">
              Reads this platform's own numbers (pipeline health, publishing, AI citations, calls
              and lead events) and proposes changes, each with the evidence behind it. You decide.
              An approved code change goes to a Claude Code agent that opens a pull request; a
              manual change is tracked until someone marks it done. Runs every Monday 7:30am, or
              now.
            </p>
          </div>
          <button
            type="button"
            onClick={() => run.mutate()}
            disabled={run.isPending || status?.enabled === false}
            className="shrink-0 px-3 py-1.5 border border-border text-ink rounded text-sm hover:border-cyan disabled:opacity-50"
          >
            {run.isPending ? "Analyzing (about a minute)…" : "Run analysis now"}
          </button>
        </div>
        <SetupNotice status={status} />
        {run.isError && <p className="text-xs text-red-400">{(run.error as Error).message}</p>}
        {lastRun && (
          <div className="text-xs bg-void border border-border rounded px-3 py-2 text-muted">
            {lastRun.status === "ok" ? (
              <>
                {lastRun.summary && <p className="text-ink mb-1">{lastRun.summary}</p>}
                {lastRun.created?.length ?? 0} new proposal(s)
                {lastRun.skipped_duplicates ? ` · ${lastRun.skipped_duplicates} already proposed` : ""}
                {lastRun.dropped_ungrounded
                  ? ` · ${lastRun.dropped_ungrounded} dropped (cited no number from the data)`
                  : ""}
              </>
            ) : (
              <span className="text-warning">{lastRun.message}</span>
            )}
          </div>
        )}
      </div>

      <div className="px-5 pt-3 flex gap-1 flex-wrap border-b border-border">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={`px-3 py-1.5 text-xs rounded-t border-b-2 ${
              tab === t.key ? "border-cyan text-ink" : "border-transparent text-muted hover:text-ink"
            }`}
          >
            {t.label} ({countFor(t.statuses)})
          </button>
        ))}
      </div>

      <div className="p-4 space-y-3">
        {isLoading && <p className="text-sm text-muted">Loading proposals…</p>}
        {isError && (
          <p className="text-sm text-warning">{(error as Error)?.message ?? "Failed to load proposals."}</p>
        )}
        {!isLoading && !isError && shown.length === 0 && (
          <p className="text-sm text-muted/80">
            {tab === "decide"
              ? "Nothing waiting for a decision. Run an analysis to get proposals."
              : "Nothing here yet."}
          </p>
        )}
        {shown.map((p) => (
          <ProposalCard key={p.id} p={p} status={status} />
        ))}
      </div>
    </div>
  );
}
