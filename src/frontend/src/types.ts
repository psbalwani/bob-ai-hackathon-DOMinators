export type RiskBand = "High" | "Medium" | "Low"
export type Trend = "worsening" | "improving" | "stable" | "volatile"
export type Severity = "Major" | "Minor" | "Administrative"

export interface IndicatorBreakdown {
  severity_mix_weight: number
  deviation_frequency: number
  repeat_offense_rate: number
  recency_weight: number
  trend_slope: number
}

export interface RiskScore {
  site_id: string
  protocol_id: string
  risk_score: number
  risk_band: RiskBand
  computed_at: string
  indicator_breakdown: IndicatorBreakdown
  trend: Trend
  open_deviation_count: number
  total_visits: number
}

export interface SiteSummary {
  site_id: string
  site_name: string
  country: string
  risk_score: number | null
  risk_band: RiskBand | null
  trend: Trend | null
  open_deviation_count: number
}

export interface SiteDetail {
  site_id: string
  site_name: string
  country: string
  activation_date: string
  risk_score: RiskScore
}

export interface Deviation {
  deviation_id: string
  visit_record_id: string
  patient_id: string
  site_id: string
  protocol_id: string
  type: string
  severity: Severity
  severity_rationale: string
  protocol_clause_ref: string
  detected_at: string
  detector_version: string
}

export interface VisitRecord {
  visit_record_id: string
  patient_id: string
  site_id: string
  protocol_id: string
  visit_id: string
  scheduled_date: string
  actual_date: string
  dosage_administered_mg: number | null
  comedications: string[]
  procedures_completed: string[]
}

export type ReviewStatus = "pending_review" | "approved" | "rejected"

export interface CapaReport {
  capa_id: string
  scope: "deviation" | "site"
  site_id: string
  related_deviation_ids: string[]
  root_cause: string
  corrective_action: string
  preventive_action: string
  suggested_owner_role: string
  suggested_due_window_days: number
  generated_at: string
  evidence_citations: string[]
  review_status: ReviewStatus
  reviewer: string | null
  reviewed_at: string | null
}

export interface DashboardSummary {
  protocol_id: string
  total_sites: number
  total_patients: number
  total_visits: number
  open_deviations: number
  high_risk_sites: number
  site_ranking: { site_id: string; risk_score: number; risk_band: RiskBand }[]
}

export interface Protocol {
  protocol_id: string
  title: string
  ich_gcp_version: string
  visit_schedule: { visit_id: string; name: string; scheduled_day: number }[]
  dosing_rules: { drug: string; min_mg: number; max_mg: number; route: string }
}

export interface OwnedProtocol {
  protocol_id: string
  title: string
  drug: string
}

export type ReadinessBand = "Likely Approval Ready" | "Conditional — Remediation Required" | "High Risk of Rejection"

export interface DrugFactorBreakdown {
  avg_site_risk: number
  high_risk_site_share: number
  major_deviation_rate: number
  unresolved_capa_rate?: number
  trend_pressure: number
}

export interface DrugCapaSummary {
  total: number
  approved: number
  pending_review: number
  rejected: number
}

export interface DrugPerformance {
  protocol_id: string
  computed_at: string
  drug_risk_index: number
  readiness_band: ReadinessBand
  factor_breakdown: DrugFactorBreakdown
  rationale: string[]
  total_sites: number
  sites_by_band: Record<RiskBand, number>
  deviations_by_severity: Record<Severity, number>
  trend_breakdown: Record<Trend, number>
  capa_summary: DrugCapaSummary | null
  top_risk_sites: { site_id: string; risk_score: number; risk_band: RiskBand }[]
}
