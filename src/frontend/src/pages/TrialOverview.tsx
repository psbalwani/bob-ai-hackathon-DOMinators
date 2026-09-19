import { useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { api } from "../lib/api"
import { useAuth } from "../lib/auth"
import { RiskBadge } from "../components/RiskBadge"
import { TrendTag } from "../components/TrendTag"
import { StatTile } from "../components/StatTile"
import { CenteredSpinner, ErrorState } from "../components/Spinner"
import { IconAlertTriangle, IconBuilding, IconCalendar, IconFlag } from "../components/icons"
import type { RiskBand, SiteSummary } from "../types"

type SortKey = "risk_score" | "site_name" | "open_deviation_count"

export function TrialOverview() {
  const navigate = useNavigate()
  const { user, currentProtocolId } = useAuth()
  const currentProtocol = user?.protocols.find((p) => p.protocol_id === currentProtocolId)
  const [query, setQuery] = useState("")
  const [bandFilter, setBandFilter] = useState<RiskBand | "All">("All")
  const [sortKey, setSortKey] = useState<SortKey>("risk_score")

  const summaryQuery = useQuery({
    queryKey: ["dashboard-summary", currentProtocolId],
    queryFn: () => api.getDashboardSummary(currentProtocolId!),
    enabled: !!currentProtocolId,
  })
  const sitesQuery = useQuery({
    queryKey: ["sites", currentProtocolId],
    queryFn: () => api.listSites(currentProtocolId!),
    enabled: !!currentProtocolId,
  })

  const filteredSites = useMemo(() => {
    let sites = sitesQuery.data ?? []
    if (bandFilter !== "All") sites = sites.filter((s) => s.risk_band === bandFilter)
    if (query.trim()) {
      const q = query.trim().toLowerCase()
      sites = sites.filter((s) => s.site_id.toLowerCase().includes(q) || s.site_name.toLowerCase().includes(q))
    }
    return [...sites].sort((a, b) => {
      if (sortKey === "site_name") return a.site_name.localeCompare(b.site_name)
      if (sortKey === "open_deviation_count") return b.open_deviation_count - a.open_deviation_count
      return (b.risk_score ?? -1) - (a.risk_score ?? -1)
    })
  }, [sitesQuery.data, query, bandFilter, sortKey])

  if (!currentProtocolId || summaryQuery.isLoading || sitesQuery.isLoading) return <CenteredSpinner />
  if (summaryQuery.isError || sitesQuery.isError)
    return <ErrorState message="Couldn't reach the Track D gateway. Is the backend running on port 8000?" />

  const summary = summaryQuery.data!

  return (
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
      <header className="mb-6">
        <h1 className="text-xl font-semibold tracking-tight text-ink sm:text-2xl">Trial Overview</h1>
        <p className="mt-1 text-sm text-muted">
          {currentProtocol && <>{currentProtocol.drug} · </>}
          {summary.protocol_id} · {summary.total_sites} sites · {summary.total_patients} patients ·{" "}
          {summary.total_visits.toLocaleString()} visits
        </p>
      </header>

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Total Sites" value={summary.total_sites} icon={<IconBuilding />} accent="brand" />
        <StatTile
          label="High-Risk Sites"
          value={summary.high_risk_sites}
          icon={<IconAlertTriangle />}
          accent="high"
        />
        <StatTile label="Open Deviations" value={summary.open_deviations} icon={<IconFlag />} accent="brand" />
        <StatTile
          label="Total Visits"
          value={summary.total_visits.toLocaleString()}
          icon={<IconCalendar />}
          accent="brand"
        />
      </div>

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-1.5">
          {(["All", "High", "Medium", "Low"] as const).map((band) => (
            <button
              key={band}
              onClick={() => setBandFilter(band)}
              className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                bandFilter === band
                  ? "bg-brand text-white"
                  : "border border-border bg-card text-muted hover:text-ink"
              }`}
            >
              {band}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search sites…"
            className="w-full rounded-lg border border-border bg-card px-3 py-1.5 text-sm text-ink placeholder:text-muted focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand sm:w-56"
          />
          <label className="flex items-center gap-1.5 rounded-lg border border-border bg-card px-2.5 py-1.5 text-sm text-ink focus-within:border-brand focus-within:ring-1 focus-within:ring-brand">
            <span className="text-muted">Sort</span>
            <select
              value={sortKey}
              onChange={(e) => setSortKey(e.target.value as SortKey)}
              className="bg-transparent text-sm text-ink focus:outline-none"
            >
              <option value="risk_score">Risk score</option>
              <option value="site_name">Site name</option>
              <option value="open_deviation_count">Open deviations</option>
            </select>
          </label>
        </div>
      </div>

      {/* Table for sm+ screens -- a data-dense grid is the right shape once there's room for it. */}
      <div className="hidden overflow-hidden rounded-card border border-border bg-card shadow-card sm:block">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-border bg-surface/60 text-xs font-medium uppercase tracking-wide text-muted">
              <th className="px-5 py-3">Site</th>
              <th className="px-5 py-3">Risk score</th>
              <th className="px-5 py-3">Band</th>
              <th className="px-5 py-3">Trend</th>
              <th className="px-5 py-3 text-right">Open deviations</th>
            </tr>
          </thead>
          <tbody>
            {filteredSites.map((site: SiteSummary) => (
              <tr
                key={site.site_id}
                onClick={() => navigate(`/sites/${site.site_id}`)}
                className="group cursor-pointer border-b border-border last:border-0 transition-colors hover:bg-brand-soft/40"
              >
                <td className="px-5 py-3.5">
                  <div className="font-medium text-ink group-hover:text-brand">{site.site_id}</div>
                  <div className="text-xs text-muted">{site.site_name}</div>
                </td>
                <td className="px-5 py-3.5">
                  <RiskMeter score={site.risk_score} band={site.risk_band} />
                </td>
                <td className="px-5 py-3.5">{site.risk_band && <RiskBadge band={site.risk_band} />}</td>
                <td className="px-5 py-3.5">{site.trend && <TrendTag trend={site.trend} />}</td>
                <td className="px-5 py-3.5 text-right font-medium tabular-nums text-ink">
                  {site.open_deviation_count}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filteredSites.length === 0 && (
          <div className="px-5 py-10 text-center text-sm text-muted">No sites match your filters.</div>
        )}
      </div>

      {/* Stacked cards below sm -- every column stays visible without a hidden
          horizontal scroll, which is the wrong pattern for a primary view. */}
      <div className="flex flex-col gap-2.5 sm:hidden">
        {filteredSites.map((site: SiteSummary) => (
          <button
            key={site.site_id}
            onClick={() => navigate(`/sites/${site.site_id}`)}
            className="flex flex-col gap-2.5 rounded-card border border-border bg-card p-4 text-left shadow-card transition-colors active:bg-surface"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="font-medium text-ink">{site.site_id}</div>
                <div className="text-xs text-muted">{site.site_name}</div>
              </div>
              {site.risk_band && <RiskBadge band={site.risk_band} />}
            </div>
            <RiskMeter score={site.risk_score} band={site.risk_band} />
            <div className="flex items-center justify-between text-xs text-muted">
              {site.trend && <TrendTag trend={site.trend} />}
              <span>
                <span className="font-medium tabular-nums text-ink">{site.open_deviation_count}</span> open
                deviations
              </span>
            </div>
          </button>
        ))}
        {filteredSites.length === 0 && (
          <div className="rounded-card border border-border bg-card px-5 py-10 text-center text-sm text-muted">
            No sites match your filters.
          </div>
        )}
      </div>
    </div>
  )
}

function RiskMeter({ score, band }: { score: number | null; band: SiteSummary["risk_band"] }) {
  return (
    <div className="flex items-center gap-2.5">
      <div className="h-2 flex-1 max-w-32 overflow-hidden rounded-full bg-surface">
        <div
          className={`h-full rounded-full transition-all duration-300 ${
            band === "High" ? "bg-risk-high" : band === "Medium" ? "bg-risk-medium" : "bg-risk-low"
          }`}
          style={{ width: `${score ?? 0}%` }}
        />
      </div>
      <span className="font-medium tabular-nums text-ink">{score ?? "–"}</span>
    </div>
  )
}
