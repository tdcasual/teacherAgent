import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import VideoHomeworkAnalysisSection from './VideoHomeworkAnalysisSection'
import type { VideoHomeworkAnalysisSectionProps } from '../../../types/workflow'

const baseProps = (): VideoHomeworkAnalysisSectionProps => ({
  videoHomeworkFeatureEnabled: true,
  analysisReports: [],
  selectedAnalysisReport: null,
})

describe('VideoHomeworkAnalysisSection', () => {
  it('renders nothing when selected report is not video homework', () => {
    const { container } = render(
      <VideoHomeworkAnalysisSection
        {...baseProps()}
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
            review_required: false,
          },
          analysis_artifact: {},
          artifact_meta: {},
        }}
      />,
    )

    expect(container.textContent).toBe('')
  })

  it('renders video homework domain detail cards', () => {
    render(
      <VideoHomeworkAnalysisSection
        {...baseProps()}
        analysisReports={[
          {
            report_id: 'submission_1',
            domain: 'video_homework',
            analysis_type: 'video_homework',
            target_type: 'submission',
            target_id: 'submission_1',
            strategy_id: 'video_homework.teacher.report',
            teacher_id: 'teacher_1',
            status: 'analysis_ready',
            review_required: false,
          },
        ]}
        selectedAnalysisReport={{
          report: {
            report_id: 'submission_1',
            domain: 'video_homework',
            analysis_type: 'video_homework',
            target_type: 'submission',
            target_id: 'submission_1',
            strategy_id: 'video_homework.teacher.report',
            teacher_id: 'teacher_1',
            status: 'analysis_ready',
            review_required: false,
          },
          analysis_artifact: {
            executive_summary: '学生能完整展示实验步骤，但口头表达仍偏简略。',
            completion_overview: { status: 'completed', summary: '已完成主要实验流程展示。', duration_sec: 58 },
            expression_signals: [{ title: '步骤表达较完整', detail: '能够按顺序介绍器材与步骤。' }],
            evidence_clips: [{ label: '器材介绍', start_sec: 0, end_sec: 4, excerpt: '首先介绍实验器材与步骤。' }],
            teaching_recommendations: ['增加术语表达模板练习。'],
            confidence_and_gaps: { confidence: 0.86, gaps: ['teacher_rubric'] },
          },
          artifact_meta: { parse_confidence: 0.84 },
        }}
      />,
    )

    expect(screen.getByText('视频作业分析')).toBeTruthy()
    expect(screen.getByText(/已完成主要实验流程展示/)).toBeTruthy()
    expect(screen.getByText(/步骤表达较完整/)).toBeTruthy()
    expect(screen.getByText(/器材介绍/)).toBeTruthy()
    expect(screen.getByText(/增加术语表达模板练习/)).toBeTruthy()
  })
})
