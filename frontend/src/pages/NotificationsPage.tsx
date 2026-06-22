import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { apiFetch } from "../lib/api";
import type { Notification } from "../types";

export function NotificationsPage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => apiFetch<Notification[]>("/api/notifications"),
  });

  const markRead = useMutation({
    mutationFn: (id: number) =>
      apiFetch(`/api/notifications/${id}/read`, { method: "PATCH" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      queryClient.invalidateQueries({ queryKey: ["notifications-count"] });
    },
  });

  const getLink = (n: Notification) => {
    if (n.entity_type === "content_draft" && n.entity_id) {
      return `/content/review/${n.entity_id}`;
    }
    if (n.entity_type === "schema_deployment") return "/schema/review";
    return null;
  };

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-bold text-ink">Notifications</h2>
      <div className="space-y-2">
        {isLoading ? (
          <p className="text-muted">Loading…</p>
        ) : !data?.length ? (
          <p className="text-muted">No notifications</p>
        ) : (
          data.map((n) => {
            const link = getLink(n);
            return (
              <div
                key={n.id}
                className={`aeo-panel border p-4 flex items-start justify-between gap-4 ${
                  n.read_at ? "border-border opacity-60" : "border-navy/20"
                }`}
              >
                <div>
                  <p className="font-medium text-ink">{n.title}</p>
                  {n.body && <p className="text-sm text-muted mt-1">{n.body}</p>}
                  <p className="text-xs text-muted/80 mt-2">
                    {new Date(n.created_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex gap-2 shrink-0">
                  {link && (
                    <Link to={link} className="text-xs text-ink hover:text-cyan font-medium">
                      View →
                    </Link>
                  )}
                  {!n.read_at && (
                    <button
                      onClick={() => markRead.mutate(n.id)}
                      className="text-xs text-muted/80 hover:text-ink"
                    >
                      Mark read
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
