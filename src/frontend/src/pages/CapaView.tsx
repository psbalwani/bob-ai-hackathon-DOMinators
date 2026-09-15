import { useNavigate, useParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { api, client } from "../lib/api"
import { Card, CardBody, CardHeader } from "../components/Card"
import { CenteredSpinner, ErrorState } from "../components/Spinner"
import type { CapaReport } from "../types"

function Section({ title, body }: { title: string; body: string }) {
  return (
    <div>
      <div className="text-xs font-semibold uppercase tracking-wide text-muted">{title}</div>
      <p className="mt-1.5 text-sm leading-relaxed text-ink">{body}</p>
    </div>
  )
}

export function CapaView() {
  const { capaId = "" } = useParams()
  const navigate = useNavigate()

  const { data: capa, isLoading, isError } = useQuery<CapaReport>({
    queryKey: ["capa", capaId],
    queryFn: () => client.get<CapaReport>(`/capa/${capaId}`).then((r) => r.data),
  })

  if (isLoading) return <CenteredSpinner />
  if (isError || !capa) return <ErrorState message={`Couldn't load CAPA report '${capaId}'.`} />

  return (
    <div className="mx-auto max-w-3xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <button
        onClick={() => navigate(`/sites/${capa.site_id}`)}
        className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-muted hover:text-ink"
      >
        ← {capa.site_id}
      </button>

      <header className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-ink sm:text-2xl">CAPA Report</h1>
          <p className="mt-1 text-sm text-muted">
            {capa.capa_id} · {capa.site_id} · Generated {new Date(capa.generated_at).toLocaleDateString()}
          </p>
        </div>
        <a
          href={api.getCapaExportUrl(capa.capa_id, "markdown")}
          target="_blank"
          rel="noreferrer"
          className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90"
        >
          Export Markdown
        </a>
      </header>

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
