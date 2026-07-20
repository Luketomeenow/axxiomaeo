import type { SearchVsGenerative } from "../types";

interface Props {
  data: SearchVsGenerative;
}

function Metric({ label, value, suffix = "" }: { label: string; value: number | string; suffix?: string }) {
  return (
    <div className="flex items-baseline justify-between py-1.5 border-b border-border/60 last:border-0">
      <span className="text-sm text-muted">{label}</span>
      <span className="text-lg font-bold text-ink">
        {value}
        {suffix}
      </span>
    </div>
  );
}

export function SearchVsGenerativePanel({ data }: Props) {
  const { search, generative } = data;
  const fmt = (n: number) => n.toLocaleString();

  return (
    <div className="grid md:grid-cols-2 gap-6">
      {/* Traditional Search */}
      <div className="aeo-panel p-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="aeo-title">Traditional Search</h3>
          <span className="text-xs text-muted">Google / Bing organic</span>
        </div>
        {search.configured ? (
          <>
            <p className="text-xs uppercase tracking-wide text-muted/70 mt-2 mb-1">Visibility</p>
            <Metric label="Impressions (30d)" value={fmt(search.visibility.impressions)} />
            <Metric label="Clicks (30d)" value={fmt(search.visibility.clicks)} />
            <Metric label="Avg. position" value={search.visibility.avg_position || "—"} />
            <p className="text-xs uppercase tracking-wide text-muted/70 mt-4 mb-1">Traffic</p>
            <Metric label="Organic search sessions" value={fmt(search.traffic.organic_search_sessions)} />
            <Metric
              label="Conversions (30d)"
              value={`${fmt(search.traffic.conversions ?? 0)} (${search.traffic.conversion_rate ?? 0}%)`}
            />
          </>
        ) : (
          <p className="text-sm text-muted">
            Connect Google Search Console &amp; GA4 — set <code>GOOGLE_SERVICE_ACCOUNT_JSON</code> and each
            brand&apos;s Search Console URL / GA4 property ID in{" "}
            <a href="/settings/brands" className="aeo-link">Brand Settings</a>.
          </p>
        )}
      </div>

      {/* Generative / AI */}
      <div className="aeo-panel p-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="aeo-title">Generative / AI</h3>
          <span className="text-xs text-muted">ChatGPT · Perplexity · Gemini · AI Overviews</span>
        </div>
        <p className="text-xs uppercase tracking-wide text-muted/70 mt-2 mb-1">Visibility</p>
        <Metric label="Citation share" value={generative.visibility.citation_share} suffix="%" />
        <Metric label="Avg. visibility" value={generative.visibility.avg_visibility_pct} suffix="%" />
        <Metric label="Share of voice" value={generative.visibility.share_of_voice} suffix="%" />
        <p className="text-xs uppercase tracking-wide text-muted/70 mt-4 mb-1">Traffic</p>
        <Metric label="AI-referred sessions" value={fmt(generative.traffic.ai_referred_sessions)} />
        <Metric
          label="Conversions (30d)"
          value={`${fmt(generative.traffic.conversions ?? 0)} (${generative.traffic.conversion_rate ?? 0}%)`}
        />
      </div>
    </div>
  );
}
