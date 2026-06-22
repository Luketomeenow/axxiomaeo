import { useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { supabase } from "../lib/supabase";

export function LoginPage() {
  const { user, signIn, loading } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (!loading && user) return <Navigate to="/" replace />;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      if (!supabase) {
        setError("Supabase not configured. Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY.");
        return;
      }
      await signIn(email, password);
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message === "Failed to fetch"
            ? "Cannot reach Supabase. Check VITE_SUPABASE_URL in frontend/.env and restart the dev server."
            : err.message
          : "Login failed";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-void flex items-center justify-center p-4">
      <div className="aeo-panel w-full max-w-md p-8 shadow-2xl shadow-cyan/5">
        <div className="mb-8">
          <div className="flex items-baseline gap-1.5">
            <span className="text-2xl font-bold text-cyan tracking-wide">AXXIOM</span>
            <span className="text-2xl font-bold text-ink tracking-wide">AEO</span>
          </div>
          <p className="text-sm text-muted mt-2">Sign in to the automation command center</p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-ink/80 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="aeo-input"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-ink/80 mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="aeo-input"
              required
            />
          </div>
          {error && <p className="text-sm text-danger">{error}</p>}
          <button type="submit" disabled={submitting} className="aeo-btn-primary w-full py-2.5">
            {submitting ? "Signing in…" : "Sign In"}
          </button>
        </form>
      </div>
    </div>
  );
}
