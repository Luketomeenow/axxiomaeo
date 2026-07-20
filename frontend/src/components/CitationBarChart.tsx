import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

interface Props {
  data: {
    brand_id?: string;
    category?: string;
    platform?: string;
    funnel_stage?: string;
    label?: string;
    citation_share: number;
  }[];
  dataKey: string;
  title: string;
}

export function CitationBarChart({ data, dataKey, title }: Props) {
  const chartData = data.map((d) => ({
    name: String((d as Record<string, string | number | undefined>)[dataKey] ?? "Unknown").replace(
      /_/g,
      " "
    ),
    share: d.citation_share,
  }));

  return (
    <div className="aeo-panel p-5">
      <h3 className="aeo-title mb-4">{title}</h3>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={chartData} layout="vertical" margin={{ left: 80 }}>
          <XAxis type="number" domain={[0, 100]} unit="%" />
          <YAxis type="category" dataKey="name" width={75} tick={{ fontSize: 11 }} />
          <Tooltip formatter={(v) => [`${v}%`, "Citation Share"]} />
          <Bar dataKey="share" fill="#22d3ee" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
