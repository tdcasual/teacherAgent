import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import WorkflowTab, { type WorkflowTabProps } from './WorkflowTab'

vi.mock('../workflow/WorkflowSummaryCard', () => ({
  default: () => <div>workflow-summary-card</div>,
}))

vi.mock('../workflow/UploadSection', () => ({
  default: () => <div>workflow-upload-section</div>,
}))

vi.mock('../workflow/AssignmentProgressSection', () => ({
  default: () => <div>workflow-progress-section</div>,
}))

vi.mock('../workflow/ExamDraftSection', () => ({
  default: () => <div>workflow-exam-draft-section</div>,
}))

vi.mock('../workflow/AssignmentDraftSection', () => ({
  default: () => <div>workflow-assignment-draft-section</div>,
}))

vi.mock('../workflow/AnalysisReportSection', () => ({
  default: () => <div>workflow-analysis-section</div>,
}))

vi.mock('../workflow/VideoHomeworkAnalysisSection', () => ({
  default: () => <div>workflow-video-analysis-section</div>,
}))

vi.mock('../workflow/WorkflowTimeline', () => ({
  default: () => <div>workflow-timeline-section</div>,
}))

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const buildProps = (): WorkflowTabProps => ({
  uploadMode: 'assignment',
  draftLoading: false,
  draftError: '',
  uploadDraft: { job_id: 'job1', assignment_id: 'HW-1', date: '2026-03-14', scope: 'public', delivery_mode: 'pdf', requirements: { subject: '物理', topic: '受力分析', grade_level: '高二', class_level: '中等', core_concepts: [], typical_problem: '', misconceptions: [], duration_minutes: 40, preferences: [], extra_constraints: '' }, requirements_missing: [], questions: [], draft_saved: true } as never,
  examDraftLoading: false,
  examDraftError: '',
  examDraft: null,
  activeWorkflowIndicator: {
    label: '待审核',
    tone: 'active',
    steps: [
      { key: 'upload', label: '上传文件', state: 'done' },
      { key: 'parse', label: '解析', state: 'done' },
      { key: 'review', label: '审核草稿', state: 'active' },
      { key: 'confirm', label: '创建作业', state: 'todo' },
    ],
  },
  setUploadMode: () => undefined,
  formatUploadJobSummary: () => 'upload-summary',
  formatExamJobSummary: () => 'exam-summary',
  formatProgressSummary: () => 'progress-summary',
  uploadJobInfo: null,
  uploadAssignmentId: 'HW-1',
  examJobInfo: null,
  examId: '',
  scrollToWorkflowSection: () => undefined,
  refreshWorkflowWorkbench: () => undefined,
  progressData: null,
  progressAssignmentId: 'HW-1',
  progressLoading: false,
  fetchAssignmentProgress: async () => undefined,
  analysisFeatureEnabled: true,
  analysisFeatureShadowMode: false,
  analysisReportsLoading: false,
  analysisReportsError: '',
  analysisReports: [],
  selectedAnalysisReportId: '',
  selectedAnalysisReport: null,
  analysisReviewQueue: [],
  analysisReportsSummary: '',
  analysisReviewSummary: '',
  analysisOpsSnapshot: null,
  analysisDomainFilter: 'all',
  analysisStatusFilter: 'all',
  analysisStrategyFilter: 'all',
  analysisTargetTypeFilter: 'all',
  setAnalysisDomainFilter: () => undefined,
  setAnalysisStatusFilter: () => undefined,
  setAnalysisStrategyFilter: () => undefined,
  setAnalysisTargetTypeFilter: () => undefined,
  refreshAnalysisReports: async () => undefined,
  selectAnalysisReport: async () => undefined,
  rerunAnalysisReport: async () => undefined,
  rerunAnalysisReportsBulk: async () => undefined,
  videoHomeworkFeatureEnabled: true,
  uploading: false,
  examUploading: false,
  progressPanelCollapsed: false,
  setProgressPanelCollapsed: () => undefined,
  setProgressAssignmentId: () => undefined,
  progressOnlyIncomplete: false,
  setProgressOnlyIncomplete: () => undefined,
  progressError: '',
  draftSaving: false,
  uploadConfirming: false,
  examDraftSaving: false,
  examConfirming: false,
  executionTimeline: [],
  uploadCardCollapsed: false,
  setUploadCardCollapsed: () => undefined,
  handleUploadAssignment: async () => undefined,
  handleUploadExam: async () => undefined,
  setUploadAssignmentId: () => undefined,
  uploadDate: '2026-03-14',
  setUploadDate: () => undefined,
  uploadScope: 'public',
  setUploadScope: () => undefined,
  uploadClassName: '',
  setUploadClassName: () => undefined,
  uploadStudentIds: '',
  setUploadStudentIds: () => undefined,
  setUploadFiles: () => undefined,
  setUploadAnswerFiles: () => undefined,
  uploadError: '',
  uploadStatus: '',
  setExamId: () => undefined,
  examDate: '2026-03-14',
  setExamDate: () => undefined,
  examClassName: '',
  setExamClassName: () => undefined,
  setExamPaperFiles: () => undefined,
  setExamAnswerFiles: () => undefined,
  setExamScoreFiles: () => undefined,
  examUploadError: '',
  examUploadStatus: '',
  examDraftPanelCollapsed: false,
  setExamDraftPanelCollapsed: () => undefined,
  examDraftActionError: '',
  examDraftActionStatus: '',
  formatExamDraftSummary: () => 'exam-draft-summary',
  saveExamDraft: async () => undefined,
  handleConfirmExamUpload: async () => undefined,
  updateExamDraftMeta: () => undefined,
  updateExamQuestionField: () => undefined,
  updateExamAnswerKeyText: () => undefined,
  updateExamScoreSchemaSelectedCandidate: () => undefined,
  stopKeyPropagation: () => undefined,
  draftPanelCollapsed: false,
  setDraftPanelCollapsed: () => undefined,
  draftActionError: '',
  draftActionStatus: '',
  saveDraft: async () => undefined,
  handleConfirmUpload: async () => undefined,
  formatDraftSummary: () => 'draft-summary',
  formatMissingRequirements: () => 'missing',
  updateDraftRequirement: () => undefined,
  updateDraftQuestion: () => undefined,
  misconceptionsText: '',
  setMisconceptionsText: () => undefined,
  setMisconceptionsDirty: () => undefined,
  parseCommaList: () => [],
  parseLineList: () => [],
  difficultyLabel: () => '',
  difficultyOptions: [],
  normalizeDifficulty: () => 'medium',
  questionShowCount: 3,
  setQuestionShowCount: () => undefined,
}) as unknown as WorkflowTabProps

describe('WorkflowTab', () => {
  it('groups workflow content into current action and supplementary sections', () => {
    render(<WorkflowTab {...buildProps()} />)

    expect(screen.getByText('主线先做，补充后看。')).toBeTruthy()
    expect(screen.getByText('workflow-summary-card')).toBeTruthy()
    expect(screen.getByText('工作流编辑')).toBeTruthy()
    expect(screen.getByText('先完成必做动作，再展开补充参考。')).toBeTruthy()
    expect(screen.getByText('必做动作')).toBeTruthy()
    expect(screen.getByText('必做')).toBeTruthy()
    expect(screen.getByText('按下面的主线动作继续处理。')).toBeTruthy()
    expect(screen.queryByText('下一步：继续审核草稿并确认创建作业')).toBeNull()
    expect(screen.getByText('workflow-upload-section')).toBeTruthy()
    expect(screen.getByText('workflow-assignment-draft-section')).toBeTruthy()
    expect(screen.getByText('补充参考')).toBeTruthy()
    expect(screen.getByText('按需查看')).toBeTruthy()
    expect(screen.getByText('workflow-progress-section')).toBeTruthy()
    expect(screen.getByText('workflow-analysis-section')).toBeTruthy()
    expect(screen.getByText('workflow-video-analysis-section')).toBeTruthy()
    expect(screen.getByText('workflow-timeline-section')).toBeTruthy()
    expect(screen.getByTestId('teacher-workflow-primary-stage').getAttribute('data-workflow-tier')).toBe('primary')
    expect(screen.getByTestId('teacher-workflow-secondary-stage').getAttribute('data-workflow-tier')).toBe('supporting')

    const progressSection = screen.getByText('workflow-progress-section')
    const timelineSection = screen.getByText('workflow-timeline-section')

    expect(progressSection.compareDocumentPosition(timelineSection) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })
})
