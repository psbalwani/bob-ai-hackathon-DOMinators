import type { ReviewStatus } from "../types"

const STYLES: Record<ReviewStatus, string> = {
  pending_review: "bg-risk-medium-soft text-risk-medium",
  approved: "bg-risk-low-soft text-risk-low",
  rejected: "bg-risk-high-soft text-risk-high",
}

const LABELS: Record<ReviewStatus, string> = {
  pending_review: "Pending review",
  approved: "Approved",
  rejected: "Rejected",
}

export function ReviewBadge({ status, className = "" }: { status: ReviewStatus; className?: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${STYLES[status]} ${className}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {LABELS[status]}
    </span>
  )
}

export { LABELS as REVIEW_LABELS }
