import type { ReadinessBand } from "../types"

// Reuses the same reserved risk semantics as RiskBadge (red/amber/green) --
// a readiness verdict is exactly a risk band at the drug level, so it must
// read with the same colors, not a second unrelated palette.
const STYLES: Record<ReadinessBand, string> = {
  "High Risk of Rejection": "bg-risk-high-soft text-risk-high ring-1 ring-inset ring-risk-high/20",
  "Conditional — Remediation Required": "bg-risk-medium-soft text-risk-medium ring-1 ring-inset ring-risk-medium/20",
  "Likely Approval Ready": "bg-risk-low-soft text-risk-low ring-1 ring-inset ring-risk-low/20",
}

const DOT: Record<ReadinessBand, string> = {
  "High Risk of Rejection": "bg-risk-high",
  "Conditional — Remediation Required": "bg-risk-medium",
  "Likely Approval Ready": "bg-risk-low",
}

export function ReadinessBadge({ band, className = "" }: { band: ReadinessBand; className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-sm font-semibold ${STYLES[band]} ${className}`}
    >
      <span className={`h-2 w-2 rounded-full ${DOT[band]}`} />
      {band}
    </span>
  )
}
