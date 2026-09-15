export function StatTile({
  label,
  value,
  accent,
}: {
  label: string
  value: string | number
  accent?: "high" | "default"
}) {
  return (
    <div className="rounded-card border border-border bg-card px-5 py-4">
      <div className="text-xs font-medium uppercase tracking-wide text-muted">{label}</div>
      <div className={`mt-1.5 text-2xl font-semibold tabular-nums ${accent === "high" ? "text-risk-high" : "text-ink"}`}>
        {value}
      </div>
    </div>
  )
}
