import { Bar, BarChart, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

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
   * checks on that platform is simply absent from the row (no bar). */
  rows: Record<string, string | number>[];
  /** Canonical brand order (stable across scopes) — drives color assignment. */
  brands: string[];
  title: string;
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
          <Tooltip
            formatter={(v, name) => [`${v ?? 0}%`, String(name)]}
            labelFormatter={(label) => `Platform: ${label}`}
          />
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
