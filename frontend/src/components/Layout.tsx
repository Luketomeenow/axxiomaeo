import { Link, Outlet, useLocation } from "react-router-dom";
import { NotificationBell } from "./NotificationBell";

const navItems = [
  { path: "/", label: "Dashboard" },
  { path: "/content/review", label: "Content Review" },
  { path: "/content/queue", label: "Content Queue" },
  { path: "/schema/review", label: "Schema Review" },
  { path: "/citations", label: "Citations" },
  { path: "/schema/health", label: "Schema Health" },
  { path: "/reports", label: "Reports" },
  { path: "/notifications", label: "Notifications" },
];

export function Layout() {
  const location = useLocation();

  return (
    <div className="min-h-screen flex">
      <aside className="w-64 bg-navy text-white flex flex-col shrink-0">
        <div className="p-6 border-b border-white/10">
          <h1 className="font-display text-xl font-bold">Axxiom AEO</h1>
          <p className="text-xs text-white/50 mt-1">Automation Dashboard</p>
        </div>
        <nav className="flex-1 p-4 space-y-1">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`block px-3 py-2 rounded text-sm transition-colors ${
                location.pathname === item.path ||
                (item.path !== "/" && location.pathname.startsWith(item.path))
                  ? "bg-orange text-white"
                  : "text-white/70 hover:bg-white/10 hover:text-white"
              }`}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>
      <div className="flex-1 flex flex-col min-w-0">
        <header className="bg-white border-b border-black/8 px-6 py-4 flex items-center justify-between">
          <h2 className="font-display text-lg font-bold text-navy">
            {navItems.find(
              (n) =>
                location.pathname === n.path ||
                (n.path !== "/" && location.pathname.startsWith(n.path))
            )?.label || "Dashboard"}
          </h2>
          <NotificationBell />
        </header>
        <main className="flex-1 p-6 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
