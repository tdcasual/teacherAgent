import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import AnalysisReportSection from './AnalysisReportSection'
import type { AnalysisReportSectionProps } from '../../../types/workflow'

const baseProps = (): AnalysisReportSectionProps => ({
  analysisFeatureEnabled: true,
  analysisFeatureShadowMode: false,
  analysisReportsLoading: false,
  analysisReportsError: '',
  analysisReports: [],
  selectedAnalysisReportId: '',
  selectedAnalysisReport: null,
  analysisReviewQueue: [],
  analysisReportsSummary: null,
  analysisReviewSummary: null,
  analysisDomainFilter: '',
  analysisStatusFilter: '',
  analysisStrategyFilter: '',
  analysisTargetTypeFilter: '',
  setAnalysisDomainFilter: vi.fn(),
  setAnalysisStatusFilter: vi.fn(),
  setAnalysisStrategyFilter: vi.fn(),
  setAnalysisTargetTypeFilter: vi.fn(),
  refreshAnalysisReports: vi.fn(),
  selectAnalysisReport: vi.fn(),
  rerunAnalysisReport: vi.fn(),
  rerunAnalysisReportsBulk: vi.fn(),
})

describe('AnalysisReportSection', () => {
  it('renders empty and loading states', () => {
    const { rerender } = render(<AnalysisReportSection {...baseProps()} />)
    expect(screen.getByText('暂无分析报告')).toBeTruthy()

    rerender(
      <AnalysisReportSection
        {...baseProps()}
        analysisReportsLoading
      />,
    )
    expect(screen.getByText('分析报告加载中…')).toBeTruthy()
  })

  it('renders filters, explicit target summary, detail and actions', () => {
    const props = baseProps()
    const setAnalysisDomainFilter = vi.fn()
    const setAnalysisStatusFilter = vi.fn()
    const setAnalysisStrategyFilter = vi.fn()
    const setAnalysisTargetTypeFilter = vi.fn()
    const selectAnalysisReport = vi.fn()
    const rerunAnalysisReport = vi.fn()
    const rerunAnalysisReportsBulk = vi.fn()

    const view = render(
      <AnalysisReportSection
        {...props}
        analysisFeatureShadowMode
        analysisReports={[
          {
            report_id: 'report_1',
            domain: 'survey',
            analysis_type: 'survey',
            target_type: 'report',
            target_id: 'report_1',
            strategy_id: 'survey.teacher.report',
            teacher_id: 'teacher_1',
            status: 'analysis_ready',
            confidence: 0.81,
            summary: '班级整体在实验设计题上失分较多。',
            review_required: true,
            created_at: '2026-03-06T10:00:00',
            updated_at: '2026-03-06T10:05:00',
          },
        ]}
        analysisReviewQueue={[
          {
            item_id: 'review_1',
            domain: 'survey',
            report_id: 'report_1',
            teacher_id: 'teacher_1',
            status: 'queued',
            reason: 'low_confidence',
            confidence: 0.41,
            created_at: null,
            updated_at: null,
          },
        ]}
        analysisReportsSummary={{
          total_reports: 1,
          review_required_reports: 1,
          status_counts: { analysis_ready: 1 },
          domains: [{ domain: 'survey', total_reports: 1, review_required_reports: 1, queued_review_items: 1, status_counts: { analysis_ready: 1 } }],
        }}
        analysisReviewSummary={{
          total_items: 1,
          unresolved_items: 1,
          status_counts: { queued: 1 },
          reason_counts: { low_confidence: 1 },
          domains: [{ domain: 'survey', total_items: 1, unresolved_items: 1 }],
        }}
        selectedAnalysisReportId="report_1"
        selectedAnalysisReport={{
          report: {
            report_id: 'report_1',
            domain: 'survey',
            analysis_type: 'survey',
            target_type: 'report',
            target_id: 'report_1',
            strategy_id: 'survey.teacher.report',
            teacher_id: 'teacher_1',
            status: 'analysis_ready',
            confidence: 0.81,
            summary: '班级整体在实验设计题上失分较多。',
            review_required: true,
            created_at: '2026-03-06T10:00:00',
            updated_at: '2026-03-06T10:05:00',
          },
          analysis_artifact: {
            executive_summary: '班级整体在实验设计题上失分较多。',
            key_signals: [{ title: '实验设计理解偏弱', detail: 'Q1 中选择偏难的比例较高。' }],
            teaching_recommendations: ['先做实验设计拆解，再做当堂检测。'],
            confidence_and_gaps: { confidence: 0.81, gaps: ['student_level_raw_data'] },
          },
          artifact_meta: { parse_confidence: 0.78 },
        }}
        analysisDomainFilter=""
        analysisStatusFilter=""
        analysisStrategyFilter=""
        analysisTargetTypeFilter=""
        setAnalysisDomainFilter={setAnalysisDomainFilter}
        setAnalysisStatusFilter={setAnalysisStatusFilter}
        setAnalysisStrategyFilter={setAnalysisStrategyFilter}
        setAnalysisTargetTypeFilter={setAnalysisTargetTypeFilter}
        selectAnalysisReport={selectAnalysisReport}
        rerunAnalysisReport={rerunAnalysisReport}
        rerunAnalysisReportsBulk={rerunAnalysisReportsBulk}
      />,
    )

    expect(screen.getByText('Shadow')).toBeTruthy()
    expect(screen.getByText('当前对话对象')).toBeTruthy()
    expect(screen.getByText(/实验设计理解偏弱/)).toBeTruthy()
    expect(screen.getByText(/先做实验设计拆解/)).toBeTruthy()

    const scoped = within(view.container)
    fireEvent.change(scoped.getByLabelText('分析域'), { target: { value: 'survey' } })
    fireEvent.change(scoped.getByLabelText('状态'), { target: { value: 'analysis_ready' } })
    fireEvent.change(scoped.getByLabelText('策略'), { target: { value: 'survey.teacher.report' } })
    fireEvent.change(scoped.getByLabelText('对象类型'), { target: { value: 'report' } })
    fireEvent.click(scoped.getByRole('button', { name: '选择对象' }))
    fireEvent.click(scoped.getByRole('button', { name: '重新分析' }))
    fireEvent.click(scoped.getByRole('button', { name: '批量重跑当前筛选（1）' }))
    fireEvent.click(scoped.getByRole('button', { name: '清除当前对象' }))

    expect(setAnalysisDomainFilter).toHaveBeenCalledWith('survey')
    expect(setAnalysisStatusFilter).toHaveBeenCalledWith('analysis_ready')
    expect(setAnalysisStrategyFilter).toHaveBeenCalledWith('survey.teacher.report')
    expect(setAnalysisTargetTypeFilter).toHaveBeenCalledWith('report')
    expect(selectAnalysisReport).toHaveBeenCalledWith('report_1', 'survey')
    expect(rerunAnalysisReport).toHaveBeenCalledWith('report_1', 'survey')
    expect(rerunAnalysisReportsBulk).toHaveBeenCalledWith(['report_1'])
    expect(selectAnalysisReport).toHaveBeenCalledWith('', '')
  })
})
