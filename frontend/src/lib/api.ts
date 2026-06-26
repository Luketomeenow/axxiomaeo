import { supabase } from "./supabase";

function normalizeApiUrl(raw: string | undefined): string {
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
  if (supabase) {
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
    headers: { ...headers, ...options.headers },
  });
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
