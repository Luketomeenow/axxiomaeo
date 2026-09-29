import { supabase } from "./supabase";

/**
 * Which sign-in the dashboard uses, fixed at build time.
 * - "supabase" (default; Netlify): Supabase Auth, JWT sent as a Bearer token.
 * - "password" (Azure App Service build): the dashboard password is checked by
 *   the API, which sets an HttpOnly session cookie. No Supabase at all.
 */
export const AUTH_PROVIDER: "supabase" | "password" =
  import.meta.env.VITE_AUTH_PROVIDER === "password" ? "password" : "supabase";

export const passwordAuth = AUTH_PROVIDER === "password";

/** Whether sign-in is enforced at all (false only for local no-auth dev). */
export const authEnabled = passwordAuth || Boolean(supabase);
