import { Link } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { api } from "../lib/api"
import { useAuth } from "../lib/auth"
import { Card, CardBody, CardHeader } from "../components/Card"
import { StatTile } from "../components/StatTile"
import { RiskBadge } from "../components/RiskBadge"
import { ReadinessBadge } from "../components/ReadinessBadge"
import { DrugFactorChart } from "../components/DrugFactorChart"
import { CenteredSpinner, ErrorState } from "../components/Spinner"
import { IconAlertTriangle, IconBuilding, IconFlag, IconShieldCheck } from "../components/icons"
import type { RiskBand, Trend } from "../types"

const BAND_BAR_COLOR: Record<RiskBand, string> = {
  High: "bg-risk-high",
  Medium: "bg-risk-medium",
  Low: "bg-risk-low",
}

const TREND_META: Record<Trend, { label: string; icon: string; className: string }> = {
  worsening: { label: "Worsening", icon: "↗", className: "text-risk-high" },
  improving: { label: "Improving", icon: "↘", className: "text-risk-low" },
  stable: { label: "Stable", icon: "→", className: "text-muted" },
  volatile: { label: "Volatile", icon: "↕", className: "text-risk-medium" },
}

const RING_COLOR: Record<string, string> = {
  "High Risk of Rejection": "border-risk-high bg-risk-high-soft",
  "Conditional — Remediation Required": "border-risk-medium bg-risk-medium-soft",
  "Likely Approval Ready": "border-risk-low bg-risk-low-soft",
}

export function DrugPerformance() {
  const { user, currentProtocolId } = useAuth()
  const currentProtocol = user?.protocols.find((p) => p.protocol_id === currentProtocolId)

  const performanceQuery = useQuery({
    queryKey: ["drug-performance", currentProtocolId],
    queryFn: () => api.getDrugPerformance(currentProtocolId!),
    enabled: !!currentProtocolId,
  })

  if (!currentProtocolId || performanceQuery.isLoading) return <CenteredSpinner />
  if (performanceQuery.isError || !performanceQuery.data)
    return <ErrorState message="Couldn't reach the Track D gateway. Is the backend running on port 8000?" />

  const perf = performanceQuery.data
  const totalDeviations =
    perf.deviations_by_severity.Major + perf.deviations_by_severity.Minor + perf.deviations_by_severity.Administrative
  const bandOrder: RiskBand[] = ["High", "Medium", "Low"]

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <header className="mb-6">
        <h1 className="text-xl font-semibold tracking-tight text-ink sm:text-2xl">Drug Performance</h1>
        <p className="mt-1 text-sm text-muted">
          {currentProtocol?.drug ?? perf.protocol_id} · {perf.protocol_id} · {perf.total_sites} sites · aggregated
          across every site for a single, portfolio-level FDA-readiness view
        </p>
      </header>

      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader>
            <div className="text-sm font-medium text-ink">Drug risk index</div>
            <div className="text-xs text-muted">Aggregated across all {perf.total_sites} sites</div>
          </CardHeader>
          <CardBody className="flex flex-col items-center justify-center gap-3 py-8">
            <div
              className={`flex h-28 w-28 items-center justify-center rounded-full border-4 ${RING_COLOR[perf.readiness_band]}`}
            >
              <div className="text-4xl font-semibold tabular-nums text-ink">{perf.drug_risk_index}</div>
            </div>
            <div className="text-xs text-muted">out of 100</div>
            <ReadinessBadge band={perf.readiness_band} />
          </CardBody>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="text-sm font-medium text-ink">Contributing factors</div>
            <div className="text-xs text-muted">Share of the risk index contributed by each aggregate factor</div>
          </CardHeader>
          <CardBody>
            <DrugFactorChart breakdown={perf.factor_breakdown} />
          </CardBody>
        </Card>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Total Sites" value={perf.total_sites} icon={<IconBuilding />} accent="brand" />
        <StatTile
          label="High-Risk Sites"
          value={perf.sites_by_band.High}
          icon={<IconAlertTriangle />}
          accent="high"
        />
        <StatTile label="Total Deviations" value={totalDeviations} icon={<IconFlag />} accent="brand" />
        <StatTile
          label="Unresolved CAPAs"
          value={perf.capa_summary ? perf.capa_summary.pending_review + perf.capa_summary.rejected : "–"}
          icon={<IconShieldCheck />}
          accent={perf.capa_summary && perf.capa_summary.pending_review + perf.capa_summary.rejected > 0 ? "high" : "brand"}
        />
      </div>

      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <div className="text-sm font-medium text-ink">Site risk distribution</div>
          </CardHeader>
          <CardBody>
            <div className="flex h-3 w-full gap-0.5 overflow-hidden rounded-full bg-surface">
              {bandOrder.map((band) =>
                perf.sites_by_band[band] > 0 ? (
                  <div
                    key={band}
                    className={`${BAND_BAR_COLOR[band]} rounded-full`}
                    style={{ width: `${(perf.sites_by_band[band] / perf.total_sites) * 100}%` }}
                    title={`${band}: ${perf.sites_by_band[band]}`}
                  />
                ) : null,
              )}
            </div>
            <div className="mt-4 flex flex-wrap gap-4 text-sm">
              {bandOrder.map((band) => (
                <div key={band} className="flex items-center gap-2">
                  <RiskBadge band={band} />
                  <span className="font-medium tabular-nums text-ink">{perf.sites_by_band[band]}</span>
                  <span className="text-xs text-muted">sites</span>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <div className="text-sm font-medium text-ink">Site trend</div>
          </CardHeader>
          <CardBody>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {(Object.keys(TREND_META) as Trend[]).map((trend) => (
                <div key={trend} className="rounded-lg bg-surface px-3 py-2.5 text-center">
                  <div className={`text-lg font-semibold ${TREND_META[trend].className}`}>
                    <span aria-hidden>{TREND_META[trend].icon}</span> {perf.trend_breakdown[trend]}
                  </div>
                  <div className="mt-0.5 text-[11px] text-muted">{TREND_META[trend].label}</div>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      </div>

      <Card className="mb-6">
        <CardHeader>
          <div className="text-sm font-medium text-ink">Approval readiness rationale</div>
          <div className="text-xs text-muted">Deterministic, data-cited factors — every number ties back to the stats above</div>
        </CardHeader>
        <CardBody>
          <ul className="flex flex-col gap-2.5">
            {perf.rationale.map((line, i) => (
              <li key={i} className="flex gap-2.5 text-sm leading-relaxed text-ink">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" />
                {line}
              </li>
            ))}
            {perf.rationale.length === 0 && (
              <li className="text-sm text-muted">No risk-contributing factors detected — clean site network.</li>
            )}
          </ul>
        </CardBody>
      </Card>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {perf.capa_summary && (
          <Card>
            <CardHeader>
              <div className="text-sm font-medium text-ink">CAPA remediation status</div>
              <div className="text-xs text-muted">{perf.capa_summary.total} CAPA reports generated for this drug</div>
            </CardHeader>
            <CardBody className="grid grid-cols-3 gap-3 text-center">
              <div className="rounded-lg bg-risk-low-soft px-3 py-3">
                <div className="text-lg font-semibold tabular-nums text-risk-low">{perf.capa_summary.approved}</div>
                <div className="mt-0.5 text-[11px] text-muted">Approved</div>
              </div>
              <div className="rounded-lg bg-risk-medium-soft px-3 py-3">
                <div className="text-lg font-semibold tabular-nums text-risk-medium">
                  {perf.capa_summary.pending_review}
                </div>
                <div className="mt-0.5 text-[11px] text-muted">Pending</div>
              </div>
              <div className="rounded-lg bg-risk-high-soft px-3 py-3">
                <div className="text-lg font-semibold tabular-nums text-risk-high">{perf.capa_summary.rejected}</div>
                <div className="mt-0.5 text-[11px] text-muted">Rejected</div>
              </div>
            </CardBody>
          </Card>
        )}

        <Card>
          <CardHeader>
            <div className="text-sm font-medium text-ink">Top risk sites</div>
          </CardHeader>
          <div className="divide-y divide-border">
            {perf.top_risk_sites.map((s) => (
              <Link
                key={s.site_id}
                to={`/sites/${s.site_id}`}
                className="group flex items-center justify-between gap-4 px-5 py-3 transition-colors hover:bg-brand-soft/40"
              >
                <span className="text-sm font-medium text-ink group-hover:text-brand">{s.site_id}</span>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium tabular-nums text-ink">{s.risk_score}</span>
                  <RiskBadge band={s.risk_band} />
                </div>
              </Link>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}
