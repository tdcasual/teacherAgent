import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import SurveyAnalysisSection from './SurveyAnalysisSection'
import type { SurveyAnalysisSectionProps } from '../../../types/workflow'

const baseProps = (): SurveyAnalysisSectionProps => ({
  surveyFeatureEnabled: true,
  surveyFeatureShadowMode: false,
  surveyReportsLoading: false,
  surveyReportsError: '',
  surveyReports: [],
  selectedSurveyReportId: '',
  selectedSurveyReport: null,
  surveyReviewQueue: [],
  refreshSurveyReports: vi.fn(),
  selectSurveyReport: vi.fn(),
  rerunSurveyReport: vi.fn(),
})

describe('SurveyAnalysisSection', () => {
  it('renders empty and loading states', () => {
    const { rerender } = render(<SurveyAnalysisSection {...baseProps()} />)
    expect(screen.getByText('暂无问卷分析报告')).toBeTruthy()

    rerender(
      <SurveyAnalysisSection
        {...baseProps()}
        surveyReportsLoading
      />,
    )
    expect(screen.getByText('问卷报告加载中…')).toBeTruthy()
  })

  it('renders report list, review badge, detail and rerun action', () => {
    const props = baseProps()
    const selectSurveyReport = vi.fn()
    const rerunSurveyReport = vi.fn()
    render(
      <SurveyAnalysisSection
        {...props}
        surveyFeatureShadowMode
        surveyReports={[
          {
            report_id: 'report_1',
            teacher_id: 'teacher_1',
            class_name: '高二2403班',
            status: 'analysis_ready',
            confidence: 0.81,
            summary: '班级整体在实验设计题上失分较多。',
            created_at: '2026-03-06T10:00:00',
            updated_at: '2026-03-06T10:05:00',
          },
        ]}
        surveyReviewQueue={[
          { report_id: 'report_1', teacher_id: 'teacher_1', reason: 'low_confidence', confidence: 0.41, created_at: null },
        ]}
        selectedSurveyReportId="report_1"
        selectedSurveyReport={{
          report: {
            report_id: 'report_1',
            teacher_id: 'teacher_1',
            class_name: '高二2403班',
            status: 'analysis_ready',
            confidence: 0.81,
            summary: '班级整体在实验设计题上失分较多。',
            created_at: '2026-03-06T10:00:00',
            updated_at: '2026-03-06T10:05:00',
          },
          analysis_artifact: {
            executive_summary: '班级整体在实验设计题上失分较多。',
            key_signals: [{ title: '实验设计理解偏弱', detail: 'Q1 中选择偏难的比例较高。' }],
            teaching_recommendations: ['先做实验设计拆解，再做当堂检测。'],
            confidence_and_gaps: { confidence: 0.81, gaps: ['student_level_raw_data'] },
          },
          bundle_meta: { parse_confidence: 0.78 },
          review_required: true,
        }}
        selectSurveyReport={selectSurveyReport}
        rerunSurveyReport={rerunSurveyReport}
      />,
    )

    expect(screen.getByText('Shadow')).toBeTruthy()
    expect(screen.getByText('待复核')).toBeTruthy()
    expect(screen.getByText(/实验设计理解偏弱/)).toBeTruthy()
    expect(screen.getByText(/先做实验设计拆解/)).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: '查看详情' }))
    fireEvent.click(screen.getByRole('button', { name: '重新分析' }))

    expect(selectSurveyReport).toHaveBeenCalledWith('report_1')
    expect(rerunSurveyReport).toHaveBeenCalledWith('report_1')
  })
})
