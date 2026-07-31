'use client'

import { FormEvent, useCallback, useEffect, useState } from 'react'
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Clock3,
  History,
  RefreshCw,
  Search,
  ShieldCheck,
} from 'lucide-react'
import { auditApi } from '@/lib/api/audit'
import type {
  AuditHistoryItem,
  AuditPresentation,
  AuditPresentationMode,
  AuditFreshnessStatus,
  AuditRevalidationResult,
} from '@/lib/types/audit'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'

interface AuditPresentationPanelProps {
  initialAnswerId?: string
  conversationId?: string
}

const modes: AuditPresentationMode[] = ['summary', 'detailed', 'audit']

function confidenceLabel(value: number) {
  return Math.round(value * 100) + '%'
}

function freshnessVariant(status: AuditPresentation['freshness']['status']) {
  return status === 'current' ? 'default' : 'destructive'
}

function createIdempotencyKey() {
  const randomPart =
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID()
      : Math.random().toString(36).slice(2)
  return 'audit-ui-' + Date.now() + '-' + randomPart
}

export function AuditPresentationPanel({
  initialAnswerId,
  conversationId,
}: AuditPresentationPanelProps) {
  const [inputAnswerId, setInputAnswerId] = useState(initialAnswerId ?? '')
  const [answerId, setAnswerId] = useState(initialAnswerId ?? '')
  const [mode, setMode] = useState<AuditPresentationMode>('summary')
  const [presentation, setPresentation] = useState<AuditPresentation | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [hasError, setHasError] = useState(false)
  const [revalidationReason, setRevalidationReason] = useState('')
  const [isRevalidating, setIsRevalidating] = useState(false)
  const [revalidationError, setRevalidationError] = useState(false)
  const [revalidationResult, setRevalidationResult] =
    useState<AuditRevalidationResult | null>(null)

  useEffect(() => {
    if (!initialAnswerId) {
      return
    }
    setInputAnswerId(initialAnswerId)
    setAnswerId(initialAnswerId)
  }, [initialAnswerId])

  useEffect(() => {
    if (!answerId) {
      setPresentation(null)
      return
    }

    let active = true
    setIsLoading(true)
    setHasError(false)

    auditApi.getPresentation(answerId, mode)
      .then((result) => {
        if (active) {
          setPresentation(result)
        }
      })
      .catch(() => {
        if (active) {
          setPresentation(null)
          setHasError(true)
        }
      })
      .finally(() => {
        if (active) {
          setIsLoading(false)
        }
      })

    return () => {
      active = false
    }
  }, [answerId, mode])

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const normalized = inputAnswerId.trim()
    if (normalized) {
      setAnswerId(normalized)
    }
  }

  const handleRevalidate = async () => {
    if (!presentation || !revalidationReason.trim()) {
      return
    }

    setIsRevalidating(true)
    setRevalidationError(false)

    try {
      // Only evidence the audit itself decided on can be revalidated: the
      // backend rejects IDs outside the source report.
      const auditedEvidence = new Set([
        ...presentation.evidence_decisions.map(
          (decision) => decision.evidence_id,
        ),
        ...presentation.selected_evidence_ids,
      ])
      const evidenceIds = presentation.freshness.affected_evidence_ids.filter(
        (evidenceId) => auditedEvidence.has(evidenceId),
      )

      const result = await auditApi.revalidate(presentation.answer_id, {
        source_audit_id: presentation.audit_id,
        idempotency_key: createIdempotencyKey(),
        reason: revalidationReason.trim(),
        evidence_ids: evidenceIds,
        change_ids: presentation.freshness.change_ids,
      })

      setRevalidationResult(result)
      setRevalidationReason('')
      setInputAnswerId(result.result_answer_id)
      setAnswerId(result.result_answer_id)
    } catch {
      setRevalidationError(true)
    } finally {
      setIsRevalidating(false)
    }
  }

  return (
    <div className="h-full space-y-3 overflow-y-auto">
      <Card className="flex min-h-full flex-col overflow-hidden">
        <CardHeader className="flex-shrink-0 pb-3">
          <CardTitle className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.13em] text-muted-foreground">
            <ShieldCheck className="h-4 w-4 text-teal" />
            Audit presentation
          </CardTitle>
        </CardHeader>
        <CardContent className="flex-1 space-y-4 overflow-y-auto">
          <form className="flex gap-2" onSubmit={handleSubmit}>
            <label className="sr-only" htmlFor="audit-answer-id">
              Answer ID
            </label>
            <Input
              id="audit-answer-id"
              value={inputAnswerId}
              onChange={(event) => setInputAnswerId(event.target.value)}
              placeholder="Answer ID"
              autoComplete="off"
            />
            <Button
              type="submit"
              variant="outline"
              size="icon"
              aria-label="Load audit"
            >
              <Search className="h-4 w-4" />
            </Button>
          </form>

          <div
            className="flex flex-wrap gap-2"
            role="group"
            aria-label="Audit presentation mode"
          >
            {modes.map((candidate) => (
              <Button
                key={candidate}
                type="button"
                size="sm"
                variant={mode === candidate ? 'default' : 'outline'}
                onClick={() => setMode(candidate)}
              >
                {candidate}
              </Button>
            ))}
          </div>

          {!answerId && (
            <p className="text-sm text-muted-foreground">
              Envia uma pergunta no Chat e abre a auditoria diretamente na resposta AI.
            </p>
          )}

          {isLoading && (
            <div className="flex justify-center py-8" aria-label="Loading audit">
              <LoadingSpinner size="md" />
            </div>
          )}

          {hasError && !isLoading && (
            <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive-tint p-3 text-sm text-destructive">
              <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
              <span>Unable to load this audit presentation.</span>
            </div>
          )}

          {revalidationError && (
            <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive-tint p-3 text-sm text-destructive">
              <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
              <span>Unable to revalidate this audit.</span>
            </div>
          )}

          {revalidationResult && (
            <div className="rounded-md border border-teal/40 bg-teal-tint p-3 text-sm">
              <div className="font-medium">Revalidation completed</div>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                <Badge variant="outline">
                  {revalidationResult.result_answer_id}
                </Badge>
                <ArrowRight className="h-3 w-3" />
                <Badge variant="outline">
                  {revalidationResult.result_audit_id}
                </Badge>
              </div>
            </div>
          )}

          {presentation && !isLoading && (
            <AuditPresentationContent
              presentation={presentation}
              mode={mode}
              revalidationReason={revalidationReason}
              onRevalidationReasonChange={setRevalidationReason}
              onRevalidate={handleRevalidate}
              isRevalidating={isRevalidating}
            />
          )}
        </CardContent>
      </Card>

      <AuditHistoryPanel
        conversationId={conversationId}
        onOpenAnswer={(nextAnswerId) => {
          setInputAnswerId(nextAnswerId)
          setAnswerId(nextAnswerId)
        }}
      />
    </div>
  )
}

function AuditPresentationContent({
  presentation,
  mode,
  revalidationReason,
  onRevalidationReasonChange,
  onRevalidate,
  isRevalidating,
}: {
  presentation: AuditPresentation
  mode: AuditPresentationMode
  revalidationReason: string
  onRevalidationReasonChange: (value: string) => void
  onRevalidate: () => void
  isRevalidating: boolean
}) {
  const freshnessIsCurrent = presentation.freshness.status === 'current'

  return (
    <div className="space-y-4" data-testid="audit-presentation">
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div className="rounded-md border p-3">
          <div className="text-xs text-muted-foreground">Status</div>
          <Badge className="mt-1">{presentation.status}</Badge>
        </div>
        <div className="rounded-md border p-3">
          <div className="text-xs text-muted-foreground">Confidence</div>
          <div className="mt-1 font-medium">
            {confidenceLabel(presentation.overall_confidence)}
          </div>
        </div>
        <div className="rounded-md border p-3">
          <div className="text-xs text-muted-foreground">Freshness</div>
          <Badge
            className="mt-1"
            variant={freshnessVariant(presentation.freshness.status)}
          >
            {freshnessIsCurrent ? (
              <CheckCircle2 className="h-3 w-3" />
            ) : (
              <Clock3 className="h-3 w-3" />
            )}
            {presentation.freshness.status}
          </Badge>
        </div>
        <div className="rounded-md border p-3">
          <div className="text-xs text-muted-foreground">Human review</div>
          <div className="mt-1 font-medium">
            {presentation.requires_human_review ? 'Required' : 'Not required'}
          </div>
        </div>
      </div>

      {!freshnessIsCurrent && presentation.freshness.requires_revalidation && (
        <section className="rounded-md border border-destructive/40 p-3">
          <h3 className="text-sm font-semibold">Controlled revalidation</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Esta resposta não está confirmada como atual. A revalidação preserva o relatório original.
          </p>
          <div className="mt-3 space-y-2">
            <label className="text-xs font-medium" htmlFor="revalidation-reason">
              Reason
            </label>
            <Input
              id="revalidation-reason"
              value={revalidationReason}
              onChange={(event) => onRevalidationReasonChange(event.target.value)}
              placeholder="Explain why this answer should be revalidated"
              maxLength={2000}
            />
            <Button
              type="button"
              size="sm"
              onClick={onRevalidate}
              disabled={isRevalidating || !revalidationReason.trim()}
            >
              {isRevalidating ? (
                <LoadingSpinner size="sm" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
              Revalidate answer
            </Button>
          </div>
        </section>
      )}

      <div className="flex flex-wrap gap-2 text-xs">
        <Badge variant="outline">
          Selected evidence: {presentation.counts.selected_evidence}
        </Badge>
        <Badge variant="outline">
          Rejected evidence: {presentation.counts.rejected_evidence}
        </Badge>
      </div>

      <div className="rounded-md border p-3">
        <div className="text-xs text-muted-foreground">Answer</div>
        <p className="mt-1 whitespace-pre-wrap text-sm">{presentation.answer}</p>
      </div>

      <section>
        <h3 className="mb-2 text-sm font-semibold">
          Claims ({presentation.counts.claims})
        </h3>
        <div className="space-y-2">
          {presentation.claims.length === 0 && (
            <p className="text-sm text-muted-foreground">No claims recorded.</p>
          )}
          {presentation.claims.map((claim) => (
            <div key={claim.claim_id} className="rounded-md border p-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{claim.support_status}</Badge>
                <span className="text-xs text-muted-foreground">
                  {confidenceLabel(claim.confidence)}
                </span>
              </div>
              <p className="mt-2">{claim.text}</p>
              {claim.qualification && (
                <p className="mt-1 text-xs text-muted-foreground">
                  {claim.qualification}
                </p>
              )}
              {claim.evidence_ids.length > 0 && (
                <p className="mt-2 text-xs text-muted-foreground">
                  Evidence: {claim.evidence_ids.join(', ')}
                </p>
              )}
            </div>
          ))}
        </div>
      </section>

      {mode !== 'summary' && (
        <>
          <section>
            <h3 className="mb-2 text-sm font-semibold">
              Citations ({presentation.counts.citations})
            </h3>
            <div className="space-y-2">
              {presentation.citations.map((citation) => (
                <div
                  key={citation.evidence_id}
                  className="rounded-md border p-3 text-sm"
                >
                  <div className="font-medium">{citation.evidence_id}</div>
                  <div className="text-xs text-muted-foreground">
                    {citation.source_id} · {citation.document_version_id}
                    {citation.pdf_page
                      ? ' · PDF page ' + citation.pdf_page
                      : ''}
                  </div>
                  {mode === 'audit' && (
                    <p className="mt-2 whitespace-pre-wrap text-xs">
                      {citation.text}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </section>

          <section>
            <h3 className="mb-2 text-sm font-semibold">Evidence decisions</h3>
            <div className="space-y-2">
              {presentation.evidence_decisions.map((decision) => (
                <div
                  key={decision.evidence_id}
                  className="rounded-md border p-3 text-sm"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span>{decision.evidence_id}</span>
                    <Badge
                      variant={
                        decision.decision === 'selected'
                          ? 'default'
                          : 'outline'
                      }
                    >
                      {decision.decision}
                    </Badge>
                  </div>
                  {decision.reason && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      {decision.reason}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </section>

          <section>
            <h3 className="mb-2 text-sm font-semibold">
              Conflicts ({presentation.counts.conflicts})
            </h3>
            {presentation.conflicts.length === 0 ? (
              <p className="text-sm text-muted-foreground">No conflicts recorded.</p>
            ) : (
              <div className="space-y-2">
                {presentation.conflicts.map((conflict) => (
                  <div
                    key={conflict.conflict_id}
                    className="rounded-md border p-3 text-sm"
                  >
                    <Badge
                      variant={
                        conflict.severity === 'error'
                          ? 'destructive'
                          : 'outline'
                      }
                    >
                      {conflict.severity}
                    </Badge>
                    <p className="mt-2">{conflict.description}</p>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section>
            <h3 className="mb-2 text-sm font-semibold">
              Trace ({presentation.counts.trace_events})
            </h3>
            <div className="space-y-2">
              {presentation.trace.map((event, index) => (
                <div
                  key={event.stage + '-' + index}
                  className="flex items-center justify-between rounded-md border p-3 text-sm"
                >
                  <span>{event.stage}</span>
                  <span className="text-xs text-muted-foreground">
                    {event.status} · {event.duration_ms}ms
                  </span>
                </div>
              ))}
            </div>
          </section>
        </>
      )}

      <p className="text-xs text-muted-foreground">
        Audit {presentation.audit_id} · pipeline {presentation.pipeline_version}
      </p>
    </div>
  )
}

function AuditHistoryPanel({
  conversationId,
  onOpenAnswer,
}: {
  conversationId?: string
  onOpenAnswer: (answerId: string) => void
}) {
  const [items, setItems] = useState<AuditHistoryItem[]>([])
  const [turnId, setTurnId] = useState('')
  const [freshness, setFreshness] = useState<AuditFreshnessStatus | ''>('')
  const [nextOffset, setNextOffset] = useState<number | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [hasError, setHasError] = useState(false)

  const loadHistory = useCallback(async (next: number = 0) => {
    if (!conversationId) {
      setItems([])
      setNextOffset(null)
      return
    }

    setIsLoading(true)
    setHasError(false)
    try {
      const page = await auditApi.listReports({
        conversation_id: conversationId,
        turn_id: turnId.trim() || undefined,
        freshness_status: freshness || undefined,
        limit: 20,
        offset: next,
      })
      // Page 0 replaces the list; later pages append, so "Load more" keeps
      // what is already on screen instead of swapping it out.
      setItems((current) => (next === 0 ? page.items : [...current, ...page.items]))
      setNextOffset(page.next_offset)
    } catch {
      setHasError(true)
    } finally {
      setIsLoading(false)
    }
  }, [conversationId, freshness, turnId])

  useEffect(() => {
    void loadHistory(0)
  }, [conversationId, loadHistory])

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.13em] text-muted-foreground">
          <History className="h-4 w-4 text-teal" />
          Audit history
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {!conversationId && (
          <p className="text-sm text-muted-foreground">
            Select a chat session to inspect its audit history.
          </p>
        )}

        {conversationId && (
          <>
            <div className="grid gap-2 sm:grid-cols-[1fr_auto_auto]">
              <Input
                aria-label="Turn ID filter"
                value={turnId}
                onChange={(event) => setTurnId(event.target.value)}
                placeholder="Filter by turn ID"
              />
              <select
                aria-label="Freshness filter"
                className="h-9 rounded-md border bg-popover px-3 text-sm"
                value={freshness}
                onChange={(event) =>
                  setFreshness(event.target.value as AuditFreshnessStatus | '')
                }
              >
                <option value="">All freshness</option>
                <option value="current">Current</option>
                <option value="possibly_outdated">Possibly outdated</option>
                <option value="outdated">Outdated</option>
                <option value="unknown">Unknown</option>
              </select>
              <Button
                type="button"
                variant="outline"
                size="icon"
                aria-label="Refresh audit history"
                onClick={() => void loadHistory(0)}
              >
                <RefreshCw className="h-4 w-4" />
              </Button>
            </div>

            {isLoading && (
              <div className="flex justify-center py-4" aria-label="Loading audit history">
                <LoadingSpinner size="sm" />
              </div>
            )}

            {hasError && !isLoading && (
              <p className="text-sm text-destructive">
                Unable to load audit history.
              </p>
            )}

            {!isLoading && !hasError && items.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No audit reports found for this session.
              </p>
            )}

            <div className="space-y-2">
              {items.map((item) => (
                <div
                  key={item.audit_id}
                  className="rounded-md border p-3 text-sm"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Badge variant={item.freshness.status === 'current' ? 'default' : 'destructive'}>
                        {item.freshness.status}
                      </Badge>
                      <span className="text-xs text-muted-foreground">
                        {item.answer_id}
                      </span>
                    </div>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => onOpenAnswer(item.answer_id)}
                    >
                      Open audit
                    </Button>
                  </div>
                  <p className="mt-2 line-clamp-2">{item.question}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Turn: {item.turn_id ?? '—'} · Confidence: {confidenceLabel(item.overall_confidence)}
                  </p>
                </div>
              ))}
            </div>

            {nextOffset !== null && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => void loadHistory(nextOffset)}
              >
                Load more
              </Button>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
