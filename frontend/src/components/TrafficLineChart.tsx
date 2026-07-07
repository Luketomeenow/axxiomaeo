import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TrafficTrendResponse } from "../types";

const COLORS = ["#22d3ee", "#34d399", "#a78bfa", "#fbbf24", "#60a5fa"];

interface Props {
  data: TrafficTrendResponse;
}

export function TrafficLineChart({ data }: Props) {
  if (!data.configured || data.brands.length === 0) {
    const message =
      data.reason === "no_credentials"
        ? "GA4 property IDs are configured, but GOOGLE_SERVICE_ACCOUNT_JSON is missing in backend/.env. Add a base64-encoded Google service account with Analytics read access."
        : "Connect GA4 property IDs in Brand Settings to see AI-referred traffic from ChatGPT, Perplexity, and other AI sources.";

    return (
      <div className="aeo-panel p-5">
        <h3 className="aeo-title mb-2">Search vs Generative Traffic (90 days)</h3>
        <p className="text-sm text-muted">
          {data.reason === "no_ga4" ? (
            <>
              Connect GA4 property IDs in{" "}
              <a href="/settings/brands" className="aeo-link">
                Brand Settings
              </a>{" "}
              to see AI-referred traffic from ChatGPT, Perplexity, and other AI sources.
            </>
          ) : (
            message
          )}
        </p>
      </div>
    );
  }

  // Aggregate across brands into two series: organic search vs AI-referred.
  const totals = new Map<string, { organic: number; ai: number }>();
  for (const brand of data.brands) {
    const aiSeries = brand.ai_data ?? brand.data;
    const organicSeries = brand.organic_data ?? [];
    for (const point of aiSeries) {
      const e = totals.get(point.date) ?? { organic: 0, ai: 0 };
      e.ai += point.sessions;
      totals.set(point.date, e);
    }
    for (const point of organicSeries) {
      const e = totals.get(point.date) ?? { organic: 0, ai: 0 };
      e.organic += point.sessions;
      totals.set(point.date, e);
    }
  }

  const chartData = Array.from(totals.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, v]) => ({ date, organic: v.organic, ai: v.ai }));

  return (
    <div className="aeo-panel p-5">
      <h3 className="aeo-title mb-4">Search vs Generative Traffic (90 days)</h3>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 10 }}
            tickFormatter={(v) => v.slice(5)}
          />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Legend />
          <Line
            type="monotone"
            dataKey="organic"
            name="Organic Search"
            stroke={COLORS[1]}
            dot={false}
            strokeWidth={2}
          />
          <Line
            type="monotone"
            dataKey="ai"
            name="AI-Referred"
            stroke={COLORS[0]}
            dot={false}
            strokeWidth={2}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
