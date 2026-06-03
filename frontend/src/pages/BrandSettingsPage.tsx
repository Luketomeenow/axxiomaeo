import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiFetch } from "../lib/api";
import type { Brand } from "../types";

function normalizeGa4PropertyId(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return "";
  return trimmed.startsWith("properties/") ? trimmed.slice("properties/".length).trim() : trimmed;
}

export function BrandSettingsPage() {
  const { brandId } = useParams<{ brandId?: string }>();
  const queryClient = useQueryClient();
  const [saveMsg, setSaveMsg] = useState("");
  const [saveError, setSaveError] = useState("");

  const { data: brands, isLoading } = useQuery({
    queryKey: ["brands"],
    queryFn: () => apiFetch<Brand[]>("/api/brands"),
  });

  const { data: brand, isLoading: loadingBrand } = useQuery({
    queryKey: ["brand", brandId],
    queryFn: () => apiFetch<Brand>(`/api/brands/${brandId}`),
    enabled: !!brandId,
  });

  const [form, setForm] = useState<Partial<Brand>>({});

  useEffect(() => {
    setForm({});
    setSaveMsg("");
    setSaveError("");
  }, [brandId]);

  const update = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<Brand>(`/api/brands/${brandId}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(["brand", brandId], updated);
      queryClient.invalidateQueries({ queryKey: ["brands"] });
      setForm({});
      setSaveError("");
      setSaveMsg("Saved successfully.");
      setTimeout(() => setSaveMsg(""), 3000);
    },
    onError: (err: Error) => {
      setSaveMsg("");
      setSaveError(err.message || "Failed to save brand settings.");
    },
  });

  if (!brandId) {
    return (
      <div className="space-y-4">
        <h2 className="font-display text-xl font-bold text-navy">Brand Settings</h2>
        <p className="text-sm text-black/50">
          WordPress application passwords are managed via Railway environment variables.
        </p>
        <div className="bg-white rounded border border-black/8 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-black/8 text-left text-black/50">
                <th className="px-4 py-3">Brand</th>
                <th className="px-4 py-3">URL</th>
                <th className="px-4 py-3">GA4 Property</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-black/40">
                    Loading…
                  </td>
                </tr>
              ) : (
                brands?.map((b) => (
                  <tr key={b.id} className="border-t border-black/5">
                    <td className="px-4 py-3 font-medium">{b.name}</td>
                    <td className="px-4 py-3 text-black/60">{b.wp_url}</td>
                    <td className="px-4 py-3 text-black/60">{b.ga4_property_id || "—"}</td>
                    <td className="px-4 py-3">
                      <Link
                        to={`/settings/brands/${b.id}`}
                        className="text-navy text-xs font-medium hover:text-orange"
                      >
                        Edit →
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  if (loadingBrand || !brand) {
    return <p className="text-black/50">Loading brand…</p>;
  }

  const values = {
    name: form.name ?? brand.name,
    wp_url: form.wp_url ?? brand.wp_url,
    markets: form.markets ?? brand.markets,
    phone: form.phone ?? brand.phone ?? "",
    ga4_property_id: form.ga4_property_id ?? brand.ga4_property_id ?? "",
    gsc_site_url: form.gsc_site_url ?? brand.gsc_site_url ?? "",
    logo_url: form.logo_url ?? brand.logo_url ?? "",
  };

  const marketsText = Array.isArray(values.markets) ? values.markets.join(", ") : "";

  const handleSave = () => {
    const ga4 = normalizeGa4PropertyId(values.ga4_property_id);
    update.mutate({
      name: values.name.trim(),
      wp_url: values.wp_url.trim(),
      markets: values.markets,
      phone: values.phone.trim() || null,
      ga4_property_id: ga4 || null,
      gsc_site_url: values.gsc_site_url.trim() || null,
      logo_url: values.logo_url.trim() || null,
    });
  };

  return (
    <div className="space-y-4 max-w-2xl">
      <Link to="/settings/brands" className="text-xs text-navy hover:text-orange">
        ← All brands
      </Link>
      <h2 className="font-display text-xl font-bold text-navy">Edit: {brand.name}</h2>
      <p className="text-xs text-black/50">
        WordPress passwords are managed via Railway environment variables, not here.
      </p>

      {saveMsg && (
        <div className="bg-green-50 border border-green-200 text-green-800 text-sm px-4 py-2 rounded">
          {saveMsg}
        </div>
      )}

      {saveError && (
        <div className="bg-red-50 border border-red-200 text-red-800 text-sm px-4 py-2 rounded">
          {saveError}
        </div>
      )}

      <div className="bg-white rounded border border-black/8 p-6 space-y-4">
        <div>
          <label className="block text-xs font-medium text-black/60 mb-1">Name</label>
          <input
            type="text"
            value={values.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full border border-black/15 rounded px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-black/60 mb-1">WordPress URL</label>
          <input
            type="url"
            value={values.wp_url}
            onChange={(e) => setForm({ ...form, wp_url: e.target.value })}
            className="w-full border border-black/15 rounded px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-black/60 mb-1">
            Markets (comma-separated)
          </label>
          <input
            type="text"
            value={marketsText}
            onChange={(e) =>
              setForm({
                ...form,
                markets: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
              })
            }
            className="w-full border border-black/15 rounded px-3 py-2 text-sm"
            placeholder="Houston TX, Dallas TX"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-black/60 mb-1">Phone</label>
          <input
            type="text"
            value={values.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            className="w-full border border-black/15 rounded px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-black/60 mb-1">GA4 Property ID</label>
          <input
            type="text"
            value={values.ga4_property_id}
            onChange={(e) => setForm({ ...form, ga4_property_id: e.target.value })}
            onBlur={(e) =>
              setForm({ ...form, ga4_property_id: normalizeGa4PropertyId(e.target.value) })
            }
            className="w-full border border-black/15 rounded px-3 py-2 text-sm"
            placeholder="123456789"
          />
          <p className="text-xs text-black/40 mt-1">
            Numeric property ID only (e.g. 123456789). Required for the AI traffic trend chart on
            the dashboard.
          </p>
        </div>
        <div>
          <label className="block text-xs font-medium text-black/60 mb-1">GSC Site URL</label>
          <input
            type="text"
            value={values.gsc_site_url}
            onChange={(e) => setForm({ ...form, gsc_site_url: e.target.value })}
            className="w-full border border-black/15 rounded px-3 py-2 text-sm"
            placeholder="https://example.com/"
          />
        </div>
        <button
          type="button"
          onClick={handleSave}
          disabled={update.isPending}
          className="px-4 py-2 bg-navy text-white rounded text-sm hover:bg-navy/90 disabled:opacity-50"
        >
          {update.isPending ? "Saving…" : "Save Changes"}
        </button>
      </div>
    </div>
  );
}
