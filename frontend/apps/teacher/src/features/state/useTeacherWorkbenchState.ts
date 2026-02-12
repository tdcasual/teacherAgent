import { useCallback, useReducer } from 'react'
import {
  createInitialTeacherWorkbenchState,
  teacherWorkbenchReducer,
  type TeacherWorkbenchState,
} from './teacherWorkbenchState'
import type { AssignmentProgress, ExamUploadDraft, ExamUploadJobStatus, TeacherMemoryInsightsResponse, TeacherMemoryProposal, UploadDraft, UploadJobStatus } from '../../appTypes'

type StateSetterValue<T> = T | ((prev: T) => T)

const resolveStateSetter = <T>(value: StateSetterValue<T>, prev: T): T => {
  if (typeof value === 'function') {
    return (value as (prev: T) => T)(prev)
  }
  return value
}

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
    (value: StateSetterValue<UploadJobStatus | null>) => {
      update((prev) => ({ ...prev, uploadJobInfo: resolveStateSetter(value, prev.uploadJobInfo) }))
    },
    [update],
  )

  const setExamJobInfo = useCallback(
    (value: StateSetterValue<ExamUploadJobStatus | null>) => {
      update((prev) => ({ ...prev, examJobInfo: resolveStateSetter(value, prev.examJobInfo) }))
    },
    [update],
  )

  const setUploadError = useCallback((value: string) => setField('uploadError', value), [setField])

  const setUploadStatus = useCallback(
    (value: StateSetterValue<string>) => {
      update((prev) => ({ ...prev, uploadStatus: resolveStateSetter(value, prev.uploadStatus) }))
    },
    [update],
  )

  const setExamUploadError = useCallback((value: string) => setField('examUploadError', value), [setField])

  const setExamUploadStatus = useCallback(
    (value: StateSetterValue<string>) => {
      update((prev) => ({ ...prev, examUploadStatus: resolveStateSetter(value, prev.examUploadStatus) }))
    },
    [update],
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
    (value: StateSetterValue<boolean>) => {
      update((prev) => ({ ...prev, uploadCardCollapsed: resolveStateSetter(value, prev.uploadCardCollapsed) }))
    },
    [update],
  )
  const setUploadJobId = useCallback((value: string) => setField('uploadJobId', value), [setField])
  const setUploadConfirming = useCallback((value: boolean) => setField('uploadConfirming', value), [setField])
  const setUploadStatusPollNonce = useCallback(
    (value: StateSetterValue<number>) => {
      update((prev) => ({ ...prev, uploadStatusPollNonce: resolveStateSetter(value, prev.uploadStatusPollNonce) }))
    },
    [update],
  )
  const setUploadDraft = useCallback(
    (value: StateSetterValue<UploadDraft | null>) => {
      update((prev) => ({ ...prev, uploadDraft: resolveStateSetter(value, prev.uploadDraft) }))
    },
    [update],
  )
  const setDraftPanelCollapsed = useCallback(
    (value: StateSetterValue<boolean>) => {
      update((prev) => ({ ...prev, draftPanelCollapsed: resolveStateSetter(value, prev.draftPanelCollapsed) }))
    },
    [update],
  )
  const setDraftLoading = useCallback((value: boolean) => setField('draftLoading', value), [setField])
  const setDraftError = useCallback((value: string) => setField('draftError', value), [setField])
  const setQuestionShowCount = useCallback(
    (value: StateSetterValue<number>) => {
      update((prev) => ({ ...prev, questionShowCount: resolveStateSetter(value, prev.questionShowCount) }))
    },
    [update],
  )
  const setDraftSaving = useCallback((value: boolean) => setField('draftSaving', value), [setField])
  const setDraftActionStatus = useCallback((value: string) => setField('draftActionStatus', value), [setField])
  const setDraftActionError = useCallback((value: string) => setField('draftActionError', value), [setField])
  const setMisconceptionsText = useCallback((value: string) => setField('misconceptionsText', value), [setField])
  const setMisconceptionsDirty = useCallback((value: boolean) => setField('misconceptionsDirty', value), [setField])

  const setProgressPanelCollapsed = useCallback(
    (value: StateSetterValue<boolean>) => {
      update((prev) => ({ ...prev, progressPanelCollapsed: resolveStateSetter(value, prev.progressPanelCollapsed) }))
    },
    [update],
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
    (value: StateSetterValue<number>) => {
      update((prev) => ({ ...prev, examStatusPollNonce: resolveStateSetter(value, prev.examStatusPollNonce) }))
    },
    [update],
  )
  const setExamDraft = useCallback(
    (value: StateSetterValue<ExamUploadDraft | null>) => {
      update((prev) => ({ ...prev, examDraft: resolveStateSetter(value, prev.examDraft) }))
    },
    [update],
  )
  const setExamDraftPanelCollapsed = useCallback(
    (value: StateSetterValue<boolean>) => {
      update((prev) => ({ ...prev, examDraftPanelCollapsed: resolveStateSetter(value, prev.examDraftPanelCollapsed) }))
    },
    [update],
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
