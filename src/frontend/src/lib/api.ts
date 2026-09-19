import axios from "axios"
import type {
  CapaReport,
  DashboardSummary,
  Deviation,
  OwnedProtocol,
  Protocol,
  SiteDetail,
  SiteSummary,
  VisitRecord,
} from "../types"

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"

export const client = axios.create({ baseURL: BASE_URL })

// Set by AuthProvider on login/logout/restore -- a module-level variable
// (not React state) so the axios interceptor below can read it on every
// request without every call site having to thread a token through.
let authToken: string | null = null

export function setAuthToken(token: string | null) {
  authToken = token
}

client.interceptors.request.use((config) => {
  if (authToken) {
    config.headers.Authorization = `Bearer ${authToken}`
  }
  return config
})

export interface AuthUser {
  user_id: string
  username: string
  protocols: OwnedProtocol[]
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: AuthUser
}

export const api = {
  login: (username: string, password: string) =>
    client.post<LoginResponse>("/auth/login", { username, password }).then((r) => r.data),

  getMe: () => client.get<AuthUser>("/auth/me").then((r) => r.data),

  getProtocol: (protocolId: string) =>
    client.get<Protocol>("/protocol", { params: { protocol_id: protocolId } }).then((r) => r.data),

  getDashboardSummary: (protocolId: string) =>
    client
      .get<DashboardSummary>("/dashboard/summary", { params: { protocol_id: protocolId } })
      .then((r) => r.data),

  runPipeline: (protocolId: string) =>
    client.post("/pipeline/run", { protocol_id: protocolId }).then((r) => r.data),

  listSites: (protocolId: string) =>
    client
      .get<{ sites: SiteSummary[] }>("/sites", { params: { protocol_id: protocolId } })
      .then((r) => r.data.sites),

  getSite: (siteId: string, protocolId: string) =>
    client.get<SiteDetail>(`/sites/${siteId}`, { params: { protocol_id: protocolId } }).then((r) => r.data),

  getSiteDeviations: (siteId: string, protocolId: string) =>
    client
      .get<{ deviations: Deviation[] }>(`/sites/${siteId}/deviations`, { params: { protocol_id: protocolId } })
      .then((r) => r.data.deviations),

  getSiteVisits: (siteId: string, protocolId: string) =>
    client
      .get<{ visits: VisitRecord[] }>(`/sites/${siteId}/visits`, { params: { protocol_id: protocolId } })
      .then((r) => r.data.visits),

  getSiteCapaReports: (siteId: string, protocolId: string) =>
    client
      .get<{ capa_reports: CapaReport[] }>(`/sites/${siteId}/capa`, { params: { protocol_id: protocolId } })
      .then((r) => r.data.capa_reports),

  getDeviationDetail: (deviationId: string) =>
    client
      .get<{ deviation: Deviation; visit_record: VisitRecord | null }>(`/deviations/${deviationId}`)
      .then((r) => r.data),

  generateCapa: (protocolId: string, siteId: string, deviationIds?: string[]) =>
    client
      .post<CapaReport>("/capa/generate", {
        protocol_id: protocolId,
        scope: "site",
        site_id: siteId,
        deviation_ids: deviationIds,
      })
      .then((r) => r.data),

  reviewCapa: (capaId: string, decision: "approve" | "reject", reviewer?: string) =>
    client.post(`/capa/${capaId}/review`, { decision, reviewer }).then((r) => r.data),

  // The export endpoint now requires the same Authorization header as
  // everything else, so it can't be a plain <a href> anymore (that would
  // issue an unauthenticated GET) -- fetch the text via axios instead and
  // let the caller trigger a browser download from it.
  exportCapa: (capaId: string, format: "markdown" | "pdf" = "markdown") =>
    client.get<string>(`/capa/${capaId}/export`, { params: { format } }).then((r) => r.data),
}
