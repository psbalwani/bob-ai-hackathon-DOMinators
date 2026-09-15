import type { ReactNode } from "react"

type Accent = "high" | "brand" | "default"

const ACCENT_TEXT: Record<Accent, string> = {
  high: "text-risk-high",
  brand: "text-brand",
  default: "text-ink",
}

const ACCENT_ICON: Record<Accent, string> = {
  high: "bg-risk-high-soft text-risk-high",
  brand: "bg-brand-soft text-brand",
  default: "bg-surface text-muted",
}

export function StatTile({
  label,
  value,
  accent = "default",
  icon,
}: {
  label: string
  value: string | number
  accent?: Accent
  icon?: ReactNode
}) {
  return (
    <div className="rounded-card border border-border bg-card px-5 py-4 shadow-card">
      <div className="flex items-center justify-between gap-2">
        <div className="text-xs font-medium uppercase tracking-wide text-muted">{label}</div>
        {icon && (
          <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${ACCENT_ICON[accent]}`}>
            {icon}
          </div>
        )}
      </div>
      <div className={`mt-1.5 text-2xl font-semibold tabular-nums ${ACCENT_TEXT[accent]}`}>{value}</div>
    </div>
  )
}
