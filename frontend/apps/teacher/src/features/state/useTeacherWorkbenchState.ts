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

  const setUploadMode = useCallback((value: 'assignment' | 'exam') => setField('uploadMode', value), [setField])
  const setUploadAssignmentId = useCallback((value: string) => setField('uploadAssignmentId', value), [setField])
  const setUploadDate = useCallback((value: string) => setField('uploadDate', value), [setField])
  const setUploadScope = useCallback((value: 'public' | 'class' | 'student') => setField('uploadScope', value), [setField])
  const setUploadClassName = useCallback((value: string) => setField('uploadClassName', value), [setField])
  const setUploadStudentIds = useCallback((value: string) => setField('uploadStudentIds', value), [setField])
  const setUploadFiles = useCallback((value: File[]) => setField('uploadFiles', value), [setField])
  const setUploadAnswerFiles = useCallback((value: File[]) => setField('uploadAnswerFiles', value), [setField])
  const setUploading = useCallback((value: boolean) => setField('uploading', value), [setField])
  const setUploadCardCollapsed = useCallback(
    (value: boolean | ((prev: boolean) => boolean)) => {
      if (typeof value === 'function') {
        update((prev) => ({ ...prev, uploadCardCollapsed: (value as any)(prev.uploadCardCollapsed) }))
        return
      }
      setField('uploadCardCollapsed', value)
    },
    [setField, update],
  )
  const setUploadJobId = useCallback((value: string) => setField('uploadJobId', value), [setField])
  const setUploadConfirming = useCallback((value: boolean) => setField('uploadConfirming', value), [setField])
  const setUploadStatusPollNonce = useCallback(
    (value: number | ((prev: number) => number)) => {
      if (typeof value === 'function') {
        update((prev) => ({ ...prev, uploadStatusPollNonce: (value as any)(prev.uploadStatusPollNonce) }))
        return
      }
      setField('uploadStatusPollNonce', value)
    },
    [setField, update],
  )
  const setUploadDraft = useCallback(
    (value: UploadDraft | null | ((prev: UploadDraft | null) => UploadDraft | null)) => {
      if (typeof value === 'function') {
        update((prev) => ({ ...prev, uploadDraft: (value as any)(prev.uploadDraft) }))
        return
      }
      setField('uploadDraft', value)
    },
    [setField, update],
  )
  const setDraftPanelCollapsed = useCallback(
    (value: boolean | ((prev: boolean) => boolean)) => {
      if (typeof value === 'function') {
        update((prev) => ({ ...prev, draftPanelCollapsed: (value as any)(prev.draftPanelCollapsed) }))
        return
      }
      setField('draftPanelCollapsed', value)
    },
    [setField, update],
  )
  const setDraftLoading = useCallback((value: boolean) => setField('draftLoading', value), [setField])
  const setDraftError = useCallback((value: string) => setField('draftError', value), [setField])
  const setQuestionShowCount = useCallback(
    (value: number | ((prev: number) => number)) => {
      if (typeof value === 'function') {
        update((prev) => ({ ...prev, questionShowCount: (value as any)(prev.questionShowCount) }))
        return
      }
      setField('questionShowCount', value)
    },
    [setField, update],
  )
  const setDraftSaving = useCallback((value: boolean) => setField('draftSaving', value), [setField])
  const setDraftActionStatus = useCallback((value: string) => setField('draftActionStatus', value), [setField])
  const setDraftActionError = useCallback((value: string) => setField('draftActionError', value), [setField])
  const setMisconceptionsText = useCallback((value: string) => setField('misconceptionsText', value), [setField])
  const setMisconceptionsDirty = useCallback((value: boolean) => setField('misconceptionsDirty', value), [setField])

  const setProgressPanelCollapsed = useCallback(
    (value: boolean | ((prev: boolean) => boolean)) => {
      if (typeof value === 'function') {
        update((prev) => ({ ...prev, progressPanelCollapsed: (value as any)(prev.progressPanelCollapsed) }))
        return
      }
      setField('progressPanelCollapsed', value)
    },
    [setField, update],
  )
  const setProgressAssignmentId = useCallback((value: string) => setField('progressAssignmentId', value), [setField])
  const setProgressLoading = useCallback((value: boolean) => setField('progressLoading', value), [setField])
  const setProgressError = useCallback((value: string) => setField('progressError', value), [setField])
  const setProgressData = useCallback((value: AssignmentProgress | null) => setField('progressData', value), [setField])
  const setProgressOnlyIncomplete = useCallback((value: boolean) => setField('progressOnlyIncomplete', value), [setField])

  const setProposalLoading = useCallback((value: boolean) => setField('proposalLoading', value), [setField])
  const setProposalError = useCallback((value: string) => setField('proposalError', value), [setField])
  const setProposals = useCallback((value: TeacherMemoryProposal[]) => setField('proposals', value), [setField])
  const setMemoryStatusFilter = useCallback((value: 'applied' | 'rejected' | 'all') => setField('memoryStatusFilter', value), [setField])
  const setMemoryInsights = useCallback((value: TeacherMemoryInsightsResponse | null) => setField('memoryInsights', value), [setField])

  const setExamId = useCallback((value: string) => setField('examId', value), [setField])
  const setExamDate = useCallback((value: string) => setField('examDate', value), [setField])
  const setExamClassName = useCallback((value: string) => setField('examClassName', value), [setField])
  const setExamPaperFiles = useCallback((value: File[]) => setField('examPaperFiles', value), [setField])
  const setExamScoreFiles = useCallback((value: File[]) => setField('examScoreFiles', value), [setField])
  const setExamAnswerFiles = useCallback((value: File[]) => setField('examAnswerFiles', value), [setField])
  const setExamUploading = useCallback((value: boolean) => setField('examUploading', value), [setField])
  const setExamJobId = useCallback((value: string) => setField('examJobId', value), [setField])
  const setExamStatusPollNonce = useCallback(
    (value: number | ((prev: number) => number)) => {
      if (typeof value === 'function') {
        update((prev) => ({ ...prev, examStatusPollNonce: (value as any)(prev.examStatusPollNonce) }))
        return
      }
      setField('examStatusPollNonce', value)
    },
    [setField, update],
  )
  const setExamDraft = useCallback(
    (value: ExamUploadDraft | null | ((prev: ExamUploadDraft | null) => ExamUploadDraft | null)) => {
      if (typeof value === 'function') {
        update((prev) => ({ ...prev, examDraft: (value as any)(prev.examDraft) }))
        return
      }
      setField('examDraft', value)
    },
    [setField, update],
  )
  const setExamDraftPanelCollapsed = useCallback(
    (value: boolean | ((prev: boolean) => boolean)) => {
      if (typeof value === 'function') {
        update((prev) => ({ ...prev, examDraftPanelCollapsed: (value as any)(prev.examDraftPanelCollapsed) }))
        return
      }
      setField('examDraftPanelCollapsed', value)
    },
    [setField, update],
  )
  const setExamDraftLoading = useCallback((value: boolean) => setField('examDraftLoading', value), [setField])
  const setExamDraftError = useCallback((value: string) => setField('examDraftError', value), [setField])
  const setExamDraftSaving = useCallback((value: boolean) => setField('examDraftSaving', value), [setField])
  const setExamDraftActionStatus = useCallback((value: string) => setField('examDraftActionStatus', value), [setField])
  const setExamDraftActionError = useCallback((value: string) => setField('examDraftActionError', value), [setField])
  const setExamConfirming = useCallback((value: boolean) => setField('examConfirming', value), [setField])

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
