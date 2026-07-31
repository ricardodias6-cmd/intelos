import apiClient from './client'
import type {
  AuditHistoryFilters,
  AuditPresentation,
  AuditPresentationMode,
  AuditReportPage,
  AuditRevalidationRequest,
  AuditRevalidationResult,
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

  revalidate: async (
    answerId: string,
    request: AuditRevalidationRequest,
  ) => {
    const response = await apiClient.post<AuditRevalidationResult>(
      `/evidence/answer/${encodeURIComponent(answerId)}/audit/revalidate`,
      request,
    )
    return response.data
  },

  listReports: async (filters: AuditHistoryFilters = {}) => {
    const response = await apiClient.get<AuditReportPage>(
      '/evidence/audit-reports',
      { params: filters },
    )
    return response.data
  },
}

export default auditApi
