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
export type UploadMode = 'assignment' | 'exam'

export type DifficultyOption = Readonly<{ value: string; label: string }>

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

export type FormatUploadJobSummary = (
  job: UploadJobStatus | null,
  fallbackId?: string,
) => string
export type FormatExamJobSummary = (
  job: ExamUploadJobStatus | null,
  fallbackId?: string,
) => string
export type FormatProgressSummary = (
  data: AssignmentProgress | null,
  assignmentId?: string,
) => string
export type FormatDraftSummary = (
  draft: UploadDraft | null,
  jobInfo: UploadJobStatus | null,
) => string
export type FormatExamDraftSummary = (
  draft: ExamUploadDraft | null,
  jobInfo: ExamUploadJobStatus | null,
) => string
export type FormatMissingRequirements = (missing?: string[]) => string
export type DifficultyLabel = (value: string | number | undefined) => string
export type NormalizeDifficulty = (value: string | number | undefined) => string

// ── Utility function signatures ────────────────────────────────────────

export type ParseList = (text: string) => string[]
export type StopKeyPropagation = (e: KeyboardEvent<HTMLElement>) => void

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
