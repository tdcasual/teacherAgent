import { useCallback, useEffect, useState } from 'react'
import type {
  SurveyReportDetail,
  SurveyReportSummary,
  SurveyReviewQueueItem,
} from '../../../types/workflow'

type UseSurveyReportsParams = {
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

export function useSurveyReports({ apiBase, teacherId, enabled }: UseSurveyReportsParams) {
  const [surveyReports, setSurveyReports] = useState<SurveyReportSummary[]>([])
  const [surveyReportsLoading, setSurveyReportsLoading] = useState(false)
  const [surveyReportsError, setSurveyReportsError] = useState('')
  const [selectedSurveyReportId, setSelectedSurveyReportId] = useState('')
  const [selectedSurveyReport, setSelectedSurveyReport] = useState<SurveyReportDetail | null>(null)
  const [surveyReviewQueue, setSurveyReviewQueue] = useState<SurveyReviewQueueItem[]>([])

  const selectSurveyReport = useCallback(
    async (reportId: string) => {
      const reportIdFinal = String(reportId || '').trim()
      if (!enabled || !teacherId || !reportIdFinal) {
        setSelectedSurveyReportId('')
        setSelectedSurveyReport(null)
        return
      }
      setSelectedSurveyReportId(reportIdFinal)
      const detail = await fetchJson<SurveyReportDetail>(
        `${apiBase}/teacher/surveys/reports/${encodeURIComponent(reportIdFinal)}?teacher_id=${encodeURIComponent(teacherId)}`,
      )
      setSelectedSurveyReport(detail)
    },
    [apiBase, enabled, teacherId],
  )

  const refreshSurveyReports = useCallback(async () => {
    if (!enabled || !teacherId) {
      setSurveyReports([])
      setSurveyReviewQueue([])
      setSelectedSurveyReportId('')
      setSelectedSurveyReport(null)
      setSurveyReportsError('')
      setSurveyReportsLoading(false)
      return
    }
    setSurveyReportsLoading(true)
    try {
      const [reportsRes, reviewRes] = await Promise.all([
        fetchJson<{ items: SurveyReportSummary[] }>(
          `${apiBase}/teacher/surveys/reports?teacher_id=${encodeURIComponent(teacherId)}`,
        ),
        fetchJson<{ items: SurveyReviewQueueItem[] }>(
          `${apiBase}/teacher/surveys/review-queue?teacher_id=${encodeURIComponent(teacherId)}`,
        ),
      ])
      const nextReports = Array.isArray(reportsRes.items) ? reportsRes.items : []
      setSurveyReports(nextReports)
      setSurveyReviewQueue(Array.isArray(reviewRes.items) ? reviewRes.items : [])
      setSurveyReportsError('')

      const nextSelectedId = selectedSurveyReportId || nextReports[0]?.report_id || ''
      if (nextSelectedId) {
        await selectSurveyReport(nextSelectedId)
      } else {
        setSelectedSurveyReportId('')
        setSelectedSurveyReport(null)
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : '问卷报告加载失败'
      setSurveyReportsError(message)
    } finally {
      setSurveyReportsLoading(false)
    }
  }, [apiBase, enabled, teacherId, selectedSurveyReportId, selectSurveyReport])

  const rerunSurveyReport = useCallback(
    async (reportId: string) => {
      const reportIdFinal = String(reportId || '').trim()
      if (!enabled || !teacherId || !reportIdFinal) return
      await fetchJson<{ ok: boolean }>(
        `${apiBase}/teacher/surveys/reports/${encodeURIComponent(reportIdFinal)}/rerun`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ teacher_id: teacherId, reason: 'teacher_workbench_rerun' }),
        },
      )
      await refreshSurveyReports()
      await selectSurveyReport(reportIdFinal)
    },
    [apiBase, enabled, teacherId, refreshSurveyReports, selectSurveyReport],
  )

  useEffect(() => {
    void refreshSurveyReports()
  }, [refreshSurveyReports])

  return {
    surveyReports,
    surveyReportsLoading,
    surveyReportsError,
    selectedSurveyReportId,
    selectedSurveyReport,
    surveyReviewQueue,
    refreshSurveyReports,
    selectSurveyReport,
    rerunSurveyReport,
  }
}
