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
import type { ReportListItem } from "../types";

/** Citation share / AI sessions / content published across historical report months. */
export function ReportTrendChart({ reports }: { reports: ReportListItem[] }) {
  // Oldest → newest along the X axis.
  const data = [...reports]
    .filter((r) => r.report_month)
    .sort((a, b) => (a.report_month! < b.report_month! ? -1 : 1))
    .map((r) => ({
      month: (r.report_month ?? "").slice(0, 7), // YYYY-MM
      citation_share: Number(r.overall_citation_share ?? 0),
      ai_sessions: Number(r.ai_referred_sessions ?? 0),
      content: Number(r.content_pieces_published ?? 0),
    }));

  if (data.length < 2) {
    return (
      <div className="aeo-panel px-4 py-10 text-center text-muted/80">
        Need at least two monthly reports to plot a trend. Generate a report each month (or click
        Generate) and this fills in over time.
      </div>
    );
  }

  return (
    <div className="aeo-panel p-5">
      <h3 className="aeo-title mb-1">Performance over time</h3>
      <p className="text-xs text-muted mb-4">Citation share and AI-referred sessions by report month.</p>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ left: 4, right: 12, top: 8 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="month" tick={{ fontSize: 11 }} />
          <YAxis yAxisId="left" tick={{ fontSize: 11 }} unit="%" />
          <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} />
          <Tooltip />
          <Legend />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="citation_share"
            name="Citation share %"
            stroke="#22d3ee"
            strokeWidth={2}
            dot={{ r: 3 }}
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="ai_sessions"
            name="AI sessions"
            stroke="#34d399"
            strokeWidth={2}
            dot={{ r: 3 }}
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="content"
            name="Content published"
            stroke="#fbbf24"
            strokeWidth={2}
            dot={{ r: 3 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
