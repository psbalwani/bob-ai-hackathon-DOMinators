import axios from "axios"
import type {
  CapaReport,
  DashboardSummary,
  Deviation,
  Protocol,
  SiteDetail,
  SiteSummary,
  VisitRecord,
} from "../types"

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"

export const client = axios.create({ baseURL: BASE_URL })

const PROTOCOL_ID = "TRIAL-2026-ONC-04"

export const api = {
  protocolId: PROTOCOL_ID,

  getProtocol: () => client.get<Protocol>("/protocol").then((r) => r.data),

  getDashboardSummary: () =>
    client
      .get<DashboardSummary>("/dashboard/summary", { params: { protocol_id: PROTOCOL_ID } })
      .then((r) => r.data),

  runPipeline: () => client.post("/pipeline/run", { protocol_id: PROTOCOL_ID }).then((r) => r.data),

  listSites: () =>
    client.get<{ sites: SiteSummary[] }>("/sites", { params: { protocol_id: PROTOCOL_ID } }).then((r) => r.data.sites),

  getSite: (siteId: string) => client.get<SiteDetail>(`/sites/${siteId}`).then((r) => r.data),

  getSiteDeviations: (siteId: string) =>
    client.get<{ deviations: Deviation[] }>(`/sites/${siteId}/deviations`).then((r) => r.data.deviations),

  getSiteVisits: (siteId: string) =>
    client.get<{ visits: VisitRecord[] }>(`/sites/${siteId}/visits`).then((r) => r.data.visits),

  getSiteCapaReports: (siteId: string) =>
    client.get<{ capa_reports: CapaReport[] }>(`/sites/${siteId}/capa`).then((r) => r.data.capa_reports),

  getDeviationDetail: (deviationId: string) =>
    client
      .get<{ deviation: Deviation; visit_record: VisitRecord | null }>(`/deviations/${deviationId}`)
      .then((r) => r.data),

  generateCapa: (siteId: string, deviationIds?: string[]) =>
    client
      .post<CapaReport>("/capa/generate", { scope: "site", site_id: siteId, deviation_ids: deviationIds })
      .then((r) => r.data),

  getCapaExportUrl: (capaId: string, format: "markdown" | "pdf" = "markdown") =>
    `${BASE_URL}/capa/${capaId}/export?format=${format}`,

  reviewCapa: (capaId: string, decision: "approve" | "reject", reviewer?: string) =>
    client.post(`/capa/${capaId}/review`, { decision, reviewer }).then((r) => r.data),
}
