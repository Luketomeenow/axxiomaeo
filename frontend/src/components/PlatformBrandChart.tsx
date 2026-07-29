import { Bar, BarChart, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { CHECK_DEFINITION } from "./CitationBarChart";

/** Fixed categorical slots (CVD-validated against the app panel surface
 * #151b24 — lightness band, chroma, adjacent-pair CVD ΔE≥8, normal-vision
 * ΔE≥15, contrast ≥3:1 all pass). Color follows the brand: slots are assigned
 * by canonical brand order, never by position in the currently filtered set,
 * so changing audit scope never repaints a surviving brand. */
const SERIES_COLORS = [
  "#3987e5", // blue
  "#008300", // green
  "#d55181", // magenta
  "#c98500", // yellow
  "#199e70", // aqua
  "#d95926", // orange
  "#9085e9", // violet
  "#e66767", // red
];

export function brandColor(brand: string, canonicalOrder: string[]): string {
  const idx = canonicalOrder.indexOf(brand);
  return SERIES_COLORS[(idx >= 0 ? idx : canonicalOrder.length) % SERIES_COLORS.length];
}

interface Props {
  /** One row per platform: { platform, [brandId]: sharePct } — a brand with no
   * checks on that platform is simply absent from the row (no bar). Rows may
   * also carry `${brandId}__cited` / `${brandId}__total` counts, which the
   * hover uses to show the math behind each share. */
  rows: Record<string, string | number>[];
  /** Canonical brand order (stable across scopes) — drives color assignment. */
  brands: string[];
  title: string;
}

interface PlatformTooltipProps {
  active?: boolean;
  label?: string | number;
  payload?: {
    dataKey?: string | number;
    name?: string;
    value?: number;
    color?: string;
    payload: Record<string, string | number | undefined>;
  }[];
}

function PlatformTooltip({ active, payload, label }: PlatformTooltipProps) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="bg-panel border border-border rounded-md px-3 py-2 text-xs shadow-lg max-w-[260px]">
      <p className="text-ink font-semibold text-sm">Platform: {label}</p>
      {payload.map((entry) => {
        const key = String(entry.dataKey);
        const cited = row[`${key}__cited`];
        const total = row[`${key}__total`];
        return (
          <p key={key} className="mt-0.5" style={{ color: entry.color }}>
            {entry.name}:{" "}
            {entry.value == null
              ? "no checks on this platform"
              : `${entry.value}%${
                  cited != null && total != null ? ` — cited in ${cited} of ${total} checks` : ""
                }`}
          </p>
        );
      })}
      <p className="text-muted mt-1 leading-snug">{CHECK_DEFINITION}</p>
    </div>
  );
}

export function PlatformBrandChart({ rows, brands, title }: Props) {
  const height = Math.max(220, rows.length * (brands.length * 14 + 26) + 60);
  return (
    <div className="aeo-panel p-5">
      <h3 className="aeo-title mb-4">{title}</h3>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={rows} layout="vertical" margin={{ left: 80 }} barGap={2} barCategoryGap="18%">
          <XAxis type="number" domain={[0, 100]} unit="%" tick={{ fontSize: 11 }} />
          <YAxis type="category" dataKey="platform" width={75} tick={{ fontSize: 11 }} />
          <Tooltip content={<PlatformTooltip />} />
          <Legend wrapperStyle={{ fontSize: 12 }} iconSize={10} />
          {brands.map((b) => (
            <Bar
              key={b}
              dataKey={b}
              name={b.replace(/_/g, " ")}
              fill={brandColor(b, brands)}
              barSize={10}
              radius={[0, 4, 4, 0]}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
