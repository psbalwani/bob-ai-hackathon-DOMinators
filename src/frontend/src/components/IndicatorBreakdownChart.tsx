import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"
import type { IndicatorBreakdown } from "../types"

const LABELS: Record<keyof IndicatorBreakdown, string> = {
  severity_mix_weight: "Severity mix",
  deviation_frequency: "Deviation frequency",
  repeat_offense_rate: "Repeat offense rate",
  recency_weight: "Recency",
  trend_slope: "Trend",
}

const COLORS = ["#1d4ed8", "#2563eb", "#3b82f6", "#60a5fa", "#93c5fd"]

export function IndicatorBreakdownChart({ breakdown }: { breakdown: IndicatorBreakdown }) {
  const data = (Object.keys(LABELS) as (keyof IndicatorBreakdown)[]).map((key) => ({
    key,
    label: LABELS[key],
    share: Math.round(breakdown[key] * 1000) / 10,
  }))

  return (
    <ResponsiveContainer width="100%" height={220}>
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
          width={120}
          tick={{ fontSize: 12, fill: "var(--color-ink)" }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip
          cursor={{ fill: "var(--color-surface)" }}
          formatter={(value) => [`${value}%`, "Share of score"]}
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
