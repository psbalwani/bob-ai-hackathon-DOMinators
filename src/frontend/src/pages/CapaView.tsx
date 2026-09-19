import { useState } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, client } from "../lib/api"
import { downloadTextFile } from "../lib/download"
import { Card, CardBody, CardHeader } from "../components/Card"
import { ReviewBadge, REVIEW_LABELS } from "../components/ReviewBadge"
import { CenteredSpinner, ErrorState } from "../components/Spinner"
import { Button } from "../components/Button"
import { IconChevronLeft } from "../components/icons"
import type { CapaReport } from "../types"

/** A multi-type CAPA report's corrective/preventive action is a numbered
 * list ("1. ... 2. ... 3. ...") -- generator.py now joins items with real
 * newlines, but older persisted reports (and any LLM-refined text) may
 * still have them space-separated, so this matches "N. " markers directly
 * rather than only splitting on "\n". Requires markers to be sequential
 * starting at 1 so incidental "on day 2." prose doesn't get misread as a
 * list; falls back to plain text otherwise. */
function parseNumberedList(text: string): string[] | null {
  const markers = [...text.matchAll(/(?:^|\s)(\d+)\.\s+/g)]
  if (markers.length < 2) return null
  if (markers.some((m, i) => Number(m[1]) !== i + 1)) return null

  return markers.map((m, i) => {
    const start = m.index! + m[0].length
    const end = i + 1 < markers.length ? markers[i + 1].index! : text.length
    return text.slice(start, end).trim()
  })
}

function Section({ title, body }: { title: string; body: string }) {
  const items = parseNumberedList(body)
  return (
    <div>
      <div className="text-xs font-semibold uppercase tracking-wide text-muted">{title}</div>
      {items ? (
        <ol className="mt-1.5 list-decimal space-y-1.5 pl-5 text-sm leading-relaxed text-ink marker:text-muted">
          {items.map((item, i) => (
            <li key={i}>{item}</li>
          ))}
        </ol>
      ) : (
        <p className="mt-1.5 text-sm leading-relaxed text-ink">{body}</p>
      )}
    </div>
  )
}

export function CapaView() {
  const { capaId = "" } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [reviewerName, setReviewerName] = useState("")

  const { data: capa, isLoading, isError } = useQuery<CapaReport>({
    queryKey: ["capa", capaId],
    queryFn: () => client.get<CapaReport>(`/capa/${capaId}`).then((r) => r.data),
  })

  const reviewMutation = useMutation({
    mutationFn: (decision: "approve" | "reject") =>
      api.reviewCapa(capaId, decision, reviewerName.trim() || undefined),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["capa", capaId] }),
  })

  const exportMutation = useMutation({
    mutationFn: () => api.exportCapa(capaId, "markdown"),
    onSuccess: (markdown) => downloadTextFile(`${capaId}.md`, markdown, "text/markdown"),
  })

  if (isLoading) return <CenteredSpinner />
  if (isError || !capa) return <ErrorState message={`Couldn't load CAPA report '${capaId}'.`} />

  const isApproved = capa.review_status === "approved"
  const isPending = capa.review_status === "pending_review"

  return (
    <div className="mx-auto max-w-3xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <button
        onClick={() => navigate(`/sites/${capa.site_id}`)}
        className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-muted transition-colors hover:text-ink"
      >
        <IconChevronLeft className="h-3.5 w-3.5" />
        {capa.site_id}
      </button>

      <header className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-xl font-semibold tracking-tight text-ink sm:text-2xl">CAPA Report</h1>
            <ReviewBadge status={capa.review_status} />
          </div>
          <p className="mt-1 text-sm text-muted">
            {capa.capa_id} · {capa.site_id} · Generated {new Date(capa.generated_at).toLocaleDateString()}
            {capa.reviewer && capa.reviewed_at && (
              <>
                {" "}
                · {REVIEW_LABELS[capa.review_status].toLowerCase()} by {capa.reviewer} on{" "}
                {new Date(capa.reviewed_at).toLocaleDateString()}
              </>
            )}
          </p>
        </div>

        {isApproved ? (
          <button
            onClick={() => exportMutation.mutate()}
            disabled={exportMutation.isPending}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-strong disabled:opacity-50"
          >
            {exportMutation.isPending ? "Exporting…" : "Export Markdown"}
          </button>
        ) : (
          <span
            title="This report must be approved before it can be exported"
            className="inline-flex shrink-0 cursor-not-allowed items-center gap-1.5 rounded-lg border border-border px-4 py-2 text-sm font-medium text-muted"
          >
            Export requires approval
          </span>
        )}
      </header>

      {isPending && (
        <Card className="mb-4 border-risk-medium/30 bg-risk-medium-soft/40">
          <CardBody className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-sm font-medium text-ink">Review this report before it's finalized</div>
              <div className="text-xs text-muted">
                A human reviewer must approve a CAPA report before it can be exported or sent to a site.
              </div>
            </div>
            <div className="flex items-center gap-2">
              <input
                value={reviewerName}
                onChange={(e) => setReviewerName(e.target.value)}
                placeholder="Your name (optional)"
                className="w-40 rounded-lg border border-border bg-card px-3 py-1.5 text-sm text-ink placeholder:text-muted focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
              />
              <Button size="sm" onClick={() => reviewMutation.mutate("reject")} disabled={reviewMutation.isPending}>
                Reject
              </Button>
              <Button
                size="sm"
                variant="success"
                onClick={() => reviewMutation.mutate("approve")}
                disabled={reviewMutation.isPending}
              >
                Approve
              </Button>
            </div>
          </CardBody>
        </Card>
      )}

      {!isPending && (
        <div className="mb-4 flex justify-end">
          <button
            onClick={() => reviewMutation.mutate(isApproved ? "reject" : "approve")}
            disabled={reviewMutation.isPending}
            className="text-xs font-medium text-muted underline decoration-dotted hover:text-ink disabled:opacity-50"
          >
            {isApproved ? "Revoke approval" : "Reconsider — mark as approved instead"}
          </button>
        </div>
      )}

      <div className="mb-4 grid grid-cols-2 gap-3">
        <Card>
          <CardBody className="py-4">
            <div className="text-xs font-medium uppercase tracking-wide text-muted">Owner</div>
            <div className="mt-1 text-sm font-semibold text-ink">{capa.suggested_owner_role}</div>
          </CardBody>
        </Card>
        <Card>
          <CardBody className="py-4">
            <div className="text-xs font-medium uppercase tracking-wide text-muted">Due window</div>
            <div className="mt-1 text-sm font-semibold text-ink">{capa.suggested_due_window_days} days</div>
          </CardBody>
        </Card>
      </div>

      <Card className="mb-4">
        <CardBody className="flex flex-col gap-5">
          <Section title="Root cause" body={capa.root_cause} />
          <Section title="Corrective action" body={capa.corrective_action} />
          <Section title="Preventive action" body={capa.preventive_action} />
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <div className="text-sm font-medium text-ink">Evidence citations</div>
          <div className="text-xs text-muted">Every claim traces back to a real deviation or clause</div>
        </CardHeader>
        <CardBody className="flex flex-wrap gap-2">
          {capa.evidence_citations.map((c) => (
            <span
              key={c}
              className="rounded-full border border-border bg-surface px-3 py-1 text-xs font-medium text-ink"
            >
              {c}
            </span>
          ))}
        </CardBody>
      </Card>
    </div>
  )
}
