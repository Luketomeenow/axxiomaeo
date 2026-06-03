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

const COLORS = ["#1a3a5c", "#c8410a", "#1a7a4a", "#b8962e", "#4b6899"];

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
      <div className="bg-white rounded border border-black/8 p-5">
        <h3 className="font-display text-base font-bold text-navy mb-2">
          AI-Referred Traffic Trend (90 days)
        </h3>
        <p className="text-sm text-black/50">
          {data.reason === "no_ga4" ? (
            <>
              Connect GA4 property IDs in{" "}
              <a href="/settings/brands" className="text-orange hover:underline">
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

  const topBrands = [...data.brands]
    .sort(
      (a, b) =>
        b.data.reduce((s, d) => s + d.sessions, 0) -
        a.data.reduce((s, d) => s + d.sessions, 0)
    )
    .slice(0, 5);

  const dateMap = new Map<string, Record<string, number>>();
  for (const brand of topBrands) {
    for (const point of brand.data) {
      if (!dateMap.has(point.date)) dateMap.set(point.date, {});
      dateMap.get(point.date)![brand.brand_id] = point.sessions;
    }
  }

  const chartData = Array.from(dateMap.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, values]) => ({ date, ...values }));

  return (
    <div className="bg-white rounded border border-black/8 p-5">
      <h3 className="font-display text-base font-bold text-navy mb-4">
        AI-Referred Traffic Trend (90 days)
      </h3>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#00000010" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 10 }}
            tickFormatter={(v) => v.slice(5)}
          />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Legend />
          {topBrands.map((brand, i) => (
            <Line
              key={brand.brand_id}
              type="monotone"
              dataKey={brand.brand_id}
              name={brand.brand_name}
              stroke={COLORS[i % COLORS.length]}
              dot={false}
              strokeWidth={2}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
