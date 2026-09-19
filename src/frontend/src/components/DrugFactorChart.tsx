import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import type { DrugFactorBreakdown } from "../types"

// Same shape/purpose as IndicatorBreakdownChart (share of one aggregate
// score contributed by each named factor), one level up: sites -> drug.
// Kept as its own component rather than a generic one because the factor
// keys differ (unresolved_capa_rate is only present when CAPA data is
// available) and the two breakdowns describe different objects.
const LABELS: Record<keyof DrugFactorBreakdown, string> = {
  avg_site_risk: "Average site risk",
  high_risk_site_share: "High-risk site share",
  major_deviation_rate: "Major deviation rate",
  unresolved_capa_rate: "Unresolved CAPAs",
  trend_pressure: "Worsening trend",
}

const COLORS = ["#1d4ed8", "#2563eb", "#3b82f6", "#60a5fa", "#93c5fd"]

export function DrugFactorChart({ breakdown }: { breakdown: DrugFactorBreakdown }) {
  const keys = (Object.keys(breakdown) as (keyof DrugFactorBreakdown)[]).filter((k) => breakdown[k] !== undefined)
  const data = keys
    .map((key) => ({ key, label: LABELS[key], share: Math.round((breakdown[key] as number) * 1000) / 10 }))
    .sort((a, b) => b.share - a.share)

  return (
    <ResponsiveContainer width="100%" height={Math.max(160, data.length * 44)}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24, top: 4, bottom: 4 }}>
        <CartesianGrid horizontal={false} stroke="var(--color-border)" />
        <XAxis
          type="number"
          domain={[0, 100]}
          tickFormatter={(v) => `${v}%`}
          tick={{ fontSize: 11, fill: "var(--color-muted)" }}
          axisLine={{ stroke: "var(--color-border)" }}
          tickLine={false}
        />
        <YAxis
          type="category"
          dataKey="label"
          width={150}
          tick={{ fontSize: 12, fill: "var(--color-ink)" }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          cursor={{ fill: "var(--color-surface)" }}
          formatter={(value) => [`${value}%`, "Share of risk index"]}
          contentStyle={{
            background: "var(--color-card)",
            border: "1px solid var(--color-border)",
            borderRadius: 8,
            fontSize: 12,
          }}
        />
        <Bar dataKey="share" radius={[0, 4, 4, 0]} maxBarSize={18}>
          {data.map((entry, i) => (
            <Cell key={entry.key} fill={COLORS[i % COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
