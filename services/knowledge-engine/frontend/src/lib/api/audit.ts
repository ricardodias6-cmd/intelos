import apiClient from './client'
import type {
  AuditPresentation,
  AuditPresentationMode,
} from '@/lib/types/audit'

export const auditApi = {
  getPresentation: async (
    answerId: string,
    mode: AuditPresentationMode = 'summary',
  ) => {
    const response = await apiClient.get<AuditPresentation>(
      `/evidence/answer/${encodeURIComponent(answerId)}/audit/presentation`,
      { params: { mode } },
    )
    return response.data
  },
}

export default auditApi
