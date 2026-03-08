/**
 * Shared type definitions for the workflow feature.
 *
 * Centralizes types used across WorkflowTab, UploadSection,
 * AssignmentDraftSection, ExamDraftSection, and WorkflowSummaryCard.
 */
import type { FormEvent, KeyboardEvent, Dispatch, SetStateAction } from 'react'
import type {
  UploadJobStatus,
  ExamUploadJobStatus,
  AssignmentProgress,
  UploadDraft,
  ExamUploadDraft,
  WorkflowIndicator,
} from '../appTypes'

// ── Primitive helpers ──────────────────────────────────────────────────

export type UploadScope = 'public' | 'class' | 'student'
type UploadMode = 'assignment' | 'exam'

type DifficultyOption = Readonly<{ value: string; label: string }>

export type AssignmentQuestion = {
  stem?: string
  answer?: string
  score?: number
  difficulty?: string
  kp?: string
  kp_id?: string
  tags?: string[] | string
  type?: string
  question_id?: string
}

export type ExamQuestion = {
  question_id?: string
  question_no?: string
  max_score?: number | null
}

// ── Formatter function signatures ──────────────────────────────────────

type FormatUploadJobSummary = (
  job: UploadJobStatus | null,
  fallbackId?: string,
) => string
type FormatExamJobSummary = (
  job: ExamUploadJobStatus | null,
  fallbackId?: string,
) => string
export type FormatProgressSummary = (
  data: AssignmentProgress | null,
  assignmentId?: string,
) => string
type FormatDraftSummary = (
  draft: UploadDraft | null,
  jobInfo: UploadJobStatus | null,
) => string
type FormatExamDraftSummary = (
  draft: ExamUploadDraft | null,
  jobInfo: ExamUploadJobStatus | null,
) => string
type FormatMissingRequirements = (missing?: string[]) => string
type DifficultyLabel = (value: string | number | undefined) => string
type NormalizeDifficulty = (value: string | number | undefined) => string

// ── Utility function signatures ────────────────────────────────────────

type ParseList = (text: string) => string[]
type StopKeyPropagation = (e: KeyboardEvent<HTMLElement>) => void

// ── Shared prop groups ─────────────────────────────────────────────────

export type UploadSectionProps = {
  // Upload mode & state
  uploadMode: UploadMode
  setUploadMode: (v: UploadMode) => void
  uploadCardCollapsed: boolean
  setUploadCardCollapsed: Dispatch<SetStateAction<boolean>>

  // Assignment upload fields
  uploadAssignmentId: string
  setUploadAssignmentId: (v: string) => void
  uploadDate: string
  setUploadDate: (v: string) => void
  uploadScope: UploadScope
  setUploadScope: (v: UploadScope) => void
  uploadClassName: string
  setUploadClassName: (v: string) => void
  uploadStudentIds: string
  setUploadStudentIds: (v: string) => void
  setUploadFiles: (v: File[]) => void
  setUploadAnswerFiles: (v: File[]) => void

  // Exam upload fields
  examId: string
  setExamId: (v: string) => void
  examDate: string
  setExamDate: (v: string) => void
  examClassName: string
  setExamClassName: (v: string) => void
  setExamPaperFiles: (v: File[]) => void
  setExamAnswerFiles: (v: File[]) => void
  setExamScoreFiles: (v: File[]) => void

  // Job info & status
  uploadJobInfo: UploadJobStatus | null
  examJobInfo: ExamUploadJobStatus | null
  uploadError: string
  uploadStatus: string
  examUploadError: string
  examUploadStatus: string

  // Actions
  handleUploadAssignment: (e: FormEvent) => Promise<void>
  handleUploadExam: (e: FormEvent) => Promise<void>

  // Formatters
  formatUploadJobSummary: FormatUploadJobSummary
  formatExamJobSummary: FormatExamJobSummary
}

export type AssignmentDraftSectionProps = {
  uploadDraft: UploadDraft | null
  uploadJobInfo: UploadJobStatus | null
  draftPanelCollapsed: boolean
  setDraftPanelCollapsed: Dispatch<SetStateAction<boolean>>
  draftActionError: string
  draftActionStatus: string
  misconceptionsText: string
  setMisconceptionsText: (v: string) => void
  setMisconceptionsDirty: (v: boolean) => void
  questionShowCount: number
  setQuestionShowCount: Dispatch<SetStateAction<number>>

  // Actions
  saveDraft: (draft: UploadDraft) => Promise<void>
  handleConfirmUpload: () => Promise<void>
  updateDraftRequirement: (key: string, value: string | string[] | number) => void
  updateDraftQuestion: (index: number, patch: Record<string, unknown>) => void

  // Formatters & utils
  formatDraftSummary: FormatDraftSummary
  formatMissingRequirements: FormatMissingRequirements
  parseCommaList: ParseList
  parseLineList: ParseList
  difficultyLabel: DifficultyLabel
  normalizeDifficulty: NormalizeDifficulty
  difficultyOptions: readonly DifficultyOption[]
  stopKeyPropagation: StopKeyPropagation
}

export type ExamDraftSectionProps = {
  examDraft: ExamUploadDraft | null
  examJobInfo: ExamUploadJobStatus | null
  examDraftPanelCollapsed: boolean
  setExamDraftPanelCollapsed: Dispatch<SetStateAction<boolean>>
  examDraftError: string
  examDraftActionError: string
  examDraftActionStatus: string

  // Actions
  saveExamDraft: (draft: ExamUploadDraft) => Promise<void>
  handleConfirmExamUpload: () => Promise<void>
  updateExamDraftMeta: (key: string, value: string) => void
  updateExamQuestionField: (index: number, patch: Record<string, unknown>) => void
  updateExamAnswerKeyText: (value: string) => void
  updateExamScoreSchemaSelectedCandidate: (candidateId: string) => void

  // Formatters & utils
  formatExamDraftSummary: FormatExamDraftSummary
  stopKeyPropagation: StopKeyPropagation
}

export type WorkflowSummaryCardProps = {
  activeWorkflowIndicator: WorkflowIndicator
  uploadMode: UploadMode
  setUploadMode: (v: UploadMode) => void
  uploadJobInfo: UploadJobStatus | null
  uploadAssignmentId: string
  examJobInfo: ExamUploadJobStatus | null
  examId: string
  progressData: AssignmentProgress | null
  progressAssignmentId: string
  progressLoading: boolean

  // Actions
  scrollToWorkflowSection: (sectionId: string) => void
  refreshWorkflowWorkbench: () => void
  fetchAssignmentProgress: (assignmentId?: string) => Promise<void>

  // Formatters
  formatUploadJobSummary: FormatUploadJobSummary
  formatExamJobSummary: FormatExamJobSummary
  formatProgressSummary: FormatProgressSummary
}

export type AnalysisReportSummary = {
  report_id: string
  domain?: string | null
  analysis_type: string
  target_type: string
  target_id: string
  strategy_id: string
  teacher_id: string
  status: string
  confidence?: number | null
  summary?: string | null
  review_required: boolean
  created_at?: string | null
  updated_at?: string | null
}

export type AnalysisReportDetail = {
  report: AnalysisReportSummary
  analysis_artifact: Record<string, unknown>
  artifact_meta: Record<string, unknown>
}

export type AnalysisReviewQueueItem = {
  item_id: string
  domain: string
  report_id: string
  teacher_id: string
  status: string
  reason: string
  reason_code?: string | null
  disposition?: string | null
  reviewer_id?: string | null
  operator_note?: string | null
  confidence?: number | null
  created_at?: string | null
  updated_at?: string | null
  claimed_at?: string | null
  resolved_at?: string | null
  rejected_at?: string | null
  dismissed_at?: string | null
  escalated_at?: string | null
  retried_at?: string | null
}

export type AnalysisReviewQueueSummary = {
  total_items: number
  unresolved_items: number
  status_counts?: Record<string, number>
  reason_counts?: Record<string, number>
  domains: Array<{
    domain: string
    total_items: number
    unresolved_items: number
    status_counts?: Record<string, number>
    reason_counts?: Record<string, number>
  }>
  generated_at?: string | null
}

export type AnalysisReportSectionProps = {
  analysisFeatureEnabled: boolean
  analysisFeatureShadowMode: boolean
  analysisReportsLoading: boolean
  analysisReportsError: string
  analysisReports: AnalysisReportSummary[]
  selectedAnalysisReportId: string
  selectedAnalysisReport: AnalysisReportDetail | null
  analysisReviewQueue: AnalysisReviewQueueItem[]
  analysisDomainFilter: string
  analysisStatusFilter: string
  analysisStrategyFilter: string
  analysisTargetTypeFilter: string
  setAnalysisDomainFilter: (value: string) => void
  setAnalysisStatusFilter: (value: string) => void
  setAnalysisStrategyFilter: (value: string) => void
  setAnalysisTargetTypeFilter: (value: string) => void
  refreshAnalysisReports: () => void | Promise<void>
  selectAnalysisReport: (reportId: string, domain?: string) => void | Promise<void>
  rerunAnalysisReport: (reportId: string, domain?: string) => void | Promise<void>
}

export type VideoHomeworkAnalysisSectionProps = {
  videoHomeworkFeatureEnabled: boolean
  analysisReports: AnalysisReportSummary[]
  selectedAnalysisReport: AnalysisReportDetail | null
}

export type SurveyReportSummary = {
  report_id: string
  teacher_id: string
  class_name?: string | null
  status: string
  confidence?: number | null
  summary?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export type SurveyReportDetail = {
  report: SurveyReportSummary
  analysis_artifact: Record<string, unknown>
  bundle_meta: Record<string, unknown>
  review_required: boolean
}

export type SurveyReviewQueueItem = {
  report_id: string
  teacher_id: string
  reason: string
  confidence?: number | null
  created_at?: string | null
}

export type SurveyAnalysisSectionProps = {
  surveyFeatureEnabled: boolean
  surveyFeatureShadowMode: boolean
  surveyReportsLoading: boolean
  surveyReportsError: string
  surveyReports: SurveyReportSummary[]
  selectedSurveyReportId: string
  selectedSurveyReport: SurveyReportDetail | null
  surveyReviewQueue: SurveyReviewQueueItem[]
  refreshSurveyReports: () => void | Promise<void>
  selectSurveyReport: (reportId: string) => void | Promise<void>
  rerunSurveyReport: (reportId: string) => void | Promise<void>
}
