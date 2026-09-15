import type { RiskBand } from "../types"

const STYLES: Record<RiskBand, string> = {
  High: "bg-risk-high-soft text-risk-high ring-1 ring-inset ring-risk-high/20",
  Medium: "bg-risk-medium-soft text-risk-medium ring-1 ring-inset ring-risk-medium/20",
  Low: "bg-risk-low-soft text-risk-low ring-1 ring-inset ring-risk-low/20",
}

const DOT: Record<RiskBand, string> = {
  High: "bg-risk-high",
  Medium: "bg-risk-medium",
  Low: "bg-risk-low",
}

export function RiskBadge({ band, className = "" }: { band: RiskBand; className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${STYLES[band]} ${className}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${DOT[band]}`} />
      {band}
    </span>
  )
}
