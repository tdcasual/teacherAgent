import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { Group, Panel, Separator, type PanelImperativeHandle } from 'react-resizable-panels'
import TeacherSettingsPanel from './features/settings/TeacherSettingsPanel'
import TeacherTopbar from './features/layout/TeacherTopbar'
import { useChatScroll } from './features/chat/useChatScroll'
import {
  readTeacherLocalViewState,
  type SessionViewStatePayload,
} from './features/chat/viewState'
import { useTeacherSessionViewStateSync } from './features/chat/useTeacherSessionViewStateSync'
import { withPendingChatOverlay } from './features/chat/pendingOverlay'
import { fallbackSkills, TEACHER_GREETING } from './features/chat/catalog'
import TeacherChatMainContent from './features/chat/TeacherChatMainContent'
import TeacherSessionRail from './features/chat/TeacherSessionRail'
import SessionSidebar from './features/chat/SessionSidebar'
import TeacherWorkbench from './features/workbench/TeacherWorkbench'
import { buildTeacherWorkbenchViewModel } from './features/workbench/teacherWorkbenchViewModel'
import { useAssignmentUploadStatusPolling } from './features/workbench/useAssignmentUploadStatusPolling'
import { useExamUploadStatusPolling } from './features/workbench/useExamUploadStatusPolling'
import { useTeacherWorkbenchPanelControls } from './features/workbench/useTeacherWorkbenchPanelControls'
import {
  formatDraftSummary,
  formatExamDraftSummary,
  formatExamJobStatus,
  formatExamJobSummary,
  formatProgressSummary,
  formatUploadJobStatus,
  formatUploadJobSummary,
} from './features/workbench/workbenchFormatters'
import { buildExamWorkflowIndicator } from './features/workbench/workflowIndicators'
import {
  difficultyLabel,
  difficultyOptions,
  formatMissingRequirements,
  normalizeDifficulty,
  parseCommaList,
  parseLineList,
} from './features/workbench/workbenchUtils'
import {
  readFeatureFlag,
  readTeacherAnalysisWorkbenchFlag,
  readTeacherAnalysisWorkbenchShadowFlag,
} from '../../shared/featureFlags'
import { ConfirmDialog, PromptDialog } from '../../shared/dialog'
import { BottomSheet } from '../../shared/mobile/BottomSheet'
import { MobileTabBar, type MobileTabItem } from '../../shared/mobile/MobileTabBar'
import {
  MobileTabChatIcon,
  MobileTabSessionIcon,
  MobileTabWorkbenchIcon,
} from '../../shared/mobile/tabIcons'
import { useChatAttachments } from '../../shared/useChatAttachments'
import { safeLocalStorageGetItem, safeLocalStorageRemoveItem, safeLocalStorageSetItem } from './utils/storage'
import { makeId } from './utils/id'
import { formatSessionUpdatedLabel, nowTime } from './utils/time'
import { useTeacherWorkbenchState } from './features/state/useTeacherWorkbenchState'
import { useDraftMutations } from './features/workbench/hooks/useDraftMutations'
import { useAnalysisReports } from './features/workbench/hooks/useAnalysisReports'
import { useWheelScrollZone } from './features/chat/useWheelScrollZone'
import { useLocalStorageSync } from './features/state/useLocalStorageSync'
import { useSessionActions } from './features/chat/useSessionActions'
import { useAssignmentWorkflow } from './features/workbench/hooks/useAssignmentWorkflow'
import { useExamWorkflow } from './features/workbench/hooks/useExamWorkflow'
import { useTeacherChatApi } from './features/chat/useTeacherChatApi'
import { useTeacherComposerInteractions } from './features/chat/useTeacherComposerInteractions'
import { useTeacherSessionSidebarModel } from './features/chat/useTeacherSessionSidebarModel'
import { useTeacherUiPanels } from './features/chat/useTeacherUiPanels'
import { parsePendingChatJob } from './features/chat/pendingChatJob'
import { useTeacherSessionState } from './features/state/useTeacherSessionState'
import { readTeacherAuthSubject } from './features/auth/teacherAuth'
import {
  isTeacherMobileTab,
  teacherMobilePanelsFromTab,
} from './features/layout/mobileShellState'
import type {
  Message,
  PendingChatJob,
  PendingToolRun,
  Skill,
  WorkbenchTab,
  WorkflowIndicator,
} from './appTypes'
import 'katex/dist/katex.min.css'
const DEFAULT_API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const DESKTOP_BREAKPOINT = 900
const WORKBENCH_DEFAULT_WIDTH = 320
const WORKBENCH_MIN_WIDTH = 280
const WORKBENCH_BASE_MAX_WIDTH = 620
const WORKBENCH_MAX_WIDTH_RATIO = 0.42
const WORKBENCH_HARD_MAX_WIDTH = 920
const TEACHER_MOBILE_TAB_ITEMS: MobileTabItem[] = [
  { id: 'chat', label: '聊天', icon: <MobileTabChatIcon /> },
  { id: 'sessions', label: '会话', icon: <MobileTabSessionIcon /> },
  { id: 'workbench', label: '工作台', icon: <MobileTabWorkbenchIcon /> },
]
const workbenchMaxWidthForViewport = (viewportWidth: number) => {
  const fluidMax = Math.round(viewportWidth * WORKBENCH_MAX_WIDTH_RATIO)
  return Math.min(WORKBENCH_HARD_MAX_WIDTH, Math.max(WORKBENCH_BASE_MAX_WIDTH, fluidMax))
}

export default function App() {
  const initialViewStateRef = useRef<SessionViewStatePayload>(readTeacherLocalViewState())
  const workbenchPanelRef = useRef<PanelImperativeHandle | null>(null)
  const workbench = useTeacherWorkbenchState()
  const session = useTeacherSessionState(initialViewStateRef.current)
  const [viewportWidth, setViewportWidth] = useState(() => (typeof window !== 'undefined' ? window.innerWidth : 1280))
  const isMobileLayout = viewportWidth <= DESKTOP_BREAKPOINT
  const workbenchMaxWidth = workbenchMaxWidthForViewport(viewportWidth)
  const mobileShellV2Enabled = useMemo(() => {
    const source: Record<string, string | undefined> = {
      mobileShellV2: import.meta.env.VITE_MOBILE_SHELL_V2_TEACHER,
    }
    if (typeof window !== 'undefined') {
      try {
        const localOverride = window.localStorage.getItem('teacherMobileShellV2')
        if (localOverride != null) source.mobileShellV2 = localOverride
      } catch {
        // ignore localStorage read failures
      }
    }
    return readFeatureFlag('mobileShellV2', true, source)
  }, [])
  const teacherUseMobileShellV2 = mobileShellV2Enabled && isMobileLayout
  const [initialWorkbenchWidth] = useState(() => {
    if (typeof window === 'undefined') return WORKBENCH_DEFAULT_WIDTH
    const initialViewportWidth = window.innerWidth
    const initialWorkbenchMaxWidth = workbenchMaxWidthForViewport(initialViewportWidth)
    try {
      const raw = window.localStorage.getItem('teacherWorkbenchWidth')
      const parsed = Number(raw)
      if (Number.isFinite(parsed)) {
        return Math.min(initialWorkbenchMaxWidth, Math.max(WORKBENCH_MIN_WIDTH, Math.round(parsed)))
      }
    } catch {
      // ignore
    }
    return WORKBENCH_DEFAULT_WIDTH
  })
  const {
    uploadMode, uploadAssignmentId, uploadDate, uploadScope, uploadClassName, uploadStudentIds, uploadFiles, uploadAnswerFiles,
    uploading, uploadStatus, uploadError, uploadCardCollapsed, uploadJobId, uploadJobInfo, uploadConfirming, uploadStatusPollNonce,
    uploadDraft, draftPanelCollapsed, draftLoading, draftError, questionShowCount, draftSaving, draftActionStatus, draftActionError,
    misconceptionsText, misconceptionsDirty, progressPanelCollapsed, progressAssignmentId, progressLoading, progressError, progressData,
    progressOnlyIncomplete, memoryStatusFilter, studentMemoryStatusFilter, studentMemoryStudentFilter,
    examId, examDate, examClassName, examPaperFiles, examScoreFiles, examAnswerFiles, examUploading, examUploadError,
    examJobId, examJobInfo, examStatusPollNonce, examDraft, examDraftPanelCollapsed, examDraftError, examDraftSaving,
    examDraftActionError, examConfirming,
    setUploadMode, setUploadFiles,
    setUploadAnswerFiles, setUploading, setUploadStatus, setUploadError, setUploadCardCollapsed, setUploadJobId, setUploadJobInfo,
    setUploadConfirming, setUploadStatusPollNonce, setUploadDraft, setDraftPanelCollapsed, setDraftLoading, setDraftError,
    setQuestionShowCount, setDraftSaving, setDraftActionStatus, setDraftActionError, setMisconceptionsText, setMisconceptionsDirty,
    setProgressPanelCollapsed, setProgressAssignmentId, setProgressLoading, setProgressError, setProgressData,
    setProposalLoading, setProposalError, setProposals, setMemoryInsights, setStudentProposalLoading,
    setStudentProposalError, setStudentProposals, setStudentMemoryInsights,
    setExamPaperFiles, setExamScoreFiles, setExamAnswerFiles, setExamUploading,
    setExamUploadStatus, setExamUploadError, setExamJobId, setExamJobInfo, setExamStatusPollNonce, setExamDraft,
    setExamDraftPanelCollapsed, setExamDraftLoading, setExamDraftError, setExamDraftSaving, setExamDraftActionStatus,
    setExamDraftActionError, setExamConfirming,
  } = workbench
  const {
    historySessions, historyLoading, historyError, historyCursor, historyHasMore, historyQuery, showArchivedSessions,
    sessionTitleMap, deletedSessionIds, localDraftSessionIds, openSessionMenuId, renameDialogSessionId, archiveDialogSessionId,
    sessionLoading, sessionError, sessionCursor, sessionHasMore, activeSessionId, viewStateUpdatedAt,
    setHistorySessions, setHistoryLoading, setHistoryError, setHistoryCursor, setHistoryHasMore, setHistoryQuery, setShowArchivedSessions,
    setSessionTitleMap, setDeletedSessionIds, setLocalDraftSessionIds, setOpenSessionMenuId, setRenameDialogSessionId,
    setArchiveDialogSessionId, setSessionLoading, setSessionError, setSessionCursor, setSessionHasMore, setActiveSessionId,
    setViewStateUpdatedAt,
  } = session
  const [apiBase, setApiBase] = useState(() => safeLocalStorageGetItem('apiBaseTeacher') || DEFAULT_API_URL)
  const [messages, setMessages] = useState<Message[]>(() => [
    {
      id: makeId(),
      role: 'assistant',
      content: TEACHER_GREETING,
      time: nowTime(),
    },
  ])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [sessionSidebarOpen, setSessionSidebarOpen] = useState(() => safeLocalStorageGetItem('teacherSessionSidebarOpen') !== 'false')
  const [skillsOpen, setSkillsOpen] = useState(() => safeLocalStorageGetItem('teacherSkillsOpen') !== 'false')
  const [mobileTab, setMobileTab] = useState<'chat' | 'sessions' | 'workbench'>('chat')
  const [workbenchTab, setWorkbenchTab] = useState<WorkbenchTab>(() => {
    const raw = safeLocalStorageGetItem('teacherWorkbenchTab')
    return raw === 'memory' || raw === 'workflow' ? raw : 'skills'
  })
  const [activeSkillId, setActiveSkillId] = useState(() => safeLocalStorageGetItem('teacherActiveSkillId') || 'physics-teacher-ops')
  const [skillPinned, setSkillPinned] = useState(() => safeLocalStorageGetItem('teacherSkillPinned') === 'true')
  const [cursorPos, setCursorPos] = useState(0)
  const [skillQuery, setSkillQuery] = useState('')
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false)
  const [favorites, setFavorites] = useState<string[]>(() => {
    try {
      return JSON.parse(safeLocalStorageGetItem('teacherSkillFavorites') || '[]')
    } catch {
      return []
    }
  })
  const [skillList, setSkillList] = useState<Skill[]>(fallbackSkills)
  const [skillsLoading, setSkillsLoading] = useState(false)
  const [skillsError, setSkillsError] = useState('')
  const [composerWarning, setComposerWarning] = useState('')
  const [chatQueueHint, setChatQueueHint] = useState('')
  const [pendingStreamStage, setPendingStreamStage] = useState('')
  const [pendingToolRuns, setPendingToolRuns] = useState<PendingToolRun[]>([])
  const PENDING_CHAT_KEY = 'teacherPendingChatJob'
  const [pendingChatJob, setPendingChatJob] = useState<PendingChatJob | null>(() =>
    parsePendingChatJob(safeLocalStorageGetItem(PENDING_CHAT_KEY)),
  )
  const [topbarHeight, setTopbarHeight] = useState(64)

  const appRef = useRef<HTMLDivElement | null>(null)
  const inputRef = useRef<HTMLTextAreaElement | null>(null)
  const topbarRef = useRef<HTMLElement | null>(null)

  const {
    messagesRef,
    showScrollToBottom,
    enableAutoScroll,
    handleMessagesScroll,
    scrollMessagesToBottom,
  } = useChatScroll({
    activeSessionId,
    messages,
    sending,
  })

  const {
    updateExamDraftMeta,
    updateExamQuestionField,
    updateExamAnswerKeyText,
    updateExamScoreSchemaSelectedCandidate,
  } = useDraftMutations({ uploadDraft, setUploadDraft: workbench.setUploadDraft, examDraft, setExamDraft: workbench.setExamDraft })

  const { setWheelScrollZone } = useWheelScrollZone({
    appRef, sessionSidebarOpen, skillsOpen,
  })

  const chooseSkill = (skillId: string, pinned = true) => {
    setActiveSkillId(skillId)
    setSkillPinned(pinned)
  }

  const attachmentTeacherId = String(readTeacherAuthSubject()?.teacher_id || '').trim()
  const teacherAnalysisWorkbenchEnabled = useMemo(() => {
    const source: Record<string, string | undefined> = {
      teacherAnalysisWorkbench: import.meta.env.VITE_TEACHER_ANALYSIS_WORKBENCH,
      teacherSurveyAnalysis: import.meta.env.VITE_TEACHER_SURVEY_ANALYSIS,
    }
    if (typeof window !== 'undefined') {
      try {
        const analysisOverride = window.localStorage.getItem('teacherAnalysisWorkbench')
        const surveyOverride = window.localStorage.getItem('teacherSurveyAnalysis')
        if (analysisOverride != null) source.teacherAnalysisWorkbench = analysisOverride
        if (surveyOverride != null) source.teacherSurveyAnalysis = surveyOverride
      } catch {
        // ignore localStorage read failures
      }
    }
    return readTeacherAnalysisWorkbenchFlag(source)
  }, [])
  const teacherAnalysisWorkbenchShadowMode = useMemo(() => {
    const source: Record<string, string | undefined> = {
      teacherAnalysisWorkbenchShadow: import.meta.env.VITE_TEACHER_ANALYSIS_WORKBENCH_SHADOW,
      teacherSurveyAnalysisShadow: import.meta.env.VITE_TEACHER_SURVEY_ANALYSIS_SHADOW,
    }
    if (typeof window !== 'undefined') {
      try {
        const analysisOverride = window.localStorage.getItem('teacherAnalysisWorkbenchShadow')
        const surveyOverride = window.localStorage.getItem('teacherSurveyAnalysisShadow')
        if (analysisOverride != null) source.teacherAnalysisWorkbenchShadow = analysisOverride
        if (surveyOverride != null) source.teacherSurveyAnalysisShadow = surveyOverride
      } catch {
        // ignore localStorage read failures
      }
    }
    return readTeacherAnalysisWorkbenchShadowFlag(source)
  }, [])
  const {
    analysisReports,
    analysisReportsLoading,
    analysisReportsError,
    selectedAnalysisReportId,
    selectedAnalysisReport,
    analysisReviewQueue,
    analysisDomainFilter,
    analysisStatusFilter,
    analysisStrategyFilter,
    analysisTargetTypeFilter,
    setAnalysisDomainFilter,
    setAnalysisStatusFilter,
    setAnalysisStrategyFilter,
    setAnalysisTargetTypeFilter,
    refreshAnalysisReports,
    selectAnalysisReport,
    rerunAnalysisReport,
  } = useAnalysisReports({
    apiBase,
    teacherId: attachmentTeacherId,
    enabled: teacherAnalysisWorkbenchEnabled,
  })
  const selectedAnalysisTarget = useMemo(
    () => selectedAnalysisReport?.report || analysisReports.find((item) => item.report_id === selectedAnalysisReportId) || null,
    [analysisReports, selectedAnalysisReport, selectedAnalysisReportId],
  )

  const {
    refreshTeacherSessions, loadTeacherSessionMessages,
    refreshMemoryProposals, refreshMemoryInsights, deleteMemoryProposal,
    refreshStudentMemoryProposals, refreshStudentMemoryInsights, reviewStudentMemoryProposal, deleteStudentMemoryProposal,
    submitMessage, fetchSkills, renderedMessages,
    activeSessionRef, sessionRequestRef,
    historyCursorRef, historyHasMoreRef, localDraftSessionIdsRef,
    pendingChatJobRef, markdownCacheRef,
  } = useTeacherChatApi({
    apiBase, activeSessionId, messages, activeSkillId, skillPinned, skillList,
    pendingChatJob, memoryStatusFilter, studentMemoryStatusFilter, studentMemoryStudentFilter, skillsOpen, workbenchTab,
    selectedAnalysisTarget,
    setMessages, setSending, setActiveSessionId, setPendingChatJob, setChatQueueHint,
    setPendingStreamStage, setPendingToolRuns,
    setComposerWarning, setInput,
    setHistorySessions, setHistoryLoading, setHistoryError, setHistoryCursor, setHistoryHasMore,
    setLocalDraftSessionIds, setSessionLoading, setSessionError, setSessionCursor, setSessionHasMore,
    setProposalLoading, setProposalError, setProposals, setMemoryInsights,
    setStudentProposalLoading, setStudentProposalError, setStudentProposals, setStudentMemoryInsights,
    setSkillList, setSkillsLoading, setSkillsError,
    chooseSkill, enableAutoScroll, setWheelScrollZone,
  })

  useLocalStorageSync({
    apiBase, favorites, skillsOpen, workbenchTab, sessionSidebarOpen,
    activeSkillId, skillPinned, localDraftSessionIds, activeSessionId, uploadMode,
    pendingChatJob, pendingChatKey: PENDING_CHAT_KEY,
    activeSessionRef, historyCursorRef, historyHasMoreRef, localDraftSessionIdsRef, pendingChatJobRef,
    historyCursor, historyHasMore,
    topbarRef, setTopbarHeight, setViewportWidth,
    openSessionMenuId, setOpenSessionMenuId,
    inputRef, input,
    composerWarning, setComposerWarning,
    uploadError, uploadCardCollapsed, setUploadCardCollapsed,
    examUploadError,
    draftError, draftActionError, draftPanelCollapsed, setDraftPanelCollapsed,
    examDraftError, examDraftActionError, examDraftPanelCollapsed, setExamDraftPanelCollapsed,
    markdownCacheRef,
  })

  const {
    handleUploadAssignment, saveDraft, handleConfirmUpload,
    fetchAssignmentProgress, refreshWorkflowWorkbench, scrollToWorkflowSection,
    assignmentWorkflowIndicator, updateDraftRequirement, updateDraftQuestion,
  } = useAssignmentWorkflow({
    apiBase,
    uploadMode, uploadAssignmentId, uploadDate, uploadScope, uploadClassName, uploadStudentIds,
    uploadFiles, uploadAnswerFiles, uploading, uploadStatus, uploadError, uploadCardCollapsed,
    uploadJobId, uploadJobInfo, uploadConfirming, uploadStatusPollNonce,
    uploadDraft, draftPanelCollapsed, draftLoading, draftError, questionShowCount,
    draftSaving, draftActionStatus, draftActionError, misconceptionsText, misconceptionsDirty,
    progressPanelCollapsed, progressAssignmentId, progressLoading, progressError, progressData, progressOnlyIncomplete,
    examStatusPollNonce,
    setUploadError, setUploadStatus, setUploadJobId, setUploadJobInfo, setUploadDraft,
    setUploadFiles, setUploadAnswerFiles, setUploading, setUploadCardCollapsed, setUploadConfirming,
    setUploadStatusPollNonce, setDraftPanelCollapsed, setDraftLoading, setDraftError,
    setQuestionShowCount, setDraftSaving, setDraftActionStatus, setDraftActionError,
    setMisconceptionsText, setMisconceptionsDirty,
    setProgressPanelCollapsed, setProgressAssignmentId, setProgressLoading, setProgressError, setProgressData,
    setExamStatusPollNonce,
  })

  useEffect(() => {
    const sid = String(pendingChatJob?.session_id || '').trim()
    if (!sid || sid === 'main') return
    setLocalDraftSessionIds((prev) => (prev.includes(sid) ? prev : [sid, ...prev]))
  }, [pendingChatJob?.session_id, setLocalDraftSessionIds])

  useTeacherSessionViewStateSync({
    apiBase,
    activeSessionId,
    sessionTitleMap,
    deletedSessionIds,
    viewStateUpdatedAt,
    setSessionTitleMap,
    setDeletedSessionIds,
    setViewStateUpdatedAt,
    initialState: initialViewStateRef.current,
  })

  useEffect(() => {
    // Refresh recovery: resume polling for the last active upload job.
    const raw = safeLocalStorageGetItem('teacherActiveUpload')
    if (!raw) return
    try {
      const data = JSON.parse(raw)
      if (data?.type === 'assignment' && data?.job_id) {
        setUploadMode('assignment')
        setUploadJobId(String(data.job_id))
      } else if (data?.type === 'exam' && data?.job_id) {
        setUploadMode('exam')
        setExamJobId(String(data.job_id))
      }
    } catch {
      // ignore
    }
  }, [setExamJobId, setUploadJobId, setUploadMode])

  useEffect(() => {
    if (pendingChatJob) safeLocalStorageSetItem(PENDING_CHAT_KEY, JSON.stringify(pendingChatJob))
    else safeLocalStorageRemoveItem(PENDING_CHAT_KEY)
  }, [pendingChatJob, PENDING_CHAT_KEY])

  useEffect(() => {
    if (pendingChatJob?.job_id) return
    setPendingStreamStage('')
    setPendingToolRuns([])
  }, [pendingChatJob?.job_id])

  useEffect(() => {
    if (!pendingChatJob?.job_id) return
    if (!activeSessionId || pendingChatJob.session_id !== activeSessionId) return
    setMessages((prev) => withPendingChatOverlay(prev, pendingChatJob, activeSessionId))
  }, [
    activeSessionId,
    pendingChatJob,
    pendingChatJob?.created_at,
    pendingChatJob?.job_id,
    pendingChatJob?.placeholder_id,
    pendingChatJob?.session_id,
    pendingChatJob?.user_text,
  ])

  useEffect(() => {
    if (!pendingChatJob?.job_id) return
    if (pendingChatJob.session_id && pendingChatJob.session_id !== activeSessionId) {
      setActiveSessionId(pendingChatJob.session_id)
    }
    // Run only on mount to recover the original pending session once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])


  useAssignmentUploadStatusPolling({
    apiBase,
    uploadJobId,
    uploadStatusPollNonce,
    formatUploadJobStatus,
    setUploadError,
    setUploadJobInfo,
    setUploadStatus,
  })

  useExamUploadStatusPolling({
    apiBase,
    examJobId,
    examStatusPollNonce,
    formatExamJobStatus,
    setExamJobInfo,
    setExamUploadError,
    setExamUploadStatus,
  })

  const examWorkflowIndicator = useMemo<WorkflowIndicator>(() => {
    return buildExamWorkflowIndicator({
      examJobId,
      examJobInfoStatus: examJobInfo?.status,
      examUploading,
      examConfirming,
      examDraft,
      examUploadError,
      examDraftError,
      examDraftActionError,
    })
  }, [examConfirming, examDraft, examDraftActionError, examDraftError, examJobId, examJobInfo?.status, examUploadError, examUploading])

  const activeWorkflowIndicator = uploadMode === 'assignment' ? assignmentWorkflowIndicator : examWorkflowIndicator

  const examWorkflowAutoState = useMemo(() => {
    const stepState = (key: string) => examWorkflowIndicator.steps.find((s) => s.key === key)?.state || 'todo'
    const uploadStep = stepState('upload')
    const parseStep = stepState('parse')
    const reviewStep = stepState('review')
    const confirmStep = stepState('confirm')
    if (parseStep === 'error') return 'parse-error'
    if (reviewStep === 'error') return 'review-error'
    if (confirmStep === 'error') return 'confirm-error'
    if (confirmStep === 'done') return 'confirmed'
    if (confirmStep === 'active') return 'confirming'
    if (reviewStep === 'active') return 'review'
    if (parseStep === 'active') return 'parsing'
    if (uploadStep === 'active') return 'uploading'
    return 'idle'
  }, [examWorkflowIndicator])

  const {
    handleUploadExam, saveExamDraft, handleConfirmExamUpload,
  } = useExamWorkflow({
    apiBase,
    examId, examDate, examClassName,
    examPaperFiles, examScoreFiles, examAnswerFiles,
    examUploading, examUploadError,
    examJobId, examJobInfo, examDraft,
    examDraftPanelCollapsed, examDraftError, examDraftActionError,
    examDraftSaving, examConfirming, examStatusPollNonce,
    uploadCardCollapsed, uploadMode, examWorkflowAutoState,
    setExamUploadError, setExamUploadStatus,
    setExamJobId, setExamJobInfo, setExamDraft,
    setExamDraftPanelCollapsed, setExamDraftLoading, setExamDraftError,
    setExamDraftSaving, setExamDraftActionStatus, setExamDraftActionError,
    setExamUploading, setExamConfirming,
    setExamPaperFiles, setExamScoreFiles, setExamAnswerFiles,
    setUploadCardCollapsed,
    setExamStatusPollNonce,
  })

  const {
    attachments,
    addFiles,
    removeAttachment,
    clearReadyAttachments,
    readyAttachmentRefs,
    hasSendableAttachments,
    uploading: uploadingAttachments,
  } = useChatAttachments({
    apiBase,
    role: 'teacher',
    sessionId: activeSessionId || 'main',
    teacherId: attachmentTeacherId,
  })

  const {
    mention,
    mentionIndex,
    filteredSkills,
    stopKeyPropagation,
    insertPrompt,
    insertInvocationTokenAtCursor,
    insertMention,
    toggleFavorite,
    handleSend,
    handleKeyDown,
  } = useTeacherComposerInteractions({
    input,
    setInput,
    cursorPos,
    setCursorPos,
    inputRef,
    skillList,
    skillQuery,
    showFavoritesOnly,
    favorites,
    activeSkillId,
    setActiveSkillId,
    setSkillPinned,
    chooseSkill,
    setFavorites,
    submitMessage,
    getAttachmentRefs: () => readyAttachmentRefs,
    hasSendableAttachments,
    onSendSuccess: clearReadyAttachments,
    pendingChatJob,
    sending,
  })

  const {
    visibleHistorySessions,
    groupedHistorySessions,
    getSessionTitle,
    archiveDialogIsArchived,
    archiveDialogActionLabel,
  } = useTeacherSessionSidebarModel({
    historySessions,
    deletedSessionIds,
    historyQuery,
    sessionTitleMap,
    showArchivedSessions,
    archiveDialogSessionId,
  })

  const isMobileViewport = useCallback(() => {
    if (typeof window === 'undefined') return false
    return window.matchMedia('(max-width: 900px)').matches
  }, [])

  const {
    startNewTeacherSession, renameSession, toggleSessionMenu,
    toggleSessionArchive,
    cancelRenameDialog, confirmRenameDialog,
    cancelArchiveDialog, confirmArchiveDialog,
    closeSessionSidebarOnMobile, toggleSessionSidebar,
  } = useSessionActions({
    sessionRequestRef, visibleHistorySessions,
    activeSessionId, renameDialogSessionId, archiveDialogSessionId, deletedSessionIds,
    setLocalDraftSessionIds, setShowArchivedSessions, setActiveSessionId,
    setSessionCursor, setSessionHasMore, setSessionError, setOpenSessionMenuId,
    setPendingChatJob, setSending, setInput, setChatQueueHint,
    setHistorySessions, setMessages, setRenameDialogSessionId, setArchiveDialogSessionId,
    setSessionTitleMap, setDeletedSessionIds, setSessionSidebarOpen, setSkillsOpen,
    isMobileViewport,
  })

  const {
    toggleSkillsWorkbench,
    requestCloseSettings,
    toggleSettingsPanel,
    openModelSettingsPanel,
  } = useTeacherUiPanels({
    skillsOpen,
    setSkillsOpen,
    setSessionSidebarOpen,
    isMobileViewport,
    settingsOpen,
    setSettingsOpen,
  })

  useEffect(() => {
    if (!teacherUseMobileShellV2) return
    const nextPanels = teacherMobilePanelsFromTab(mobileTab)
    if (sessionSidebarOpen !== nextPanels.sessionSidebarOpen) setSessionSidebarOpen(nextPanels.sessionSidebarOpen)
    if (skillsOpen !== nextPanels.skillsOpen) setSkillsOpen(nextPanels.skillsOpen)
  }, [teacherUseMobileShellV2, mobileTab, sessionSidebarOpen, skillsOpen, setSessionSidebarOpen, setSkillsOpen])

  const handleTeacherMobileTabChange = useCallback((tabId: string) => {
    if (!isTeacherMobileTab(tabId)) return
    setMobileTab(tabId)
  }, [])

  const handleSelectSessionFromSheet = useCallback((sessionId: string) => {
    const sid = String(sessionId || '').trim()
    if (!sid) return
    setActiveSessionId(sid)
    setSessionCursor(-1)
    setSessionHasMore(false)
    setSessionError('')
    setOpenSessionMenuId('')
    setMobileTab('chat')
  }, [
    setActiveSessionId,
    setSessionCursor,
    setSessionHasMore,
    setSessionError,
    setOpenSessionMenuId,
  ])

  const handleTopbarSessionToggle = useCallback(() => {
    if (!teacherUseMobileShellV2) {
      toggleSessionSidebar()
      return
    }
    setMobileTab((prev) => (prev === 'sessions' ? 'chat' : 'sessions'))
  }, [teacherUseMobileShellV2, toggleSessionSidebar])

  const handleTopbarWorkbenchToggle = useCallback(() => {
    if (!teacherUseMobileShellV2) {
      toggleSkillsWorkbench()
      return
    }
    setMobileTab((prev) => (prev === 'workbench' ? 'chat' : 'workbench'))
  }, [teacherUseMobileShellV2, toggleSkillsWorkbench])

  const {
    isWorkbenchResizing,
    startWorkbenchResize,
    handleWorkbenchResizeReset,
  } = useTeacherWorkbenchPanelControls({
    workbenchPanelRef,
    skillsOpen,
    setSkillsOpen,
    isMobileLayout,
    workbenchMaxWidth,
    workbenchMinWidth: WORKBENCH_MIN_WIDTH,
    defaultWorkbenchWidth: WORKBENCH_DEFAULT_WIDTH,
  })

  const teacherWorkbenchViewModel = buildTeacherWorkbenchViewModel({
    workbench,
    skillsOpen,
    setSkillsOpen,
    workbenchTab,
    setWorkbenchTab,
    apiBase,
    activeSkillId,
    activeWorkflowIndicator,
    chooseSkill,
    difficultyLabel,
    difficultyOptions,
    favorites,
    fetchAssignmentProgress,
    fetchSkills,
    filteredSkills,
    formatDraftSummary,
    formatExamDraftSummary,
    formatExamJobSummary,
    formatMissingRequirements,
    formatProgressSummary,
    formatUploadJobSummary,
    handleConfirmExamUpload,
    handleConfirmUpload,
    handleUploadAssignment,
    handleUploadExam,
    insertInvocationTokenAtCursor,
    insertPrompt,
    normalizeDifficulty,
    parseCommaList,
    parseLineList,
    refreshMemoryInsights,
    refreshMemoryProposals,
    refreshStudentMemoryInsights,
    refreshStudentMemoryProposals,
    onDeleteProposal: deleteMemoryProposal,
    onReviewStudentProposal: reviewStudentMemoryProposal,
    onDeleteStudentProposal: deleteStudentMemoryProposal,
    refreshWorkflowWorkbench: () => {
      refreshWorkflowWorkbench()
      void refreshAnalysisReports()
    },
    saveDraft,
    saveExamDraft,
    scrollToWorkflowSection,
    setComposerWarning,
    setShowFavoritesOnly,
    setSkillPinned,
    setSkillQuery,
    showFavoritesOnly,
    skillPinned,
    skillQuery,
    skillsError,
    skillsLoading,
    stopKeyPropagation,
    toggleFavorite,
    updateDraftQuestion,
    updateDraftRequirement,
    updateExamAnswerKeyText,
    updateExamDraftMeta,
    updateExamScoreSchemaSelectedCandidate,
    updateExamQuestionField,
    analysisFeatureEnabled: teacherAnalysisWorkbenchEnabled,
    videoHomeworkFeatureEnabled: teacherAnalysisWorkbenchEnabled,
    analysisFeatureShadowMode: teacherAnalysisWorkbenchShadowMode,
    analysisReports,
    analysisReportsLoading,
    analysisReportsError,
    selectedAnalysisReportId,
    selectedAnalysisReport,
    analysisReviewQueue,
    analysisDomainFilter,
    analysisStatusFilter,
    analysisStrategyFilter,
    analysisTargetTypeFilter,
    setAnalysisDomainFilter,
    setAnalysisStatusFilter,
    setAnalysisStrategyFilter,
    setAnalysisTargetTypeFilter,
    refreshAnalysisReports,
    selectAnalysisReport,
    rerunAnalysisReport,
  })


  const appStyle: CSSProperties & Record<'--teacher-topbar-height', string> = {
    '--teacher-topbar-height': `${topbarHeight}px`,
    overscrollBehavior: 'none',
  }

  return (
    <div
      ref={appRef}
      className={`app teacher h-dvh flex flex-col bg-bg overflow-hidden ${teacherUseMobileShellV2 ? 'teacher-mobile-shell-v2' : ''}`.trim()}
      style={appStyle}
      data-mobile-shell-v2={mobileShellV2Enabled ? '1' : '0'}
    >
      <TeacherTopbar
        topbarRef={topbarRef}
        sessionSidebarOpen={sessionSidebarOpen}
        skillsOpen={skillsOpen}
        compactMobile={teacherUseMobileShellV2}
        onToggleSessionSidebar={handleTopbarSessionToggle}
        onOpenModelSettingsPanel={openModelSettingsPanel}
        onToggleSkillsWorkbench={handleTopbarWorkbenchToggle}
        onToggleSettingsPanel={toggleSettingsPanel}
      />

      <TeacherSettingsPanel
        open={settingsOpen}
        onClose={requestCloseSettings}
        apiBase={apiBase}
        onApiBaseChange={setApiBase}
      />

      <div
        className={`teacher-layout flex-1 min-h-0 grid relative bg-surface overflow-hidden ${
          teacherUseMobileShellV2
            ? 'grid-cols-[minmax(0,1fr)]'
            : sessionSidebarOpen
              ? 'grid-cols-[300px_minmax(0,1fr)] max-[900px]:grid-cols-[minmax(0,1fr)]'
              : 'grid-cols-[0_minmax(0,1fr)]'
        }`}
        style={{ overscrollBehavior: 'none' }}
      >
        {teacherUseMobileShellV2 ? null : (
          <TeacherSessionRail
            sessionSidebarOpen={sessionSidebarOpen}
            skillsOpen={skillsOpen}
            setSessionSidebarOpen={setSessionSidebarOpen}
            setSkillsOpen={setSkillsOpen}
            setActiveSessionId={setActiveSessionId}
            setSessionCursor={setSessionCursor}
            setSessionHasMore={setSessionHasMore}
            setSessionError={setSessionError}
            setOpenSessionMenuId={setOpenSessionMenuId}
            closeSessionSidebarOnMobile={closeSessionSidebarOnMobile}
            historyQuery={historyQuery}
            historyLoading={historyLoading}
            historyError={historyError}
            showArchivedSessions={showArchivedSessions}
            visibleHistoryCount={visibleHistorySessions.length}
            groupedHistorySessions={groupedHistorySessions}
            activeSessionId={activeSessionId}
            openSessionMenuId={openSessionMenuId}
            deletedSessionIds={deletedSessionIds}
            historyHasMore={historyHasMore}
            sessionHasMore={sessionHasMore}
            sessionLoading={sessionLoading}
            sessionError={sessionError}
            onStartNewSession={startNewTeacherSession}
            onRefreshSessions={(mode) => void refreshTeacherSessions(mode)}
            onToggleArchived={() => setShowArchivedSessions((prev) => !prev)}
            onHistoryQueryChange={setHistoryQuery}
            onToggleSessionMenu={toggleSessionMenu}
            onRenameSession={renameSession}
            onToggleSessionArchive={toggleSessionArchive}
            onLoadOlderMessages={() => void loadTeacherSessionMessages(activeSessionId, sessionCursor, true)}
            getSessionTitle={getSessionTitle}
            formatSessionUpdatedLabel={formatSessionUpdatedLabel}
          />
        )}

        <div className="min-w-0 min-h-0 flex overflow-hidden">
          <Group
            orientation="horizontal"
            disabled={isMobileLayout}
            className={`w-full h-full min-w-0 min-h-0 ${isWorkbenchResizing ? 'dragging' : ''}`}
          >
            <Panel
              className="min-w-0 min-h-0 overflow-hidden flex"
              minSize={isMobileLayout ? 0 : 360}
            >
              <TeacherChatMainContent
                renderedMessages={renderedMessages}
                sending={sending}
                hasPendingChatJob={Boolean(pendingChatJob?.job_id)}
                typingTimeLabel={nowTime()}
                messagesRef={messagesRef}
                onMessagesScroll={handleMessagesScroll}
                showScrollToBottom={showScrollToBottom}
                onScrollToBottom={() => scrollMessagesToBottom('smooth')}
                activeSkillId={activeSkillId}
                skillPinned={skillPinned}
                input={input}
                chatQueueHint={chatQueueHint}
                pendingStreamStage={pendingStreamStage}
                pendingToolRuns={pendingToolRuns}
                composerWarning={composerWarning}
                attachments={attachments}
                uploadingAttachments={uploadingAttachments}
                hasSendableAttachments={hasSendableAttachments}
                inputRef={inputRef}
                onSubmit={handleSend}
                onInputChange={(value, selectionStart) => {
                  setInput(value)
                  setCursorPos(selectionStart)
                }}
                onInputClick={(selectionStart) => setCursorPos(selectionStart)}
                onInputKeyUp={(selectionStart) => setCursorPos(selectionStart)}
                onInputKeyDown={handleKeyDown}
                onPickFiles={addFiles}
                onRemoveAttachment={removeAttachment}
                mention={mention}
                mentionIndex={mentionIndex}
                onInsertMention={insertMention}
              />
            </Panel>
            {teacherUseMobileShellV2 ? null : (
              <>
                <Separator
                  className={`group w-2 cursor-col-resize flex items-center justify-center bg-transparent transition-[background] duration-150 ease-in-out shrink-0 hover:bg-[rgba(16,163,127,0.08)] ${isWorkbenchResizing ? 'bg-[rgba(16,163,127,0.08)]' : ''} ${!skillsOpen ? 'cursor-default pointer-events-none' : ''}`}
                  onPointerDown={startWorkbenchResize}
                  onDoubleClick={handleWorkbenchResizeReset}
                >
                  <span className={`w-[3px] h-7 rounded-sm transition-[background] duration-150 ease-in-out ${isWorkbenchResizing ? 'bg-[#10a37f]' : 'bg-[#d1d5db] group-hover:bg-[#10a37f]'}`} />
                </Separator>
                <Panel
                  panelRef={workbenchPanelRef}
                  className="min-w-0 min-h-0 overflow-hidden flex"
                  minSize={WORKBENCH_MIN_WIDTH}
                  maxSize={workbenchMaxWidth}
                  defaultSize={initialWorkbenchWidth}
                  collapsible
                  collapsedSize={0}
                  onResize={(panelSize) => {
                    if (isMobileLayout) return
                    const width = Math.round(panelSize.inPixels || 0)
                    if (!Number.isFinite(width) || width <= 0) return
                    const clamped = Math.min(workbenchMaxWidth, Math.max(WORKBENCH_MIN_WIDTH, width))
                    try {
                      window.localStorage.setItem('teacherWorkbenchWidth', String(clamped))
                    } catch {
                      // ignore
                    }
                  }}
                >
                  <TeacherWorkbench viewModel={teacherWorkbenchViewModel} />
                </Panel>
              </>
            )}
          </Group>
        </div>
      </div>

      <BottomSheet
        open={teacherUseMobileShellV2 && mobileTab === 'sessions'}
        onClose={() => {
          setMobileTab('chat')
        }}
        title="历史会话"
      >
        <SessionSidebar
          mobilePresentation="sheet"
          open
          historyQuery={historyQuery}
          historyLoading={historyLoading}
          historyError={historyError}
          showArchivedSessions={showArchivedSessions}
          visibleHistoryCount={visibleHistorySessions.length}
          groupedHistorySessions={groupedHistorySessions}
          activeSessionId={activeSessionId}
          openSessionMenuId={openSessionMenuId}
          deletedSessionIds={deletedSessionIds}
          historyHasMore={historyHasMore}
          sessionHasMore={sessionHasMore}
          sessionLoading={sessionLoading}
          sessionError={sessionError}
          onStartNewSession={startNewTeacherSession}
          onRefreshSessions={(mode) => void refreshTeacherSessions(mode)}
          onToggleArchived={() => setShowArchivedSessions((prev) => !prev)}
          onHistoryQueryChange={setHistoryQuery}
          onSelectSession={handleSelectSessionFromSheet}
          onToggleSessionMenu={toggleSessionMenu}
          onRenameSession={renameSession}
          onToggleSessionArchive={toggleSessionArchive}
          onLoadOlderMessages={() => void loadTeacherSessionMessages(activeSessionId, sessionCursor, true)}
          getSessionTitle={getSessionTitle}
          formatSessionUpdatedLabel={formatSessionUpdatedLabel}
        />
      </BottomSheet>

      <BottomSheet
        open={teacherUseMobileShellV2 && mobileTab === 'workbench'}
        onClose={() => {
          setMobileTab('chat')
        }}
        title="工作台"
      >
        <TeacherWorkbench viewModel={teacherWorkbenchViewModel} />
      </BottomSheet>

      {teacherUseMobileShellV2 ? (
        <MobileTabBar
          items={TEACHER_MOBILE_TAB_ITEMS}
          activeId={mobileTab}
          onChange={handleTeacherMobileTabChange}
          ariaLabel="教师端移动导航"
        />
      ) : null}

      <PromptDialog
        open={Boolean(renameDialogSessionId)}
        title="重命名会话"
        description="可留空以删除自定义名称。"
        label="会话名称"
        placeholder="输入会话名称"
        defaultValue={renameDialogSessionId ? getSessionTitle(renameDialogSessionId) : ''}
        confirmText="保存"
        onCancel={cancelRenameDialog}
        onConfirm={confirmRenameDialog}
      />
      <ConfirmDialog
        open={Boolean(archiveDialogSessionId)}
        title={`确认${archiveDialogActionLabel}会话？`}
        description={archiveDialogSessionId ? `会话：${getSessionTitle(archiveDialogSessionId)}` : undefined}
        confirmText={archiveDialogActionLabel}
        confirmTone={archiveDialogIsArchived ? 'primary' : 'danger'}
        cancelText="取消"
        onCancel={cancelArchiveDialog}
        onConfirm={confirmArchiveDialog}
      />
    </div>
  )
}
