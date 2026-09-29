import { supabase } from "./supabase";
import { passwordAuth } from "./authMode";

function normalizeApiUrl(raw: string | undefined): string {
  // Unset → local dev backend. Explicitly EMPTY → same origin (the Azure App
  // Service build, where FastAPI serves this bundle and the API together).
  if (raw !== undefined && raw.trim() === "") {
    return "";
  }
  const value = (raw || "http://localhost:8000").trim().replace(/\/+$/, "");
  // A scheme-less value (e.g. "api.example.com") would be treated as a relative
  // path by fetch() and hit the Netlify site instead of the backend.
  if (value && !/^https?:\/\//i.test(value)) {
    return `https://${value}`;
  }
  return value;
}

const API_URL = normalizeApiUrl(import.meta.env.VITE_API_URL);

async function getAuthHeaders(): Promise<HeadersInit> {
  const headers: HeadersInit = { "Content-Type": "application/json" };
  // Password sign-in rides on the HttpOnly session cookie, not a header.
  if (!passwordAuth && supabase) {
    const { data } = await supabase.auth.getSession();
    if (data.session?.access_token) {
      headers["Authorization"] = `Bearer ${data.session.access_token}`;
    }
  }
  return headers;
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = await getAuthHeaders();
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    credentials: passwordAuth ? "same-origin" : options.credentials,
    headers: { ...headers, ...options.headers },
  });
  if (passwordAuth && response.status === 401 && window.location.pathname !== "/login") {
    // Session expired or was never there — back to the sign-in screen.
    window.location.assign("/login");
  }
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    const detail = error.detail;
    let message: string;
    if (typeof detail === "string") {
      message = detail;
    } else if (Array.isArray(detail)) {
      message = detail.map((item) => item?.msg ?? JSON.stringify(item)).join(", ");
    } else {
      message = `API error: ${response.status}`;
    }
    throw new Error(message);
  }
  return response.json();
}
