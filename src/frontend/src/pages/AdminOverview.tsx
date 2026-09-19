import { useMemo } from "react"
import { useNavigate } from "react-router-dom"
import { useQueries } from "@tanstack/react-query"
import { api } from "../lib/api"
import { useAuth } from "../lib/auth"
import { StatTile } from "../components/StatTile"
import { Card } from "../components/Card"
import { ReadinessBadge } from "../components/ReadinessBadge"
import { Spinner } from "../components/Spinner"
import { IconAlertTriangle, IconBuilding, IconShieldCheck } from "../components/icons"
import type { DashboardSummary, DrugPerformance } from "../types"

/** All-drugs view for an owner with more than one protocol -- fetches every
 * owned protocol's dashboard summary + FDA-readiness verdict in parallel
 * (each request already scoped/authorized by the existing per-protocol
 * endpoints) so an admin sees every trial at a glance instead of switching
 * or logging back in one drug at a time. */
export function AdminOverview() {
  const { user, setCurrentProtocolId } = useAuth()
  const navigate = useNavigate()
  const protocols = user?.protocols ?? []

  const summaryQueries = useQueries({
    queries: protocols.map((p) => ({
      queryKey: ["dashboard-summary", p.protocol_id],
      queryFn: () => api.getDashboardSummary(p.protocol_id),
    })),
  })
  const performanceQueries = useQueries({
    queries: protocols.map((p) => ({
      queryKey: ["drug-performance", p.protocol_id],
      queryFn: () => api.getDrugPerformance(p.protocol_id),
    })),
  })

  const rows = protocols.map((p, i) => ({
    protocol: p,
    summary: summaryQueries[i],
    performance: performanceQueries[i],
  }))

  const totals = useMemo(() => {
    const loaded = rows.map((r) => r.summary.data).filter((d): d is DashboardSummary => !!d)
    const loadedPerf = rows.map((r) => r.performance.data).filter((d): d is DrugPerformance => !!d)
    return {
      drugs: protocols.length,
      totalSites: loaded.reduce((sum, d) => sum + d.total_sites, 0),
      openDeviations: loaded.reduce((sum, d) => sum + d.open_deviations, 0),
      highRiskSites: loaded.reduce((sum, d) => sum + d.high_risk_sites, 0),
      needsRemediation: loadedPerf.filter((d) => d.readiness_band !== "Likely Approval Ready").length,
    }
  }, [rows, protocols.length])

  function viewDrug(protocolId: string, path: "/" | "/drug-performance" = "/") {
    setCurrentProtocolId(protocolId)
    navigate(path)
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <header className="mb-6">
        <h1 className="text-xl font-semibold tracking-tight text-ink sm:text-2xl">All Drugs</h1>
        <p className="mt-1 text-sm text-muted">
          {totals.drugs} drug trial{totals.drugs === 1 ? "" : "s"} you own, at a glance — no need to switch or
          log back in to check another.
        </p>
      </header>

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Drug Trials" value={totals.drugs} icon={<IconBuilding />} accent="brand" />
        <StatTile label="Total Sites" value={totals.totalSites} icon={<IconBuilding />} accent="brand" />
        <StatTile
          label="High-Risk Sites"
          value={totals.highRiskSites}
          icon={<IconAlertTriangle />}
          accent="high"
        />
        <StatTile
          label="Need Remediation"
          value={totals.needsRemediation}
          icon={<IconShieldCheck />}
          accent={totals.needsRemediation > 0 ? "high" : "brand"}
        />
      </div>

      <div className="hidden overflow-hidden rounded-card border border-border bg-card shadow-card sm:block">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-border bg-surface/60 text-xs font-medium uppercase tracking-wide text-muted">
              <th className="px-5 py-3">Drug</th>
              <th className="px-5 py-3">Sites</th>
              <th className="px-5 py-3">Patients</th>
              <th className="px-5 py-3">High-Risk Sites</th>
              <th className="px-5 py-3">Open Deviations</th>
              <th className="px-5 py-3">FDA Readiness</th>
              <th className="px-5 py-3" />
            </tr>
          </thead>
          <tbody>
            {rows.map(({ protocol, summary, performance }) => (
              <tr
                key={protocol.protocol_id}
                onClick={() => viewDrug(protocol.protocol_id)}
                className="group cursor-pointer border-b border-border last:border-0 transition-colors hover:bg-brand-soft/40"
              >
                <td className="px-5 py-3.5">
                  <div className="font-medium text-ink group-hover:text-brand">{protocol.drug}</div>
                  <div className="text-xs text-muted">{protocol.protocol_id}</div>
                </td>
                {summary.isLoading ? (
                  <td colSpan={4} className="px-5 py-3.5 text-muted">
                    <Spinner className="h-4 w-4" />
                  </td>
                ) : summary.isError || !summary.data ? (
                  <td colSpan={4} className="px-5 py-3.5 text-xs text-risk-high">
                    Couldn't load this trial's summary.
                  </td>
                ) : (
                  <>
                    <td className="px-5 py-3.5 tabular-nums text-ink">{summary.data.total_sites}</td>
                    <td className="px-5 py-3.5 tabular-nums text-ink">{summary.data.total_patients}</td>
                    <td className="px-5 py-3.5 tabular-nums">
                      <span className={summary.data.high_risk_sites > 0 ? "font-medium text-risk-high" : "text-ink"}>
                        {summary.data.high_risk_sites}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 tabular-nums text-ink">{summary.data.open_deviations}</td>
                  </>
                )}
                <td className="px-5 py-3.5" onClick={(e) => e.stopPropagation()}>
                  {performance.data ? (
                    <button onClick={() => viewDrug(protocol.protocol_id, "/drug-performance")}>
                      <ReadinessBadge band={performance.data.readiness_band} className="text-xs" />
                    </button>
                  ) : performance.isLoading ? (
                    <Spinner className="h-4 w-4" />
                  ) : (
                    <span className="text-xs text-muted">—</span>
                  )}
                </td>
                <td className="px-5 py-3.5 text-right text-xs font-medium text-brand opacity-0 transition-opacity group-hover:opacity-100">
                  View →
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Stacked cards below sm, matching the Trial Overview pattern. */}
      <div className="flex flex-col gap-2.5 sm:hidden">
        {rows.map(({ protocol, summary, performance }) => (
          <button
            key={protocol.protocol_id}
            onClick={() => viewDrug(protocol.protocol_id)}
            className="flex flex-col gap-2.5 rounded-card border border-border bg-card p-4 text-left shadow-card transition-colors active:bg-surface"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="font-medium text-ink">{protocol.drug}</div>
                <div className="text-xs text-muted">{protocol.protocol_id}</div>
              </div>
              {performance.data && <ReadinessBadge band={performance.data.readiness_band} className="text-[11px]" />}
            </div>
            {summary.isLoading ? (
              <Spinner className="h-4 w-4" />
            ) : summary.isError || !summary.data ? (
              <div className="text-xs text-risk-high">Couldn't load this trial's summary.</div>
            ) : (
              <div className="flex items-center gap-4 text-xs text-muted">
                <span>
                  <span className="font-medium tabular-nums text-ink">{summary.data.total_sites}</span> sites
                </span>
                <span>
                  <span className="font-medium tabular-nums text-ink">{summary.data.total_patients}</span> patients
                </span>
                <span>
                  <span className="font-medium tabular-nums text-ink">{summary.data.open_deviations}</span> open
                  deviations
                </span>
              </div>
            )}
          </button>
        ))}
      </div>

      {protocols.length === 0 && (
        <Card className="px-5 py-10 text-center text-sm text-muted">No drug trials on this account.</Card>
      )}
    </div>
  )
}
