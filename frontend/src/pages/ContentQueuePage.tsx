import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { BrandLocationPicker } from "../components/BrandLocationPicker";
import type { BrandLocation } from "../data/brandLocations";
import { apiFetch } from "../lib/api";
import type { ContentQueueItem } from "../types";

const PRIORITY_LABEL: Record<number, string> = {
  1: "CRITICAL",
  3: "HIGH",
  5: "MEDIUM",
};

const CONTENT_TYPES = [
  { value: "faq_hub", label: "FAQ Hub" },
  { value: "local_page", label: "Local Page" },
  { value: "vertical_page", label: "Vertical Page" },
  { value: "comparison", label: "Comparison" },
  { value: "data_stats", label: "Data & Statistics" },
];

export function ContentQueuePage() {
  const queryClient = useQueryClient();
  const [showModal, setShowModal] = useState(false);
  const [successMsg, setSuccessMsg] = useState("");
  const [form, setForm] = useState({
    location_id: "",
    brand_id: "",
    content_type: "faq_hub",
    target_query: "",
    title: "",
    city: "",
    state: "",
  });

  const selectLocation = (location: BrandLocation) => {
    setForm((prev) => ({
      ...prev,
      location_id: location.id,
      brand_id: location.brandId,
      city: location.city,
      state: location.state,
    }));
  };

  const openModal = () => {
    setShowModal(true);
  };

  const { data, isLoading } = useQuery({
    queryKey: ["content-queue"],
    queryFn: () => apiFetch<ContentQueueItem[]>("/api/content/queue"),
    refetchInterval: 60000,
  });

  const { data: brandsById } = useQuery({
    queryKey: ["brands"],
    queryFn: () => apiFetch<{ id: string; name: string }[]>("/api/brands"),
    select: (brands) => Object.fromEntries(brands.map((b) => [b.id, b.name])),
  });

  const [generatingId, setGeneratingId] = useState<number | null>(null);

  const showSuccess = (message: string) => {
    setSuccessMsg(message);
    queryClient.invalidateQueries({ queryKey: ["content-queue"] });
    queryClient.invalidateQueries({ queryKey: ["drafts"] });
    setTimeout(() => setSuccessMsg(""), 8000);
  };

  const generate = useMutation({
    mutationFn: (payload: {
      brand_id: string;
      content_type: string;
      target_query: string;
      title: string;
      city: string;
      state: string;
    }) =>
      apiFetch("/api/content/generate", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      setShowModal(false);
      showSuccess("Generation started — open Content Review (refreshes every 5s while writing).");
    },
    onError: () => {
      queryClient.invalidateQueries({ queryKey: ["drafts"] });
    },
  });

  const generateFromQueue = useMutation({
    mutationFn: (queueId: number) =>
      apiFetch(`/api/content/queue/${queueId}/generate`, { method: "POST" }),
    onMutate: (queueId) => setGeneratingId(queueId),
    onSettled: () => setGeneratingId(null),
    onSuccess: () => {
      showSuccess("Queue item generation started — check Content Review in a few minutes.");
    },
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-4">
        <h2 className="text-xl font-bold text-ink">Content Queue</h2>
        <button
          type="button"
          onClick={openModal}
          className="px-4 py-2 bg-cyan text-void rounded text-sm hover:bg-cyan/90"
        >
          Generate Content
        </button>
      </div>

      {successMsg && (
        <div className="bg-success/10 border border-success/25 text-success text-sm px-4 py-3 rounded">
          {successMsg}{" "}
          <Link to="/content/review" className="underline font-medium">
            Go to Content Review
          </Link>
        </div>
      )}

      {(generate.isError || generateFromQueue.isError) && (
        <div className="bg-warning/10 border border-warning/30 text-warning text-sm px-4 py-3 rounded">
          {(() => {
            const err = (generate.error || generateFromQueue.error) as Error | null;
            const msg = err?.message ?? "Generation failed";
            if (msg === "Not Found") {
              return "Generate endpoint unavailable — restart the backend server (uvicorn) and try again.";
            }
            if (msg.includes("409") || msg.toLowerCase().includes("already exists")) {
              return "A draft for this item already exists — check Content Review.";
            }
            if (msg.includes("429") || msg.toLowerCase().includes("generating")) {
              return msg;
            }
            return msg;
          })()}
        </div>
      )}

      <div className="aeo-panel overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-muted">
              <th className="px-4 py-3">Title</th>
              <th className="px-4 py-3">Brand</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Priority</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Scheduled</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-muted/80">
                  Loading…
                </td>
              </tr>
            ) : !data?.length ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-muted/80">
                  Queue is empty
                </td>
              </tr>
            ) : (
              data.map((item) => (
                <tr key={item.id} className="border-t border-border">
                  <td className="px-4 py-3 font-medium">{item.title}</td>
                  <td className="px-4 py-3 text-muted">{brandsById?.[item.brand_id] ?? item.brand_id}</td>
                  <td className="px-4 py-3 text-muted">{item.content_type}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`text-xs px-2 py-0.5 rounded font-medium ${
                        item.priority === 1
                          ? "bg-red-100 text-red-700"
                          : item.priority === 3
                            ? "bg-yellow-100 text-yellow-800"
                            : "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {PRIORITY_LABEL[item.priority] || "MEDIUM"}
                    </span>
                  </td>
                  <td className="px-4 py-3">{item.status}</td>
                  <td className="px-4 py-3 text-muted">{item.scheduled_for || "—"}</td>
                  <td className="px-4 py-3 text-right">
                    {item.status === "pending" ? (
                      <button
                        type="button"
                        onClick={() => generateFromQueue.mutate(item.id)}
                        disabled={generatingId === item.id || generateFromQueue.isPending}
                        className="px-3 py-1.5 bg-cyan text-void rounded text-xs font-medium hover:bg-cyan/90 disabled:opacity-50"
                      >
                        {generatingId === item.id ? "Starting…" : "Generate"}
                      </button>
                    ) : item.status === "in_progress" ? (
                      <span className="text-xs text-muted/80">Generating…</span>
                    ) : item.status === "ready" || item.status === "needs_review" ? (
                      <Link
                        to="/content/review"
                        className="text-xs text-ink font-medium hover:text-cyan"
                      >
                        Review →
                      </Link>
                    ) : (
                      <span className="text-xs text-muted/50">—</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-4 z-50">
          <div className="aeo-panel shadow-xl w-full max-w-lg p-6 space-y-4">
            <h3 className="text-lg font-semibold text-ink">Generate Content</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-muted mb-2">Brand</label>
                <BrandLocationPicker selectedId={form.location_id} onSelect={selectLocation} />
              </div>
              <div>
                <label className="block text-xs font-medium text-muted mb-1">Content type</label>
                <select
                  value={form.content_type}
                  onChange={(e) => setForm({ ...form, content_type: e.target.value })}
                  className="w-full border border-border rounded px-3 py-2 text-sm"
                >
                  {CONTENT_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-muted mb-1">Target query</label>
                <input
                  type="text"
                  value={form.target_query}
                  onChange={(e) => setForm({ ...form, target_query: e.target.value })}
                  className="w-full border border-border rounded px-3 py-2 text-sm"
                  placeholder="e.g. how often should elevators be inspected"
                  required
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-muted mb-1">Title (optional)</label>
                <input
                  type="text"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  className="w-full border border-border rounded px-3 py-2 text-sm"
                />
              </div>
              {form.content_type === "local_page" && (
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-muted mb-1">City</label>
                    <input
                      type="text"
                      value={form.city}
                      onChange={(e) => setForm({ ...form, city: e.target.value })}
                      className="w-full border border-border rounded px-3 py-2 text-sm"
                      placeholder="Houston"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-muted mb-1">State</label>
                    <input
                      type="text"
                      value={form.state}
                      onChange={(e) => setForm({ ...form, state: e.target.value })}
                      className="w-full border border-border rounded px-3 py-2 text-sm"
                      placeholder="TX"
                    />
                  </div>
                </div>
              )}
            </div>
            {generate.isError && (
              <p className="text-sm text-warning">{(generate.error as Error).message}</p>
            )}
            {!form.location_id && (
              <p className="text-sm text-muted">Select a brand location above to enable Generate.</p>
            )}
            {form.location_id && !form.target_query.trim() && (
              <p className="text-sm text-muted">Enter a target query (search phrase) to enable Generate.</p>
            )}
            <div className="flex gap-2 justify-end pt-2">
              <button
                type="button"
                onClick={() => setShowModal(false)}
                className="px-4 py-2 text-sm text-muted"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => {
                  const { location_id: _locationId, ...payload } = form;
                  generate.mutate(payload);
                }}
                disabled={!form.location_id || !form.target_query.trim() || generate.isPending}
                className="px-4 py-2 bg-cyan text-void rounded text-sm disabled:opacity-50"
              >
                {generate.isPending ? "Starting…" : "Generate"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
