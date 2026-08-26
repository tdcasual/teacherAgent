import { useEffect, useMemo, useRef, useState } from 'react'
import type { PanelImperativeHandle } from 'react-resizable-panels'
import TeacherTaskStrip from './features/layout/TeacherTaskStrip'
import TeacherAppLayout from './features/layout/TeacherAppLayout'
import { useChatScroll } from './features/chat/useChatScroll'
import { readTeacherLocalViewState, type SessionViewStatePayload } from './features/chat/viewState'
import { useTeacherSessionViewStateSync } from './features/chat/useTeacherSessionViewStateSync'
import { fallbackSkills, TEACHER_GREETING } from './features/chat/catalog'
import { buildTeacherWorkbenchViewModel } from './features/workbench/teacherWorkbenchViewModel'
import { useAssignmentUploadStatusPolling } from './features/workbench/useAssignmentUploadStatusPolling'
import { useExamUploadStatusPolling } from './features/workbench/useExamUploadStatusPolling'
import { useTeacherWorkbenchPanelControls } from './features/workbench/useTeacherWorkbenchPanelControls'
import { formatDraftSummary, formatExamDraftSummary, formatExamJobStatus, formatExamJobSummary, formatProgressSummary, formatUploadJobStatus, formatUploadJobSummary } from './features/workbench/workbenchFormatters'
import { buildTeacherWorkflowGuidance, buildExamWorkflowIndicator, findActiveWorkflowStep } from './features/workbench/workflowIndicators'
import { difficultyLabel, difficultyOptions, formatMissingRequirements, normalizeDifficulty, parseCommaList, parseLineList } from './features/workbench/workbenchUtils'
import { resolveRuntimeApiBase } from '../../shared/apiBase'
import { readTeacherAnalysisWorkbenchFlag, readTeacherAnalysisWorkbenchShadowFlag } from '../../shared/featureFlags'
import { TeacherToolConfirmDialog } from './features/chat/TeacherToolConfirmDialog'
import { useChatAttachments } from '../../shared/useChatAttachments'
import { safeLocalStorageGetItem } from './utils/storage'
import { makeId } from './utils/id'
import { nowTime } from './utils/time'
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
import { useTeacherPendingChatJob } from './features/chat/useTeacherPendingChatJob'
import { useTeacherSessionState } from './features/state/useTeacherSessionState'
import { readTeacherAuthSubject } from './features/auth/teacherAuth'
import { useTeacherMobileShell } from './features/layout/useTeacherMobileShell'
import type { Message, PendingToolRun, Skill, WorkbenchTab, WorkflowIndicator } from './appTypes'
import { WORKBENCH_DEFAULT_WIDTH, WORKBENCH_MIN_WIDTH, workbenchMaxWidthForViewport } from './teacherAppChrome'

export default function App() {
  const initialViewStateRef = useRef<SessionViewStatePayload>(readTeacherLocalViewState())
  const workbenchPanelRef = useRef<PanelImperativeHandle | null>(null)
  const workbench = useTeacherWorkbenchState()
  const session = useTeacherSessionState(initialViewStateRef.current)
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
    examDraftActionError, examConfirming, executionTimeline,
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
    setExamDraftActionError, setExamConfirming, setExecutionTimeline,
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
  const [apiBase, setApiBase] = useState(() => resolveRuntimeApiBase(safeLocalStorageGetItem('apiBaseTeacher')))
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
  const [topbarHeight, setTopbarHeight] = useState(64)
  const { pendingChatJob, setPendingChatJob, pendingChatKey } = useTeacherPendingChatJob({
    activeSessionId,
    setActiveSessionId,
    setLocalDraftSessionIds,
    setMessages,
    setPendingStreamStage,
    setPendingToolRuns,
  })
  const {
    setViewportWidth,
    isMobileLayout,
    workbenchMaxWidth,
    mobileShellV2Enabled,
    teacherUseMobileShellV2,
    mobileTab,
    setMobileTab,
    isMobileViewport,
    handleTeacherMobileTabChange,
    handleSelectSessionFromSheet,
    handleTopbarSessionToggle,
    handleTopbarWorkbenchToggle,
  } = useTeacherMobileShell({
    sessionSidebarOpen,
    skillsOpen,
    setSessionSidebarOpen,
    setSkillsOpen,
    setActiveSessionId,
    setSessionCursor,
    setSessionHasMore,
    setSessionError,
    setOpenSessionMenuId,
  })
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
    analysisReportsSummary,
    analysisReviewSummary,
    analysisOpsSnapshot,
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
    rerunAnalysisReportsBulk,
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
    submitMessage, fetchSkills, renderedMessages, toolConfirm, confirmToolWrite, cancelToolConfirm,
    activeSessionRef, sessionRequestRef,
    historyCursorRef, historyHasMoreRef, localDraftSessionIdsRef,
    pendingChatJobRef, markdownCacheRef,
  } = useTeacherChatApi({
    apiBase, activeSessionId, messages, activeSkillId, skillPinned, skillList,
    pendingChatJob, memoryStatusFilter, studentMemoryStatusFilter, studentMemoryStudentFilter, skillsOpen, workbenchTab,
    selectedAnalysisTarget,
    setMessages, setSending, setActiveSessionId, setPendingChatJob, setChatQueueHint,
    setPendingStreamStage, setPendingToolRuns, setExecutionTimeline,
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
    pendingChatJob, pendingChatKey,
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
  const teacherTaskStrip = useMemo(() => {
    const mode = uploadMode === 'exam' ? 'exam' : 'assignment'
    const summary = mode === 'assignment'
      ? (uploadJobInfo || uploadAssignmentId
        ? formatUploadJobSummary(uploadJobInfo, uploadAssignmentId)
        : progressData
          ? formatProgressSummary(progressData, progressAssignmentId || uploadAssignmentId)
          : '未开始解析 · 等待上传今天的作业资料')
      : (examJobInfo || examId
        ? formatExamJobSummary(examJobInfo, examId)
        : '未开始解析 · 等待上传今天的考试资料')
    const activeStep = findActiveWorkflowStep(activeWorkflowIndicator)
    const guidance = buildTeacherWorkflowGuidance({
      mode,
      tone: activeWorkflowIndicator.tone,
      activeStepKey: activeStep?.key,
      hasExecutionTimeline: executionTimeline.length > 0,
      hasProgressData: Boolean(progressData),
    })
    const handlePrimaryAction = () => {
      setWorkbenchTab('workflow')
      if (!skillsOpen) setSkillsOpen(true)
      if (teacherUseMobileShellV2) setMobileTab('workbench')
      scrollToWorkflowSection(guidance.primaryActionTargetId)
      if (typeof window !== 'undefined') {
        window.requestAnimationFrame(() => scrollToWorkflowSection(guidance.primaryActionTargetId))
        return
      }
    }

    return (
      <TeacherTaskStrip
        mode={mode}
        statusLabel={activeWorkflowIndicator.label}
        tone={activeWorkflowIndicator.tone}
        summary={summary}
        nextStepLabel={guidance.nextStepLabel}
        primaryActionLabel={guidance.primaryActionLabel}
        onPrimaryAction={handlePrimaryAction}
      />
    )
  }, [
    activeWorkflowIndicator,
    examId,
    examJobInfo,
    executionTimeline.length,
    progressAssignmentId,
    progressData,
    scrollToWorkflowSection,
    skillsOpen,
    teacherUseMobileShellV2,
    uploadAssignmentId,
    uploadJobInfo,
    uploadMode,
    setWorkbenchTab,
    setSkillsOpen,
    setMobileTab,
  ])
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
  const {
    startNewTeacherSession, renameSession, toggleSessionMenu,
    toggleSessionArchive,
    cancelRenameDialog, confirmRenameDialog,
    cancelArchiveDialog, confirmArchiveDialog,
    closeSessionSidebarOnMobile,
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
    analysisReportsSummary,
    analysisReviewSummary,
    analysisOpsSnapshot,
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
    rerunAnalysisReportsBulk,
    executionTimeline,
  })
  return (
    <>
    <TeacherAppLayout
      appRef={appRef}
      topbarRef={topbarRef}
      workbenchPanelRef={workbenchPanelRef}
      topbarHeight={topbarHeight}
      teacherUseMobileShellV2={teacherUseMobileShellV2}
      mobileShellV2Enabled={mobileShellV2Enabled}
      sessionSidebarOpen={sessionSidebarOpen}
      skillsOpen={skillsOpen}
      isMobileLayout={isMobileLayout}
      isWorkbenchResizing={isWorkbenchResizing}
      workbenchMaxWidth={workbenchMaxWidth}
      initialWorkbenchWidth={initialWorkbenchWidth}
      mobileTab={mobileTab}
      setMobileTab={setMobileTab}
      settingsOpen={settingsOpen}
      apiBase={apiBase}
      onApiBaseChange={setApiBase}
      onCloseSettings={requestCloseSettings}
      onToggleSessionSidebar={handleTopbarSessionToggle}
      onOpenModelSettingsPanel={openModelSettingsPanel}
      onToggleSkillsWorkbench={handleTopbarWorkbenchToggle}
      onToggleSettingsPanel={toggleSettingsPanel}
      startWorkbenchResize={startWorkbenchResize}
      onWorkbenchResizeReset={handleWorkbenchResizeReset}
      onMobileTabChange={handleTeacherMobileTabChange}
      onSelectSessionFromSheet={handleSelectSessionFromSheet}
      setSessionSidebarOpen={setSessionSidebarOpen}
      setSkillsOpen={setSkillsOpen}
      setActiveSessionId={setActiveSessionId}
      setSessionCursor={setSessionCursor}
      setSessionHasMore={setSessionHasMore}
      setSessionError={setSessionError}
      setOpenSessionMenuId={setOpenSessionMenuId}
      closeSessionSidebarOnMobile={closeSessionSidebarOnMobile}
      taskStrip={teacherTaskStrip}
      workbenchViewModel={teacherWorkbenchViewModel}
      sessionSidebar={{
        historyQuery,
        historyLoading,
        historyError,
        showArchivedSessions,
        visibleHistoryCount: visibleHistorySessions.length,
        groupedHistorySessions,
        activeSessionId,
        openSessionMenuId,
        deletedSessionIds,
        historyHasMore,
        sessionHasMore,
        sessionLoading,
        sessionError,
        onStartNewSession: startNewTeacherSession,
        onRefreshSessions: (mode) => void refreshTeacherSessions(mode),
        onToggleArchived: () => setShowArchivedSessions((prev) => !prev),
        onHistoryQueryChange: setHistoryQuery,
        onToggleSessionMenu: toggleSessionMenu,
        onRenameSession: renameSession,
        onToggleSessionArchive: toggleSessionArchive,
        onLoadOlderMessages: () => void loadTeacherSessionMessages(activeSessionId, sessionCursor, true),
        getSessionTitle,
      }}
      chat={{
        renderedMessages,
        sending,
        hasPendingChatJob: Boolean(pendingChatJob?.job_id),
        typingTimeLabel: nowTime(),
        messagesRef,
        onMessagesScroll: handleMessagesScroll,
        showScrollToBottom,
        onScrollToBottom: () => scrollMessagesToBottom('smooth'),
        activeSkillId,
        skillPinned,
        input,
        chatQueueHint,
        pendingStreamStage,
        pendingToolRuns,
        composerWarning,
        attachments,
        uploadingAttachments,
        hasSendableAttachments,
        inputRef,
        onSubmit: handleSend,
        onInputChange: (value, selectionStart) => {
          setInput(value)
          setCursorPos(selectionStart)
        },
        onInputClick: (selectionStart) => setCursorPos(selectionStart),
        onInputKeyUp: (selectionStart) => setCursorPos(selectionStart),
        onInputKeyDown: handleKeyDown,
        onPickFiles: addFiles,
        onRemoveAttachment: removeAttachment,
        mention,
        mentionIndex,
        onInsertMention: insertMention,
      }}
      renameDialogSessionId={renameDialogSessionId}
      archiveDialogSessionId={archiveDialogSessionId}
      archiveDialogActionLabel={archiveDialogActionLabel}
      archiveDialogIsArchived={archiveDialogIsArchived}
      onCancelRenameDialog={cancelRenameDialog}
      onConfirmRenameDialog={confirmRenameDialog}
      onCancelArchiveDialog={cancelArchiveDialog}
      onConfirmArchiveDialog={confirmArchiveDialog}
    />
    <TeacherToolConfirmDialog toolConfirm={toolConfirm} onConfirm={confirmToolWrite} onCancel={cancelToolConfirm} />
    </>
  )
}
