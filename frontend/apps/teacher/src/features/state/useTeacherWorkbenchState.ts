import { useCallback, useReducer } from 'react'
import {
  createInitialTeacherWorkbenchState,
  teacherWorkbenchReducer,
  type TeacherWorkbenchState,
} from './teacherWorkbenchState'
import type { AssignmentProgress, ExamUploadDraft, ExamUploadJobStatus, TeacherMemoryInsightsResponse, TeacherMemoryProposal, UploadDraft, UploadJobStatus } from '../../appTypes'

export function useTeacherWorkbenchState() {
  const [state, dispatch] = useReducer(teacherWorkbenchReducer, undefined, createInitialTeacherWorkbenchState)

  const setField = useCallback(
    (key: keyof TeacherWorkbenchState, value: TeacherWorkbenchState[keyof TeacherWorkbenchState]) => {
      dispatch({ type: 'set', key, value })
    },
    [dispatch],
  )

  const update = useCallback(
    (updater: (prev: TeacherWorkbenchState) => TeacherWorkbenchState) => {
      dispatch({ type: 'update', update: updater })
    },
    [dispatch],
  )

  const setUploadJobInfo = useCallback(
    (value: UploadJobStatus | null | ((prev: UploadJobStatus | null) => UploadJobStatus | null)) => {
      if (typeof value === 'function') {
        update((prev) => ({ ...prev, uploadJobInfo: (value as any)(prev.uploadJobInfo) }))
        return
      }
      setField('uploadJobInfo', value)
    },
    [setField, update],
  )

  const setExamJobInfo = useCallback(
    (value: ExamUploadJobStatus | null | ((prev: ExamUploadJobStatus | null) => ExamUploadJobStatus | null)) => {
      if (typeof value === 'function') {
        update((prev) => ({ ...prev, examJobInfo: (value as any)(prev.examJobInfo) }))
        return
      }
      setField('examJobInfo', value)
    },
    [setField, update],
  )

  const setUploadError = useCallback((value: string) => setField('uploadError', value), [setField])

  const setUploadStatus = useCallback(
    (value: string | ((prev: string) => string)) => {
      if (typeof value === 'function') {
        update((prev) => ({ ...prev, uploadStatus: (value as any)(prev.uploadStatus) }))
        return
      }
      setField('uploadStatus', value)
    },
    [setField, update],
  )

  const setExamUploadError = useCallback((value: string) => setField('examUploadError', value), [setField])

  const setExamUploadStatus = useCallback(
    (value: string | ((prev: string) => string)) => {
      if (typeof value === 'function') {
        update((prev) => ({ ...prev, examUploadStatus: (value as any)(prev.examUploadStatus) }))
        return
      }
      setField('examUploadStatus', value)
    },
    [setField, update],
  )

  const setUploadMode = (value: 'assignment' | 'exam') => setField('uploadMode', value)
  const setUploadAssignmentId = (value: string) => setField('uploadAssignmentId', value)
  const setUploadDate = (value: string) => setField('uploadDate', value)
  const setUploadScope = (value: 'public' | 'class' | 'student') => setField('uploadScope', value)
  const setUploadClassName = (value: string) => setField('uploadClassName', value)
  const setUploadStudentIds = (value: string) => setField('uploadStudentIds', value)
  const setUploadFiles = (value: File[]) => setField('uploadFiles', value)
  const setUploadAnswerFiles = (value: File[]) => setField('uploadAnswerFiles', value)
  const setUploading = (value: boolean) => setField('uploading', value)
  const setUploadCardCollapsed = (value: boolean | ((prev: boolean) => boolean)) => {
    if (typeof value === 'function') {
      update((prev) => ({ ...prev, uploadCardCollapsed: (value as any)(prev.uploadCardCollapsed) }))
      return
    }
    setField('uploadCardCollapsed', value)
  }
  const setUploadJobId = (value: string) => setField('uploadJobId', value)
  const setUploadConfirming = (value: boolean) => setField('uploadConfirming', value)
  const setUploadStatusPollNonce = (value: number | ((prev: number) => number)) => {
    if (typeof value === 'function') {
      update((prev) => ({ ...prev, uploadStatusPollNonce: (value as any)(prev.uploadStatusPollNonce) }))
      return
    }
    setField('uploadStatusPollNonce', value)
  }
  const setUploadDraft = (value: UploadDraft | null | ((prev: UploadDraft | null) => UploadDraft | null)) => {
    if (typeof value === 'function') {
      update((prev) => ({ ...prev, uploadDraft: (value as any)(prev.uploadDraft) }))
      return
    }
    setField('uploadDraft', value)
  }
  const setDraftPanelCollapsed = (value: boolean | ((prev: boolean) => boolean)) => {
    if (typeof value === 'function') {
      update((prev) => ({ ...prev, draftPanelCollapsed: (value as any)(prev.draftPanelCollapsed) }))
      return
    }
    setField('draftPanelCollapsed', value)
  }
  const setDraftLoading = (value: boolean) => setField('draftLoading', value)
  const setDraftError = (value: string) => setField('draftError', value)
  const setQuestionShowCount = (value: number | ((prev: number) => number)) => {
    if (typeof value === 'function') {
      update((prev) => ({ ...prev, questionShowCount: (value as any)(prev.questionShowCount) }))
      return
    }
    setField('questionShowCount', value)
  }
  const setDraftSaving = (value: boolean) => setField('draftSaving', value)
  const setDraftActionStatus = (value: string) => setField('draftActionStatus', value)
  const setDraftActionError = (value: string) => setField('draftActionError', value)
  const setMisconceptionsText = (value: string) => setField('misconceptionsText', value)
  const setMisconceptionsDirty = (value: boolean) => setField('misconceptionsDirty', value)

  const setProgressPanelCollapsed = (value: boolean | ((prev: boolean) => boolean)) => {
    if (typeof value === 'function') {
      update((prev) => ({ ...prev, progressPanelCollapsed: (value as any)(prev.progressPanelCollapsed) }))
      return
    }
    setField('progressPanelCollapsed', value)
  }
  const setProgressAssignmentId = (value: string) => setField('progressAssignmentId', value)
  const setProgressLoading = (value: boolean) => setField('progressLoading', value)
  const setProgressError = (value: string) => setField('progressError', value)
  const setProgressData = (value: AssignmentProgress | null) => setField('progressData', value)
  const setProgressOnlyIncomplete = (value: boolean) => setField('progressOnlyIncomplete', value)

  const setProposalLoading = (value: boolean) => setField('proposalLoading', value)
  const setProposalError = (value: string) => setField('proposalError', value)
  const setProposals = (value: TeacherMemoryProposal[]) => setField('proposals', value)
  const setMemoryStatusFilter = (value: 'applied' | 'rejected' | 'all') => setField('memoryStatusFilter', value)
  const setMemoryInsights = (value: TeacherMemoryInsightsResponse | null) => setField('memoryInsights', value)

  const setExamId = (value: string) => setField('examId', value)
  const setExamDate = (value: string) => setField('examDate', value)
  const setExamClassName = (value: string) => setField('examClassName', value)
  const setExamPaperFiles = (value: File[]) => setField('examPaperFiles', value)
  const setExamScoreFiles = (value: File[]) => setField('examScoreFiles', value)
  const setExamAnswerFiles = (value: File[]) => setField('examAnswerFiles', value)
  const setExamUploading = (value: boolean) => setField('examUploading', value)
  const setExamJobId = (value: string) => setField('examJobId', value)
  const setExamStatusPollNonce = (value: number | ((prev: number) => number)) => {
    if (typeof value === 'function') {
      update((prev) => ({ ...prev, examStatusPollNonce: (value as any)(prev.examStatusPollNonce) }))
      return
    }
    setField('examStatusPollNonce', value)
  }
  const setExamDraft = (value: ExamUploadDraft | null | ((prev: ExamUploadDraft | null) => ExamUploadDraft | null)) => {
    if (typeof value === 'function') {
      update((prev) => ({ ...prev, examDraft: (value as any)(prev.examDraft) }))
      return
    }
    setField('examDraft', value)
  }
  const setExamDraftPanelCollapsed = (value: boolean | ((prev: boolean) => boolean)) => {
    if (typeof value === 'function') {
      update((prev) => ({ ...prev, examDraftPanelCollapsed: (value as any)(prev.examDraftPanelCollapsed) }))
      return
    }
    setField('examDraftPanelCollapsed', value)
  }
  const setExamDraftLoading = (value: boolean) => setField('examDraftLoading', value)
  const setExamDraftError = (value: string) => setField('examDraftError', value)
  const setExamDraftSaving = (value: boolean) => setField('examDraftSaving', value)
  const setExamDraftActionStatus = (value: string) => setField('examDraftActionStatus', value)
  const setExamDraftActionError = (value: string) => setField('examDraftActionError', value)
  const setExamConfirming = (value: boolean) => setField('examConfirming', value)

  return {
    ...state,
    setUploadMode,
    setUploadAssignmentId,
    setUploadDate,
    setUploadScope,
    setUploadClassName,
    setUploadStudentIds,
    setUploadFiles,
    setUploadAnswerFiles,
    setUploading,
    setUploadStatus,
    setUploadError,
    setUploadCardCollapsed,
    setUploadJobId,
    setUploadJobInfo,
    setUploadConfirming,
    setUploadStatusPollNonce,
    setUploadDraft,
    setDraftPanelCollapsed,
    setDraftLoading,
    setDraftError,
    setQuestionShowCount,
    setDraftSaving,
    setDraftActionStatus,
    setDraftActionError,
    setMisconceptionsText,
    setMisconceptionsDirty,
    setProgressPanelCollapsed,
    setProgressAssignmentId,
    setProgressLoading,
    setProgressError,
    setProgressData,
    setProgressOnlyIncomplete,
    setProposalLoading,
    setProposalError,
    setProposals,
    setMemoryStatusFilter,
    setMemoryInsights,
    setExamId,
    setExamDate,
    setExamClassName,
    setExamPaperFiles,
    setExamScoreFiles,
    setExamAnswerFiles,
    setExamUploading,
    setExamUploadStatus,
    setExamUploadError,
    setExamJobId,
    setExamJobInfo,
    setExamStatusPollNonce,
    setExamDraft,
    setExamDraftPanelCollapsed,
    setExamDraftLoading,
    setExamDraftError,
    setExamDraftSaving,
    setExamDraftActionStatus,
    setExamDraftActionError,
    setExamConfirming,
  }
}

