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
  const [serviceUrlsRaw, setServiceUrlsRaw] = useState("");

  useEffect(() => {
    setForm({});
    setSaveMsg("");
    setSaveError("");
  }, [brandId]);

  useEffect(() => {
    setServiceUrlsRaw(brand ? JSON.stringify(brand.service_page_urls ?? {}, null, 2) : "");
  }, [brandId, brand]);

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
        <h2 className="text-xl font-bold text-ink">Brand Settings</h2>
        <p className="text-sm text-muted">
          WordPress application passwords are managed via Railway environment variables.
        </p>
        <div className="aeo-panel overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-muted">
                <th className="px-4 py-3">Brand</th>
                <th className="px-4 py-3">URL</th>
                <th className="px-4 py-3">GA4 Property</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-muted/80">
                    Loading…
                  </td>
                </tr>
              ) : (
                brands?.map((b) => (
                  <tr key={b.id} className="border-t border-border">
                    <td className="px-4 py-3 font-medium">{b.name}</td>
                    <td className="px-4 py-3 text-muted">{b.wp_url}</td>
                    <td className="px-4 py-3 text-muted">{b.ga4_property_id || "—"}</td>
                    <td className="px-4 py-3">
                      <Link
                        to={`/settings/brands/${b.id}`}
                        className="text-ink text-xs font-medium hover:text-cyan"
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
    return <p className="text-muted">Loading brand…</p>;
  }

  const values = {
    name: form.name ?? brand.name,
    wp_url: form.wp_url ?? brand.wp_url,
    markets: form.markets ?? brand.markets,
    phone: form.phone ?? brand.phone ?? "",
    ga4_property_id: form.ga4_property_id ?? brand.ga4_property_id ?? "",
    gsc_site_url: form.gsc_site_url ?? brand.gsc_site_url ?? "",
    logo_url: form.logo_url ?? brand.logo_url ?? "",
    target_queries: form.target_queries ?? brand.target_queries ?? [],
    service_page_urls: form.service_page_urls ?? brand.service_page_urls ?? {},
  };

  const marketsText = Array.isArray(values.markets) ? values.markets.join(", ") : "";
  const targetQueriesText = Array.isArray(values.target_queries)
    ? values.target_queries.join("\n")
    : "";

  const handleSave = () => {
    const ga4 = normalizeGa4PropertyId(values.ga4_property_id);
    let service_page_urls: Record<string, string> = {};
    if (serviceUrlsRaw.trim()) {
      try {
        service_page_urls = JSON.parse(serviceUrlsRaw) as Record<string, string>;
      } catch {
        setSaveError("Service page URLs must be valid JSON object.");
        return;
      }
    }
    update.mutate({
      name: values.name.trim(),
      wp_url: values.wp_url.trim(),
      markets: values.markets,
      phone: values.phone.trim() || null,
      ga4_property_id: ga4 || null,
      gsc_site_url: values.gsc_site_url.trim() || null,
      logo_url: values.logo_url.trim() || null,
      target_queries: targetQueriesText
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean),
      service_page_urls: service_page_urls,
    });
  };

  return (
    <div className="space-y-4 max-w-2xl">
      <Link to="/settings/brands" className="text-xs text-ink hover:text-cyan">
        ← All brands
      </Link>
      <h2 className="text-xl font-bold text-ink">Edit: {brand.name}</h2>
      <p className="text-xs text-muted">
        WordPress passwords are managed via Railway environment variables, not here.
      </p>

      {saveMsg && (
        <div className="bg-success/10 border border-success/25 text-success text-sm px-4 py-2 rounded">
          {saveMsg}
        </div>
      )}

      {saveError && (
        <div className="bg-danger/10 border border-red-200 text-red-800 text-sm px-4 py-2 rounded">
          {saveError}
        </div>
      )}

      <div className="aeo-panel p-6 space-y-4">
        <div>
          <label className="block text-xs font-medium text-muted mb-1">Name</label>
          <input
            type="text"
            value={values.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="w-full border border-border rounded px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-muted mb-1">WordPress URL</label>
          <input
            type="url"
            value={values.wp_url}
            onChange={(e) => setForm({ ...form, wp_url: e.target.value })}
            className="w-full border border-border rounded px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-muted mb-1">
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
            className="w-full border border-border rounded px-3 py-2 text-sm"
            placeholder="Houston TX, Dallas TX"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-muted mb-1">Phone</label>
          <input
            type="text"
            value={values.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            className="w-full border border-border rounded px-3 py-2 text-sm"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-muted mb-1">GA4 Property ID</label>
          <input
            type="text"
            value={values.ga4_property_id}
            onChange={(e) => setForm({ ...form, ga4_property_id: e.target.value })}
            onBlur={(e) =>
              setForm({ ...form, ga4_property_id: normalizeGa4PropertyId(e.target.value) })
            }
            className="w-full border border-border rounded px-3 py-2 text-sm"
            placeholder="123456789"
          />
          <p className="text-xs text-muted/80 mt-1">
            Numeric property ID only (e.g. 123456789). Required for the AI traffic trend chart on
            the dashboard.
          </p>
        </div>
        <div>
          <label className="block text-xs font-medium text-muted mb-1">GSC Site URL</label>
          <input
            type="text"
            value={values.gsc_site_url}
            onChange={(e) => setForm({ ...form, gsc_site_url: e.target.value })}
            className="w-full border border-border rounded px-3 py-2 text-sm"
            placeholder="https://example.com/"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-muted mb-1">
            GEO target queries (one per line)
          </label>
          <textarea
            value={targetQueriesText}
            onChange={(e) =>
              setForm({
                ...form,
                target_queries: e.target.value.split("\n").map((s) => s.trim()).filter(Boolean),
              })
            }
            className="w-full border border-border rounded px-3 py-2 text-sm h-24 font-mono"
            placeholder={"elevator repair Baltimore\nhow often elevator inspection Maryland"}
          />
          <p className="text-xs text-muted/80 mt-1">
            Custom queries for bi-weekly citation audits (in addition to QUERY_BANK).
          </p>
        </div>
        <div>
          <label className="block text-xs font-medium text-muted mb-1">
            Service page URLs (JSON)
          </label>
          <textarea
            value={serviceUrlsRaw}
            onChange={(e) => setServiceUrlsRaw(e.target.value)}
            className="w-full border border-border rounded px-3 py-2 text-sm h-32 font-mono"
            placeholder={'{\n  "Elevator Repair": "https://example.com/repairs/",\n  "Elevator Inspection": "https://example.com/inspection/"\n}'}
          />
          <p className="text-xs text-muted/80 mt-1">
            Maps service types to live WordPress URLs for Service JSON-LD <code>url</code> field.
          </p>
        </div>
        <button
          type="button"
          onClick={handleSave}
          disabled={update.isPending}
          className="px-4 py-2 bg-cyan text-void rounded text-sm hover:bg-cyan/90 disabled:opacity-50"
        >
          {update.isPending ? "Saving…" : "Save Changes"}
        </button>
      </div>
    </div>
  );
}

