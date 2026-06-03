import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { NotificationBell } from "./NotificationBell";

const navItems = [
  { path: "/", label: "Dashboard" },
  { path: "/content/review", label: "Content Review" },
  { path: "/content/queue", label: "Content Queue" },
  { path: "/schema/review", label: "Schema Review" },
  { path: "/citations", label: "Citations" },
  { path: "/schema/health", label: "Schema Health" },
  { path: "/reports", label: "Reports" },
  { path: "/settings/brands", label: "Brand Settings" },
  { path: "/notifications", label: "Notifications" },
];

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
    navItems.find(
      (n) =>
        location.pathname === n.path ||
        (n.path !== "/" && location.pathname.startsWith(n.path))
    )?.label || "Dashboard";

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
        {!supabaseConfigured && (
          <div className="bg-orange/10 border-b border-orange/20 px-6 py-2 text-xs text-orange">
            Dev mode: Supabase not configured — authentication is bypassed.
          </div>
        )}
        <header className="bg-white border-b border-black/8 px-6 py-4 flex items-center justify-between gap-4">
          <h2 className="font-display text-lg font-bold text-navy">{pageTitle}</h2>
          <div className="flex items-center gap-4">
            {user?.email && (
              <span className="text-xs text-black/50 hidden sm:block">{user.email}</span>
            )}
            <NotificationBell />
            {supabaseConfigured && (
              <button
                type="button"
                onClick={handleSignOut}
                className="text-xs text-navy hover:text-orange font-medium"
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
