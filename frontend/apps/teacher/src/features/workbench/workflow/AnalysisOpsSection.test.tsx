import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import AnalysisOpsSection from './AnalysisOpsSection'
import type { AnalysisOpsSectionProps } from '../../../types/workflow'

const baseProps = (): AnalysisOpsSectionProps => ({
  analysisReports: [],
  analysisReportsSummary: {
    total_reports: 3,
    review_required_reports: 2,
    status_counts: { analysis_ready: 2, review: 1 },
    domains: [
      {
        domain: 'survey',
        total_reports: 2,
        review_required_reports: 1,
        queued_review_items: 1,
        status_counts: { analysis_ready: 2 },
      },
      {
        domain: 'class_report',
        total_reports: 1,
        review_required_reports: 1,
        queued_review_items: 1,
        status_counts: { review: 1 },
      },
    ],
  },
  analysisReviewSummary: {
    total_items: 2,
    unresolved_items: 2,
    status_counts: { queued: 2 },
    reason_counts: { low_confidence: 2 },
    domains: [
      { domain: 'survey', total_items: 1, unresolved_items: 1 },
      { domain: 'class_report', total_items: 1, unresolved_items: 1 },
    ],
  },
  analysisDomainFilter: '',
  setAnalysisDomainFilter: vi.fn(),
  rerunAnalysisReportsBulk: vi.fn(),
})

describe('AnalysisOpsSection', () => {
  it('renders counters, domain summaries, and bulk rerun action', () => {
    const props = baseProps()
    const setAnalysisDomainFilter = vi.fn()
    const rerunAnalysisReportsBulk = vi.fn()

    render(
      <AnalysisOpsSection
        {...props}
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
            review_required: true,
          },
          {
            report_id: 'report_2',
            domain: 'class_report',
            analysis_type: 'class_report',
            target_type: 'report',
            target_id: 'report_2',
            strategy_id: 'class.teacher.report',
            teacher_id: 'teacher_1',
            status: 'review',
            review_required: true,
          },
        ]}
        setAnalysisDomainFilter={setAnalysisDomainFilter}
        rerunAnalysisReportsBulk={rerunAnalysisReportsBulk}
      />,
    )

    expect(screen.getByText('总报告数')).toBeTruthy()
    expect(screen.getByText('3')).toBeTruthy()
    expect(screen.getByText('待复核报告')).toBeTruthy()
    expect(screen.getByText('待处理复核')).toBeTruthy()
    expect(screen.getByRole('button', { name: /survey · 2 份/ })).toBeTruthy()
    expect(screen.getByRole('button', { name: '批量重跑当前筛选（2）' })).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /survey · 2 份/ }))
    fireEvent.click(screen.getByRole('button', { name: '批量重跑当前筛选（2）' }))

    expect(setAnalysisDomainFilter).toHaveBeenCalledWith('survey')
    expect(rerunAnalysisReportsBulk).toHaveBeenCalledWith(['report_1', 'report_2'])
  })
})
