import type { Trend } from "../types"

const CONFIG: Record<Trend, { label: string; icon: string; className: string }> = {
  worsening: { label: "Worsening", icon: "↗", className: "text-risk-high" },
  improving: { label: "Improving", icon: "↘", className: "text-risk-low" },
  stable: { label: "Stable", icon: "→", className: "text-muted" },
  volatile: { label: "Volatile", icon: "↕", className: "text-risk-medium" },
}

export function TrendTag({ trend, className = "" }: { trend: Trend; className?: string }) {
  const c = CONFIG[trend]
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-medium ${c.className} ${className}`}>
      <span aria-hidden>{c.icon}</span>
      {c.label}
    </span>
  )
}
