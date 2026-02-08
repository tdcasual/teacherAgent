import { safeLocalStorageGetItem } from '../../utils/storage'
import type {
  AssignmentProgress,
  ExamUploadDraft,
  ExamUploadJobStatus,
  TeacherMemoryInsightsResponse,
  TeacherMemoryProposal,
  UploadDraft,
  UploadJobStatus,
} from '../../appTypes'

export type TeacherWorkbenchState = {
  uploadMode: 'assignment' | 'exam'

  uploadAssignmentId: string
  uploadDate: string
  uploadScope: 'public' | 'class' | 'student'
  uploadClassName: string
  uploadStudentIds: string
  uploadFiles: File[]
  uploadAnswerFiles: File[]
  uploading: boolean
  uploadStatus: string
  uploadError: string
  uploadCardCollapsed: boolean
  uploadJobId: string
  uploadJobInfo: UploadJobStatus | null
  uploadConfirming: boolean
  uploadStatusPollNonce: number
  uploadDraft: UploadDraft | null
  draftPanelCollapsed: boolean
  draftLoading: boolean
  draftError: string
  questionShowCount: number
  draftSaving: boolean
  draftActionStatus: string
  draftActionError: string
  misconceptionsText: string
  misconceptionsDirty: boolean

  progressPanelCollapsed: boolean
  progressAssignmentId: string
  progressLoading: boolean
  progressError: string
  progressData: AssignmentProgress | null
  progressOnlyIncomplete: boolean

  proposalLoading: boolean
  proposalError: string
  proposals: TeacherMemoryProposal[]
  memoryStatusFilter: 'applied' | 'rejected' | 'all'
  memoryInsights: TeacherMemoryInsightsResponse | null

  examId: string
  examDate: string
  examClassName: string
  examPaperFiles: File[]
  examScoreFiles: File[]
  examAnswerFiles: File[]
  examUploading: boolean
  examUploadStatus: string
  examUploadError: string
  examJobId: string
  examJobInfo: ExamUploadJobStatus | null
  examStatusPollNonce: number
  examDraft: ExamUploadDraft | null
  examDraftPanelCollapsed: boolean
  examDraftLoading: boolean
  examDraftError: string
  examDraftSaving: boolean
  examDraftActionStatus: string
  examDraftActionError: string
  examConfirming: boolean
}

export type TeacherWorkbenchAction =
  | { type: 'set'; key: keyof TeacherWorkbenchState; value: TeacherWorkbenchState[keyof TeacherWorkbenchState] }
  | { type: 'update'; update: (prev: TeacherWorkbenchState) => TeacherWorkbenchState }

export const createInitialTeacherWorkbenchState = (): TeacherWorkbenchState => {
  const raw = safeLocalStorageGetItem('teacherUploadMode')
  const uploadMode = raw === 'exam' ? 'exam' : 'assignment'

  return {
    uploadMode,

    uploadAssignmentId: '',
    uploadDate: '',
    uploadScope: 'public',
    uploadClassName: '',
    uploadStudentIds: '',
    uploadFiles: [],
    uploadAnswerFiles: [],
    uploading: false,
    uploadStatus: '',
    uploadError: '',
    uploadCardCollapsed: false,
    uploadJobId: '',
    uploadJobInfo: null,
    uploadConfirming: false,
    uploadStatusPollNonce: 0,
    uploadDraft: null,
    draftPanelCollapsed: false,
    draftLoading: false,
    draftError: '',
    questionShowCount: 20,
    draftSaving: false,
    draftActionStatus: '',
    draftActionError: '',
    misconceptionsText: '',
    misconceptionsDirty: false,

    progressPanelCollapsed: true,
    progressAssignmentId: '',
    progressLoading: false,
    progressError: '',
    progressData: null,
    progressOnlyIncomplete: true,

    proposalLoading: false,
    proposalError: '',
    proposals: [],
    memoryStatusFilter: 'applied',
    memoryInsights: null,

    examId: '',
    examDate: '',
    examClassName: '',
    examPaperFiles: [],
    examScoreFiles: [],
    examAnswerFiles: [],
    examUploading: false,
    examUploadStatus: '',
    examUploadError: '',
    examJobId: '',
    examJobInfo: null,
    examStatusPollNonce: 0,
    examDraft: null,
    examDraftPanelCollapsed: false,
    examDraftLoading: false,
    examDraftError: '',
    examDraftSaving: false,
    examDraftActionStatus: '',
    examDraftActionError: '',
    examConfirming: false,
  }
}

export const teacherWorkbenchReducer = (state: TeacherWorkbenchState, action: TeacherWorkbenchAction): TeacherWorkbenchState => {
  if (action.type === 'update') return action.update(state)
  if (action.type === 'set') return { ...state, [action.key]: action.value } as TeacherWorkbenchState
  return state
}

