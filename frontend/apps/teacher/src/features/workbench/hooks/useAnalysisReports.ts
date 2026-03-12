import { useCallback, useEffect, useState } from 'react'
import type {
  AnalysisReportDetail,
  AnalysisReportSummary,
  AnalysisOpsSnapshot,
  AnalysisReviewQueueItem,
  AnalysisReviewQueueSummary,
  AnalysisReportsSummary,
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
  const [analysisReportsSummary, setAnalysisReportsSummary] = useState<AnalysisReportsSummary | null>(null)
  const [analysisReviewSummary, setAnalysisReviewSummary] = useState<AnalysisReviewQueueSummary | null>(null)
  const [analysisOpsSnapshot, setAnalysisOpsSnapshot] = useState<AnalysisOpsSnapshot | null>(null)
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
      setAnalysisReportsSummary(null)
      setAnalysisReviewSummary(null)
      setAnalysisOpsSnapshot(null)
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

      const opsUrl = new URL(`${apiBase}/teacher/analysis/ops`)
      opsUrl.searchParams.set('window_sec', '86400')

      const [reportsRes, reviewRes, opsRes] = await Promise.all([
        fetchJson<{ items: AnalysisReportSummary[]; summary?: AnalysisReportsSummary }>(reportsUrl),
        fetchJson<{ items: AnalysisReviewQueueItem[]; summary?: AnalysisReviewQueueSummary }>(reviewUrl),
        fetchJson<AnalysisOpsSnapshot>(opsUrl).catch(() => null),
      ])
      const nextReports = Array.isArray(reportsRes.items) ? reportsRes.items : []
      const nextReportsSummary = reportsRes.summary ?? null
      const nextReviewQueue = Array.isArray(reviewRes.items) ? reviewRes.items : []
      const nextReviewSummary = reviewRes.summary ?? null
      setAnalysisReports(nextReports)
      setAnalysisReportsSummary(nextReportsSummary)
      setAnalysisReviewQueue(nextReviewQueue)
      setAnalysisReviewSummary(nextReviewSummary)
      setAnalysisOpsSnapshot(opsRes ?? null)
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

  const rerunAnalysisReportsBulk = useCallback(
    async (reportIds: string[]) => {
      const normalized = reportIds.map((item) => String(item || '').trim()).filter(Boolean)
      if (!enabled || !teacherId || normalized.length === 0) return
      await fetchJson<{ accepted_count: number }>(`${apiBase}/teacher/analysis/reports/bulk-rerun`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          teacher_id: teacherId,
          report_ids: normalized,
          domain: analysisDomainFilter || undefined,
          reason: 'teacher_workbench_bulk_rerun',
        }),
      })
      await refreshAnalysisReports()
    },
    [analysisDomainFilter, apiBase, enabled, refreshAnalysisReports, teacherId],
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
    analysisReportsSummary,
    analysisReviewSummary,
    analysisOpsSnapshot,
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
    rerunAnalysisReportsBulk,
  }
}
