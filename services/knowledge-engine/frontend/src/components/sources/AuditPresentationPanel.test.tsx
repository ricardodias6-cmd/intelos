import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { AuditPresentationPanel } from './AuditPresentationPanel'
import { auditApi } from '@/lib/api/audit'
import type { AuditPresentation } from '@/lib/types/audit'

vi.mock('@/lib/api/audit', () => ({
  auditApi: {
    getPresentation: vi.fn(),
  },
}))

const presentation: AuditPresentation = {
  mode: 'audit',
  audit_id: 'AUDIT_FRONTEND_001',
  answer_id: 'ANSWER_FRONTEND_001',
  conversation_id: null,
  turn_id: null,
  response_mode: 'audit',
  question: 'Quem decide?',
  answer: 'A entidade competente decide.',
  status: 'answered',
  overall_confidence: 0.91,
  requires_human_review: false,
  freshness: {
    status: 'current',
    requires_revalidation: false,
    reason: null,
    change_ids: [],
    affected_evidence_ids: [],
    checked_at: '2026-07-31T00:00:00Z',
  },
  claims: [
    {
      claim_id: 'CLM_FRONTEND_001',
      text: 'A entidade competente decide.',
      kind: 'fact',
      evidence_ids: ['EV_FRONTEND_001'],
      support_status: 'direct',
      confidence: 0.91,
      requires_human_review: false,
      qualification: null,
    },
  ],
  citations: [],
  selected_evidence_ids: ['EV_FRONTEND_001'],
  rejected_evidence_ids: [],
  evidence_decisions: [],
  conflicts: [],
  trace: [],
  pipeline_version: 'phase-10',
  embedding_model: null,
  generated_at: '2026-07-31T00:00:00Z',
  counts: {
    claims: 1,
    citations: 0,
    selected_evidence: 1,
    rejected_evidence: 0,
    conflicts: 0,
    trace_events: 0,
  },
}

describe('AuditPresentationPanel', () => {
  it('loads a selected audit mode without exposing metadata', async () => {
    vi.mocked(auditApi.getPresentation).mockResolvedValue(presentation)

    render(<AuditPresentationPanel />)

    fireEvent.change(screen.getByLabelText('Answer ID'), {
      target: { value: 'ANSWER_FRONTEND_001' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Load audit' }))
    fireEvent.click(screen.getByRole('button', { name: 'audit' }))

    await waitFor(() => {
      expect(auditApi.getPresentation).toHaveBeenCalledWith(
        'ANSWER_FRONTEND_001',
        'audit',
      )
    })

    expect(await screen.findByTestId('audit-presentation')).toBeInTheDocument()
    expect(screen.getAllByText('A entidade competente decide.')).toHaveLength(2)
    expect(screen.queryByText('metadata')).not.toBeInTheDocument()
  })

  it('shows a safe error when the audit cannot be loaded', async () => {
    vi.mocked(auditApi.getPresentation).mockRejectedValue(new Error('secret'))

    render(<AuditPresentationPanel initialAnswerId="ANSWER_FRONTEND_404" />)

    expect(
      await screen.findByText('Unable to load this audit presentation.'),
    ).toBeInTheDocument()
    expect(screen.queryByText('secret')).not.toBeInTheDocument()
  })
})
