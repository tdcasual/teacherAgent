import { useCallback, useEffect, useState } from 'react'
import type {
  AnalysisReportDetail,
  AnalysisReportSummary,
  AnalysisReviewQueueItem,
} from '../../../types/workflow'

type UseAnalysisReportsParams = {
  apiBase: string
  teacherId: string
  enabled: boolean
}

const fetchJson = async <T,>(input: RequestInfo | URL, init?: RequestInit): Promise<T> => {
  const response = await fetch(input, init)
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `请求失败（${response.status}）`)
  }
  return (await response.json()) as T
}

const buildReportUrl = (apiBase: string, reportId: string, teacherId: string, domain: string) => {
  const url = new URL(`${apiBase}/teacher/analysis/reports/${encodeURIComponent(reportId)}`)
  url.searchParams.set('teacher_id', teacherId)
  if (domain) url.searchParams.set('domain', domain)
  return url
}

const buildReportDomain = (report: Pick<AnalysisReportSummary, 'domain' | 'analysis_type'>) => {
  return String(report.domain || report.analysis_type || '').trim()
}

export function useAnalysisReports({ apiBase, teacherId, enabled }: UseAnalysisReportsParams) {
  const [analysisReports, setAnalysisReports] = useState<AnalysisReportSummary[]>([])
  const [analysisReportsLoading, setAnalysisReportsLoading] = useState(false)
  const [analysisReportsError, setAnalysisReportsError] = useState('')
  const [selectedAnalysisReportId, setSelectedAnalysisReportId] = useState('')
  const [selectedAnalysisReport, setSelectedAnalysisReport] = useState<AnalysisReportDetail | null>(null)
  const [analysisReviewQueue, setAnalysisReviewQueue] = useState<AnalysisReviewQueueItem[]>([])
  const [analysisDomainFilter, setAnalysisDomainFilter] = useState('')
  const [analysisStatusFilter, setAnalysisStatusFilter] = useState('')
  const [analysisStrategyFilter, setAnalysisStrategyFilter] = useState('')
  const [analysisTargetTypeFilter, setAnalysisTargetTypeFilter] = useState('')

  const selectAnalysisReport = useCallback(
    async (reportId: string, domain = '') => {
      const reportIdFinal = String(reportId || '').trim()
      const domainFinal = String(domain || '').trim()
      if (!enabled || !teacherId || !reportIdFinal) {
        setSelectedAnalysisReportId('')
        setSelectedAnalysisReport(null)
        return
      }
      setSelectedAnalysisReportId(reportIdFinal)
      const detail = await fetchJson<AnalysisReportDetail>(
        buildReportUrl(apiBase, reportIdFinal, teacherId, domainFinal || analysisDomainFilter),
      )
      setSelectedAnalysisReport(detail)
    },
    [analysisDomainFilter, apiBase, enabled, teacherId],
  )

  const refreshAnalysisReports = useCallback(async () => {
    if (!enabled || !teacherId) {
      setAnalysisReports([])
      setAnalysisReviewQueue([])
      setSelectedAnalysisReportId('')
      setSelectedAnalysisReport(null)
      setAnalysisReportsError('')
      setAnalysisReportsLoading(false)
      return
    }
    setAnalysisReportsLoading(true)
    try {
      const reportsUrl = new URL(`${apiBase}/teacher/analysis/reports`)
      reportsUrl.searchParams.set('teacher_id', teacherId)
      if (analysisDomainFilter) reportsUrl.searchParams.set('domain', analysisDomainFilter)
      if (analysisStatusFilter) reportsUrl.searchParams.set('status', analysisStatusFilter)
      if (analysisStrategyFilter) reportsUrl.searchParams.set('strategy_id', analysisStrategyFilter)
      if (analysisTargetTypeFilter) reportsUrl.searchParams.set('target_type', analysisTargetTypeFilter)

      const reviewUrl = new URL(`${apiBase}/teacher/analysis/review-queue`)
      reviewUrl.searchParams.set('teacher_id', teacherId)
      if (analysisDomainFilter) reviewUrl.searchParams.set('domain', analysisDomainFilter)

      const [reportsRes, reviewRes] = await Promise.all([
        fetchJson<{ items: AnalysisReportSummary[] }>(reportsUrl),
        fetchJson<{ items: AnalysisReviewQueueItem[] }>(reviewUrl),
      ])
      const nextReports = Array.isArray(reportsRes.items) ? reportsRes.items : []
      const nextReviewQueue = Array.isArray(reviewRes.items) ? reviewRes.items : []
      setAnalysisReports(nextReports)
      setAnalysisReviewQueue(nextReviewQueue)
      setAnalysisReportsError('')

      if (selectedAnalysisReportId) {
        const selectedSummary = nextReports.find((item) => item.report_id === selectedAnalysisReportId)
        if (selectedSummary) {
          await selectAnalysisReport(selectedAnalysisReportId, buildReportDomain(selectedSummary))
        } else {
          setSelectedAnalysisReportId('')
          setSelectedAnalysisReport(null)
        }
      } else {
        setSelectedAnalysisReport(null)
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : '分析报告加载失败'
      setAnalysisReportsError(message)
    } finally {
      setAnalysisReportsLoading(false)
    }
  }, [
    analysisDomainFilter,
    analysisStatusFilter,
    analysisStrategyFilter,
    analysisTargetTypeFilter,
    apiBase,
    enabled,
    selectAnalysisReport,
    selectedAnalysisReportId,
    teacherId,
  ])

  const rerunAnalysisReport = useCallback(
    async (reportId: string, domain = '') => {
      const reportIdFinal = String(reportId || '').trim()
      const domainFinal = String(domain || '').trim()
      if (!enabled || !teacherId || !reportIdFinal) return
      await fetchJson<{ ok: boolean }>(
        `${apiBase}/teacher/analysis/reports/${encodeURIComponent(reportIdFinal)}/rerun`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            teacher_id: teacherId,
            domain: domainFinal || undefined,
            reason: 'teacher_workbench_rerun',
          }),
        },
      )
      await refreshAnalysisReports()
      await selectAnalysisReport(reportIdFinal, domainFinal)
    },
    [apiBase, enabled, refreshAnalysisReports, selectAnalysisReport, teacherId],
  )

  useEffect(() => {
    void refreshAnalysisReports()
  }, [refreshAnalysisReports])

  return {
    analysisReports,
    analysisReportsLoading,
    analysisReportsError,
    selectedAnalysisReportId,
    selectedAnalysisReport,
    analysisReviewQueue,
    analysisDomainFilter,
    analysisStatusFilter,
    analysisStrategyFilter,
    analysisTargetTypeFilter,
    setAnalysisDomainFilter,
    setAnalysisStatusFilter,
    setAnalysisStrategyFilter,
    setAnalysisTargetTypeFilter,
    refreshAnalysisReports,
    selectAnalysisReport,
    rerunAnalysisReport,
  }
}
