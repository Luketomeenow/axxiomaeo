import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

interface Datum {
  brand_id?: string;
  category?: string;
  platform?: string;
  funnel_stage?: string;
  label?: string;
  citation_share: number;
  /** Underlying counts — when present the hover shows the math behind the %. */
  cited?: number;
  total?: number;
  cited_queries?: number;
  total_queries?: number;
}

interface Props {
  data: Datum[];
  dataKey: string;
  title: string;
}

/** One record = one query asked on one AI platform. */
export const CHECK_DEFINITION =
  "A check = one query on one AI platform; “cited” = the brand was named or its site linked in at least one of the sampled answers.";

interface ShareTooltipProps {
  active?: boolean;
  payload?: {
    payload: { name: string; share: number; cited?: number; total?: number };
  }[];
}

function ShareTooltip({ active, payload }: ShareTooltipProps) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-panel border border-border rounded-md px-3 py-2 text-xs shadow-lg max-w-[240px]">
      <p className="text-ink font-semibold text-sm">{d.name}</p>
      <p className="text-cyan mt-0.5">
        Citation share: {d.share}%
        {d.cited != null && d.total != null ? ` — cited in ${d.cited} of ${d.total} checks` : ""}
      </p>
      <p className="text-muted mt-1 leading-snug">{CHECK_DEFINITION}</p>
    </div>
  );
}

export function CitationBarChart({ data, dataKey, title }: Props) {
  const chartData = data.map((d) => ({
    name: String((d as unknown as Record<string, string | number | undefined>)[dataKey] ?? "Unknown").replace(
      /_/g,
      " "
    ),
    share: d.citation_share,
    cited: d.cited ?? d.cited_queries,
    total: d.total ?? d.total_queries,
  }));

  return (
    <div className="aeo-panel p-5">
      <h3 className="aeo-title mb-4">{title}</h3>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={chartData} layout="vertical" margin={{ left: 80 }}>
          <XAxis type="number" domain={[0, 100]} unit="%" />
          <YAxis type="category" dataKey="name" width={75} tick={{ fontSize: 11 }} />
          <Tooltip content={<ShareTooltip />} />
          <Bar dataKey="share" fill="#22d3ee" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
