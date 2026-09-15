import { useNavigate, useParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { api } from "../lib/api"
import { Card, CardBody, CardHeader } from "../components/Card"
import { CenteredSpinner, ErrorState } from "../components/Spinner"
import { IconChevronLeft } from "../components/icons"
import type { Severity } from "../types"

const SEVERITY_STYLES: Record<Severity, string> = {
  Major: "bg-risk-high-soft text-risk-high",
  Minor: "bg-risk-medium-soft text-risk-medium",
  Administrative: "bg-surface text-muted",
}

function Field({ label, value }: { label: string; value: string | number | null }) {
  return (
    <div className="rounded-lg bg-surface px-3 py-2.5">
      <div className="text-[10px] font-medium uppercase tracking-wide text-muted">{label}</div>
      <div className="mt-0.5 text-sm font-medium text-ink">{value ?? "—"}</div>
    </div>
  )
}

export function DeviationDetail() {
  const { deviationId = "" } = useParams()
  const navigate = useNavigate()

  const { data, isLoading, isError } = useQuery({
    queryKey: ["deviation", deviationId],
    queryFn: () => api.getDeviationDetail(deviationId),
  })

  if (isLoading) return <CenteredSpinner />
  if (isError || !data) return <ErrorState message={`Couldn't load deviation '${deviationId}'.`} />

  const { deviation, visit_record: visit } = data

  return (
    <div className="mx-auto max-w-3xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <button
        onClick={() => navigate(`/sites/${deviation.site_id}`)}
        className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-muted transition-colors hover:text-ink"
      >
        <IconChevronLeft className="h-3.5 w-3.5" />
        {deviation.site_id}
      </button>

      <header className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-ink sm:text-2xl">
            {deviation.type.replaceAll("_", " ")}
          </h1>
          <p className="mt-1 text-sm text-muted">{deviation.deviation_id}</p>
        </div>
        <span
          className={`shrink-0 rounded-full px-3 py-1.5 text-sm font-semibold ${SEVERITY_STYLES[deviation.severity]}`}
        >
          {deviation.severity}
        </span>
      </header>

      <Card className="mb-4">
        <CardHeader>
          <div className="text-sm font-medium text-ink">Severity rationale</div>
        </CardHeader>
        <CardBody>
          <p className="text-sm leading-relaxed text-ink">{deviation.severity_rationale}</p>
          <div className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-brand-soft px-3 py-1 text-xs font-medium text-brand">
            {deviation.protocol_clause_ref}
          </div>
        </CardBody>
      </Card>

      <Card className="mb-4">
        <CardHeader>
          <div className="text-sm font-medium text-ink">Deviation record</div>
        </CardHeader>
        <CardBody className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <Field label="Patient" value={deviation.patient_id} />
          <Field label="Site" value={deviation.site_id} />
          <Field label="Visit record" value={deviation.visit_record_id} />
          <Field label="Detected at" value={new Date(deviation.detected_at).toLocaleString()} />
          <Field label="Detector version" value={deviation.detector_version} />
          <Field label="Protocol" value={deviation.protocol_id} />
        </CardBody>
      </Card>

      {visit && (
        <Card>
          <CardHeader>
            <div className="text-sm font-medium text-ink">Visit record</div>
          </CardHeader>
          <CardBody className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <Field label="Visit" value={visit.visit_id} />
            <Field label="Scheduled date" value={visit.scheduled_date} />
            <Field label="Actual date" value={visit.actual_date} />
            <Field label="Dosage (mg)" value={visit.dosage_administered_mg} />
            <Field label="Co-medications" value={visit.comedications.join(", ") || "None"} />
            <Field label="Procedures completed" value={visit.procedures_completed.join(", ") || "None"} />
          </CardBody>
        </Card>
      )}
    </div>
  )
}
