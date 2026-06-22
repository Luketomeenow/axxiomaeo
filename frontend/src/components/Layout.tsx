import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { NotificationBell } from "./NotificationBell";

const navSections = [
  {
    label: "Overview",
    items: [{ path: "/", label: "Dashboard", icon: "◈" }],
  },
  {
    label: "Content",
    items: [
      { path: "/content/review", label: "Content Review", icon: "✎" },
      { path: "/content/published", label: "Published", icon: "▣" },
      { path: "/content/queue", label: "Content Queue", icon: "☰" },
    ],
  },
  {
    label: "Schema",
    items: [
      { path: "/schema/review", label: "Schema Review", icon: "{}" },
      { path: "/schema/published", label: "Published Schema", icon: "▤" },
      { path: "/schema/health", label: "Schema Health", icon: "♥" },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { path: "/citations", label: "Citations", icon: "◎" },
      { path: "/reports", label: "Reports", icon: "▦" },
    ],
  },
  {
    label: "System",
    items: [
      { path: "/settings/brands", label: "Brand Settings", icon: "⚙" },
      { path: "/notifications", label: "Notifications", icon: "◉" },
    ],
  },
];

function isActive(path: string, current: string) {
  return current === path || (path !== "/" && current.startsWith(path));
}

export function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, signOut } = useAuth();
  const supabaseConfigured = Boolean(import.meta.env.VITE_SUPABASE_URL);

  const handleSignOut = async () => {
    await signOut();
    navigate("/login");
  };

  const pageTitle =
    navSections
      .flatMap((s) => s.items)
      .find((n) => isActive(n.path, location.pathname))?.label || "Dashboard";

  return (
    <div className="min-h-screen flex bg-void">
      <aside className="w-60 bg-panel border-r border-border flex flex-col shrink-0">
        <div className="px-5 py-5 border-b border-border">
          <div className="flex items-baseline gap-1.5">
            <span className="text-lg font-bold text-cyan tracking-wide">AXXIOM</span>
            <span className="text-lg font-bold text-ink tracking-wide">AEO</span>
          </div>
          <p className="text-[10px] text-muted uppercase tracking-[0.2em] mt-1.5">
            Answer Engine Optimization
          </p>
        </div>

        <nav className="flex-1 py-4 overflow-y-auto">
          {navSections.map((section) => (
            <div key={section.label} className="mb-4">
              <p className="px-5 mb-1.5 text-[10px] font-semibold text-muted uppercase tracking-widest">
                {section.label}
              </p>
              <div className="space-y-0.5 px-2">
                {section.items.map((item) => {
                  const active = isActive(item.path, location.pathname);
                  return (
                    <Link
                      key={item.path}
                      to={item.path}
                      className={`flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-all ${
                        active
                          ? "bg-cyan/10 text-cyan border border-cyan/20 font-medium"
                          : "text-muted hover:text-ink hover:bg-panel-hover border border-transparent"
                      }`}
                    >
                      <span className="text-xs opacity-70 w-4 text-center">{item.icon}</span>
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        {user?.email && (
          <div className="p-4 border-t border-border">
            <p className="text-[10px] text-muted uppercase tracking-wider mb-1">Signed in</p>
            <p className="text-xs text-ink/80 truncate">{user.email}</p>
          </div>
        )}
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        {!supabaseConfigured && (
          <div className="bg-warning/10 border-b border-warning/20 px-6 py-2 text-xs text-warning">
            Dev mode: Supabase not configured — authentication is bypassed.
          </div>
        )}
        <header className="bg-panel border-b border-border px-6 py-3.5 flex items-center justify-between gap-4 shrink-0">
          <h2 className="text-lg font-semibold text-ink">{pageTitle}</h2>
          <div className="flex items-center gap-3">
            <NotificationBell />
            {supabaseConfigured && (
              <button
                type="button"
                onClick={handleSignOut}
                className="aeo-btn-secondary text-xs py-1.5 px-3"
              >
                Sign Out
              </button>
            )}
          </div>
        </header>
        <main className="flex-1 p-6 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
