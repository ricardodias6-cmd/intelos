import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ChatPanel } from './ChatPanel'
import { AuditPresentationPanel } from './AuditPresentationPanel'
import { auditApi } from '@/lib/api/audit'
import type { AuditPresentation } from '@/lib/types/audit'
import type { SourceChatMessage } from '@/lib/types/api'

vi.mock('@/lib/api/audit', () => ({
  auditApi: {
    getPresentation: vi.fn(),
    revalidate: vi.fn(),
    listReports: vi.fn(),
  },
}))

vi.mock('@/lib/hooks/use-notes', () => ({
  useCreateNote: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
}))

vi.mock('@/lib/hooks/use-modal-manager', () => ({
  useModalManager: () => ({
    openModal: vi.fn(),
  }),
}))

const stalePresentation: AuditPresentation = {
  mode: 'summary',
  audit_id: 'AUDIT_FLOW_001',
  answer_id: 'ANSWER_FLOW_001',
  conversation_id: 'chat_session:SESSION_FLOW_001',
  turn_id: 'TURN_FLOW_001',
  response_mode: 'detailed',
  question: 'Quem decide?',
  answer: 'A entidade competente decide.',
  status: 'answered',
  overall_confidence: 0.91,
  requires_human_review: false,
  freshness: {
    status: 'outdated',
    requires_revalidation: true,
    reason: 'Document changed.',
    change_ids: ['CHANGE_FLOW_001'],
    affected_evidence_ids: ['EV_FLOW_001'],
    checked_at: '2026-07-31T00:00:00Z',
  },
  claims: [
    {
      claim_id: 'CLM_FLOW_001',
      text: 'A entidade competente decide.',
      kind: 'fact',
      evidence_ids: ['EV_FLOW_001'],
      support_status: 'direct',
      confidence: 0.91,
      requires_human_review: false,
      qualification: null,
    },
  ],
  citations: [],
  selected_evidence_ids: ['EV_FLOW_001'],
  rejected_evidence_ids: [],
  evidence_decisions: [
    {
      evidence_id: 'EV_FLOW_001',
      decision: 'selected',
      reason: 'Claim support',
      retrieval_score: 0.91,
      rank: 1,
    },
  ],
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

const refreshedPresentation: AuditPresentation = {
  ...stalePresentation,
  audit_id: 'AUDIT_FLOW_002',
  answer_id: 'ANSWER_FLOW_002',
  freshness: {
    ...stalePresentation.freshness,
    status: 'current',
    requires_revalidation: false,
    reason: null,
    change_ids: [],
    affected_evidence_ids: [],
  },
}

const message: SourceChatMessage = {
  id: 'ANSWER_FLOW_001',
  type: 'ai',
  content: 'A entidade competente decide.',
  timestamp: '2026-07-31T00:00:00Z',
  answer_id: 'ANSWER_FLOW_001',
  audit_report_id: 'AUDIT_FLOW_001',
  conversation_id: 'chat_session:SESSION_FLOW_001',
  turn_id: 'TURN_FLOW_001',
  audit_status: 'answered',
}

function ChatAuditFlowHarness() {
  const [answerId, setAnswerId] = useState<string | null>(null)

  return (
    <>
      <ChatPanel
        messages={[message]}
        isStreaming={false}
        contextIndicators={null}
        onSendMessage={vi.fn()}
        notebookId="NOTEBOOK_FLOW_001"
        onOpenAudit={setAnswerId}
      />
      {answerId && (
        <AuditPresentationPanel
          initialAnswerId={answerId}
          conversationId="chat_session:SESSION_FLOW_001"
        />
      )}
    </>
  )
}

describe('Chat to audit flow', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(auditApi.getPresentation).mockImplementation(async (answerId) => (
      answerId === 'ANSWER_FLOW_002'
        ? refreshedPresentation
        : stalePresentation
    ))
    vi.mocked(auditApi.listReports).mockResolvedValue({
      items: [],
      limit: 20,
      offset: 0,
      has_more: false,
      next_offset: null,
      scan_truncated: false,
    })
  })

  it('opens the audit from the AI message and revalidates to new identifiers', async () => {
    vi.mocked(auditApi.revalidate).mockResolvedValue({
      status: 'completed',
      replayed: false,
      idempotency_key: 'audit-ui-flow-key-0001',
      source_audit_id: 'AUDIT_FLOW_001',
      source_answer_id: 'ANSWER_FLOW_001',
      result_audit_id: 'AUDIT_FLOW_002',
      result_answer_id: 'ANSWER_FLOW_002',
      reason: 'Document changed.',
      evidence_ids: ['EV_FLOW_001'],
      change_ids: ['CHANGE_FLOW_001'],
      completed_at: '2026-07-31T00:00:00Z',
    })

    render(<ChatAuditFlowHarness />)

    fireEvent.click(screen.getByRole('button', { name: 'Open audit' }))
    expect(await screen.findByTestId('audit-presentation')).toBeInTheDocument()
    expect(await screen.findByText('outdated')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Reason'), {
      target: { value: 'Document changed.' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Revalidate answer' }))

    await waitFor(() => {
      expect(auditApi.revalidate).toHaveBeenCalledWith(
        'ANSWER_FLOW_001',
        expect.objectContaining({
          source_audit_id: 'AUDIT_FLOW_001',
          reason: 'Document changed.',
        }),
      )
    })
    expect(await screen.findByText('ANSWER_FLOW_002')).toBeInTheDocument()
    expect(await screen.findByText('AUDIT_FLOW_002')).toBeInTheDocument()
  })

  it('loads visual history filtered by the active conversation', async () => {
    vi.mocked(auditApi.listReports).mockResolvedValue({
      items: [
        {
          audit_id: 'AUDIT_HISTORY_001',
          answer_id: 'ANSWER_HISTORY_001',
          conversation_id: 'chat_session:SESSION_FLOW_001',
          turn_id: 'TURN_HISTORY_001',
          response_mode: 'detailed',
          question: 'Qual é o prazo?',
          answer: 'O prazo é de dez dias.',
          status: 'answered',
          overall_confidence: 0.88,
          requires_human_review: false,
          freshness: {
            status: 'current',
            requires_revalidation: false,
            reason: null,
            change_ids: [],
            affected_evidence_ids: [],
            checked_at: '2026-07-31T00:00:00Z',
          },
          generated_at: '2026-07-31T00:00:00Z',
        },
      ],
      limit: 20,
      offset: 0,
      has_more: false,
      next_offset: null,
      scan_truncated: false,
    })

    render(
      <AuditPresentationPanel conversationId="chat_session:SESSION_FLOW_001" />,
    )

    expect(await screen.findByText('ANSWER_HISTORY_001')).toBeInTheDocument()
    expect(auditApi.listReports).toHaveBeenCalledWith(
      expect.objectContaining({
        conversation_id: 'chat_session:SESSION_FLOW_001',
        limit: 20,
        offset: 0,
      }),
    )
  })
})
