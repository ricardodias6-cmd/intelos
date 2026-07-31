export type AuditPresentationMode = 'summary' | 'detailed' | 'audit'

export type AuditRevalidationStatus = 'processing' | 'completed' | 'failed'

export type AuditFreshnessStatus =
  | 'current'
  | 'possibly_outdated'
  | 'outdated'
  | 'unknown'

export interface AuditFreshness {
  status: AuditFreshnessStatus
  requires_revalidation: boolean
  reason: string | null
  change_ids: string[]
  affected_evidence_ids: string[]
  checked_at: string
}

export interface AuditClaim {
  claim_id: string
  text: string
  kind: string
  evidence_ids: string[]
  support_status: string
  confidence: number
  requires_human_review: boolean
  qualification: string | null
}

export interface AuditCitation {
  evidence_id: string
  source_id: string
  document_version_id: string
  document_version_hash: string
  pdf_page: number | null
  printed_page: string | null
  section_path: string[]
  text: string
}

export interface AuditEvidenceDecision {
  evidence_id: string
  decision: 'selected' | 'rejected' | 'not_selected'
  reason: string | null
  retrieval_score: number | null
  rank: number | null
}

export interface AuditConflict {
  conflict_id: string
  claim_id: string | null
  evidence_ids: string[]
  description: string
  severity: 'warning' | 'error'
}

export interface AuditTraceEvent {
  stage: string
  status: string
  duration_ms: number
  details: Record<string, unknown>
}

export interface AuditPresentationCounts {
  claims: number
  citations: number
  selected_evidence: number
  rejected_evidence: number
  conflicts: number
  trace_events: number
}

export interface AuditRevalidationRequest {
  source_audit_id: string
  idempotency_key: string
  reason: string
  evidence_ids: string[]
  change_ids: string[]
}

export interface AuditRevalidationResult {
  status: AuditRevalidationStatus
  replayed: boolean
  idempotency_key: string
  source_audit_id: string
  source_answer_id: string
  result_audit_id: string
  result_answer_id: string
  reason: string
  evidence_ids: string[]
  change_ids: string[]
  completed_at: string
}

/**
 * One item of `/evidence/audit-reports`.
 *
 * The endpoint returns the full persisted AuditReport, not a summary: the
 * fields below are the ones this UI reads, and the optional ones document the
 * rest of the payload so callers do not assume it was stripped server-side.
 */
export interface AuditHistoryItem {
  audit_id: string
  answer_id: string
  conversation_id: string | null
  turn_id: string | null
  response_mode: string
  question: string
  answer: string
  status: AuditPresentation['status']
  overall_confidence: number
  requires_human_review: boolean
  freshness: AuditFreshness
  generated_at: string
  claims?: AuditClaim[]
  citations?: AuditCitation[]
  selected_evidence_ids?: string[]
  rejected_evidence_ids?: string[]
  evidence_decisions?: AuditEvidenceDecision[]
  conflicts?: AuditConflict[]
  trace?: AuditTraceEvent[]
  pipeline_version?: string
  embedding_model?: string | null
  metadata?: Record<string, unknown>
}

export interface AuditReportPage {
  items: AuditHistoryItem[]
  limit: number
  offset: number
  has_more: boolean
  next_offset: number | null
  scan_truncated: boolean
}

export interface AuditHistoryFilters {
  answer_id?: string
  conversation_id?: string
  turn_id?: string
  freshness_status?: AuditFreshnessStatus
  generated_from?: string
  generated_to?: string
  limit?: number
  offset?: number
}

export interface AuditPresentation {
  mode: AuditPresentationMode
  audit_id: string
  answer_id: string
  conversation_id: string | null
  turn_id: string | null
  response_mode: string
  question: string
  answer: string
  status: 'answered' | 'insufficient_evidence' | 'conflict' | 'clarification_required'
  overall_confidence: number
  requires_human_review: boolean
  freshness: AuditFreshness
  claims: AuditClaim[]
  citations: AuditCitation[]
  selected_evidence_ids: string[]
  rejected_evidence_ids: string[]
  evidence_decisions: AuditEvidenceDecision[]
  conflicts: AuditConflict[]
  trace: AuditTraceEvent[]
  pipeline_version: string
  embedding_model: string | null
  generated_at: string
  counts: AuditPresentationCounts
}
