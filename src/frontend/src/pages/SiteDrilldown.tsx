import { useMemo, useState } from "react"
import { Link, useNavigate, useParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { api } from "../lib/api"
import { RiskBadge } from "../components/RiskBadge"
import { TrendTag } from "../components/TrendTag"
import { Card, CardBody, CardHeader } from "../components/Card"
import { IndicatorBreakdownChart } from "../components/IndicatorBreakdownChart"
import { CenteredSpinner, ErrorState } from "../components/Spinner"
import type { Severity } from "../types"

const SEVERITY_STYLES: Record<Severity, string> = {
  Major: "text-risk-high",
  Minor: "text-risk-medium",
  Administrative: "text-muted",
}

export function SiteDrilldown() {
  const { siteId = "" } = useParams()
  const navigate = useNavigate()
  const [typeFilter, setTypeFilter] = useState<string>("All")

  const siteQuery = useQuery({ queryKey: ["site", siteId], queryFn: () => api.getSite(siteId) })
  const deviationsQuery = useQuery({
    queryKey: ["site-deviations", siteId],
    queryFn: () => api.getSiteDeviations(siteId),
  })
  const capaQuery = useQuery({ queryKey: ["site-capa", siteId], queryFn: () => api.getSiteCapaReports(siteId) })

  const deviationTypes = useMemo(
    () => Array.from(new Set((deviationsQuery.data ?? []).map((d) => d.type))),
    [deviationsQuery.data],
  )
  const filteredDeviations = useMemo(() => {
    const devs = deviationsQuery.data ?? []
    return typeFilter === "All" ? devs : devs.filter((d) => d.type === typeFilter)
  }, [deviationsQuery.data, typeFilter])

  if (siteQuery.isLoading) return <CenteredSpinner />
  if (siteQuery.isError || !siteQuery.data) return <ErrorState message={`Couldn't load site '${siteId}'.`} />

  const site = siteQuery.data
  const score = site.risk_score

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <button
        onClick={() => navigate("/")}
        className="mb-4 inline-flex items-center gap-1 text-sm font-medium text-muted hover:text-ink"
      >
        ← Trial Overview
      </button>

      <header className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-ink sm:text-2xl">{site.site_id}</h1>
          <p className="mt-1 text-sm text-muted">
            {site.site_name} · {site.country}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <TrendTag trend={score.trend} />
          <RiskBadge band={score.risk_band} />
        </div>
      </header>

      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader>
            <div className="text-sm font-medium text-ink">Risk score</div>
          </CardHeader>
          <CardBody className="flex flex-col items-center justify-center gap-2 py-8">
            <div className="text-5xl font-semibold tabular-nums text-ink">{score.risk_score}</div>
            <div className="text-xs text-muted">out of 100</div>
            <div className="mt-3 grid w-full grid-cols-2 gap-2 text-center text-xs text-muted">
              <div>
                <div className="font-medium tabular-nums text-ink">{score.open_deviation_count}</div>
                open deviations
              </div>
              <div>
                <div className="font-medium tabular-nums text-ink">{score.total_visits}</div>
                total visits
              </div>
            </div>
          </CardBody>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="text-sm font-medium text-ink">Indicator breakdown</div>
            <div className="text-xs text-muted">Share of the risk score contributed by each leading indicator</div>
          </CardHeader>
          <CardBody>
            <IndicatorBreakdownChart breakdown={score.indicator_breakdown} />
          </CardBody>
        </Card>
      </div>

      <Card className="mb-6">
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="text-sm font-medium text-ink">Deviations</div>
            <div className="text-xs text-muted">{filteredDeviations.length} shown</div>
          </div>
          {deviationTypes.length > 1 && (
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value)}
              className="rounded-lg border border-border bg-card px-2.5 py-1.5 text-sm text-ink focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
            >
              <option value="All">All types</option>
              {deviationTypes.map((t) => (
                <option key={t} value={t}>
                  {t.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          )}
        </CardHeader>
        <div className="divide-y divide-border">
          {deviationsQuery.isLoading && <div className="px-5 py-6 text-sm text-muted">Loading deviations…</div>}
          {filteredDeviations.map((d) => (
            <Link
              key={d.deviation_id}
              to={`/deviations/${d.deviation_id}`}
              className="flex items-center justify-between gap-4 px-5 py-3.5 transition-colors hover:bg-surface"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-semibold ${SEVERITY_STYLES[d.severity]}`}>{d.severity}</span>
                  <span className="text-sm font-medium text-ink">{d.type.replaceAll("_", " ")}</span>
                </div>
                <div className="mt-0.5 truncate text-xs text-muted">{d.severity_rationale}</div>
              </div>
              <span className="shrink-0 text-xs text-muted">{d.patient_id}</span>
            </Link>
          ))}
          {!deviationsQuery.isLoading && filteredDeviations.length === 0 && (
            <div className="px-5 py-8 text-center text-sm text-muted">No deviations for this filter.</div>
          )}
        </div>
      </Card>

      <Card>
        <CardHeader>
          <div className="text-sm font-medium text-ink">CAPA reports</div>
        </CardHeader>
        <div className="divide-y divide-border">
          {(capaQuery.data ?? []).map((c) => (
            <Link
              key={c.capa_id}
              to={`/capa/${c.capa_id}`}
              className="flex items-center justify-between gap-4 px-5 py-3.5 transition-colors hover:bg-surface"
            >
              <div className="min-w-0">
                <div className="text-sm font-medium text-ink">{c.capa_id}</div>
                <div className="mt-0.5 truncate text-xs text-muted">{c.root_cause}</div>
              </div>
              <span className="shrink-0 rounded-full bg-brand-soft px-2.5 py-1 text-xs font-medium text-brand">
                Due in {c.suggested_due_window_days}d
              </span>
            </Link>
          ))}
          {capaQuery.data?.length === 0 && (
            <div className="px-5 py-8 text-center text-sm text-muted">
              No CAPA report generated for this site yet.
            </div>
          )}
        </div>
      </Card>
    </div>
  )
}
