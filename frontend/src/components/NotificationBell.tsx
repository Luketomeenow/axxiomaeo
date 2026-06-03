import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { apiFetch } from "../lib/api";

export function NotificationBell() {
  const { data } = useQuery({
    queryKey: ["notifications-count"],
    queryFn: () => apiFetch<{ count: number }>("/api/notifications/unread-count"),
    refetchInterval: 30000,
  });

  const count = data?.count ?? 0;

  return (
    <Link
      to="/notifications"
      className="relative p-2 rounded-full hover:bg-cream transition-colors"
      title="Notifications"
    >
      <svg className="w-5 h-5 text-navy" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
        />
      </svg>
      {count > 0 && (
        <span className="absolute -top-0.5 -right-0.5 bg-orange text-white text-xs w-5 h-5 rounded-full flex items-center justify-center font-medium">
          {count > 9 ? "9+" : count}
        </span>
      )}
    </Link>
  );
}
