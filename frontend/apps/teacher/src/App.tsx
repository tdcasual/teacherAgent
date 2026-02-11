import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Group, Panel, Separator, type PanelImperativeHandle } from 'react-resizable-panels'
import RoutingPage, { type RoutingSection } from './features/routing/RoutingPage'
import SettingsModal from './features/settings/SettingsModal'
import {
  buildInvocationToken,
  findInvocationTrigger,
  type InvocationTriggerType,
} from './features/chat/invocation'
import { useChatScroll } from './features/chat/useChatScroll'
import {
  readTeacherLocalViewState,
  type SessionViewStatePayload,
} from './features/chat/viewState'
import { useTeacherSessionViewStateSync } from './features/chat/useTeacherSessionViewStateSync'
import { withPendingChatOverlay } from './features/chat/pendingOverlay'
import { fallbackSkills, TEACHER_GREETING } from './features/chat/catalog'
import ChatComposer from './features/chat/ChatComposer'
import ChatMessages from './features/chat/ChatMessages'
import MentionPanel from './features/chat/MentionPanel'
import SessionSidebar from './features/chat/SessionSidebar'
import TeacherWorkbench from './features/workbench/TeacherWorkbench'
import { useAssignmentUploadStatusPolling } from './features/workbench/useAssignmentUploadStatusPolling'
import { useExamUploadStatusPolling } from './features/workbench/useExamUploadStatusPolling'
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
import { sessionGroupFromIso, sessionGroupOrder } from '../../shared/sessionGrouping'
import { ConfirmDialog, PromptDialog } from '../../shared/dialog'
import { safeLocalStorageGetItem, safeLocalStorageRemoveItem, safeLocalStorageSetItem } from './utils/storage'
import { makeId } from './utils/id'
import { formatSessionUpdatedLabel, nowTime } from './utils/time'
import { useTeacherWorkbenchState } from './features/state/useTeacherWorkbenchState'
import { useDraftMutations } from './features/workbench/hooks/useDraftMutations'
import { useWheelScrollZone } from './features/chat/useWheelScrollZone'
import { useLocalStorageSync } from './features/state/useLocalStorageSync'
import { useSessionActions } from './features/chat/useSessionActions'
import { useAssignmentWorkflow } from './features/workbench/hooks/useAssignmentWorkflow'
import { useExamWorkflow } from './features/workbench/hooks/useExamWorkflow'
import { useTeacherChatApi } from './features/chat/useTeacherChatApi'
import { useTeacherSessionState } from './features/state/useTeacherSessionState'
import type {
  MentionOption,
  Message,
  PendingChatJob,
  SessionGroup,
  Skill,
  TeacherHistorySession,
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
const ROUTING_SECTIONS: RoutingSection[] = ['general', 'providers', 'channels', 'rules', 'simulate', 'history']

const isRoutingSection = (value: string | null | undefined): value is RoutingSection =>
  Boolean(value && ROUTING_SECTIONS.includes(value as RoutingSection))

const workbenchMaxWidthForViewport = (viewportWidth: number) => {
  const fluidMax = Math.round(viewportWidth * WORKBENCH_MAX_WIDTH_RATIO)
  return Math.min(WORKBENCH_HARD_MAX_WIDTH, Math.max(WORKBENCH_BASE_MAX_WIDTH, fluidMax))
}

export default function App() {
  const initialViewStateRef = useRef<SessionViewStatePayload>(readTeacherLocalViewState())
  const workbenchPanelRef = useRef<PanelImperativeHandle | null>(null)
  const workbench = useTeacherWorkbenchState()
  const session = useTeacherSessionState(initialViewStateRef.current)
  const [isWorkbenchResizing, setIsWorkbenchResizing] = useState(false)
  const [viewportWidth, setViewportWidth] = useState(() => (typeof window !== 'undefined' ? window.innerWidth : 1280))
  const isMobileLayout = viewportWidth <= DESKTOP_BREAKPOINT
  const workbenchMaxWidth = workbenchMaxWidthForViewport(viewportWidth)
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
    progressOnlyIncomplete, proposalLoading, proposalError, proposals, memoryStatusFilter, memoryInsights,
    examId, examDate, examClassName, examPaperFiles, examScoreFiles, examAnswerFiles, examUploading, examUploadStatus, examUploadError,
    examJobId, examJobInfo, examStatusPollNonce, examDraft, examDraftPanelCollapsed, examDraftLoading, examDraftError, examDraftSaving,
    examDraftActionStatus, examDraftActionError, examConfirming,
    setUploadMode, setUploadAssignmentId, setUploadDate, setUploadScope, setUploadClassName, setUploadStudentIds, setUploadFiles,
    setUploadAnswerFiles, setUploading, setUploadStatus, setUploadError, setUploadCardCollapsed, setUploadJobId, setUploadJobInfo,
    setUploadConfirming, setUploadStatusPollNonce, setUploadDraft, setDraftPanelCollapsed, setDraftLoading, setDraftError,
    setQuestionShowCount, setDraftSaving, setDraftActionStatus, setDraftActionError, setMisconceptionsText, setMisconceptionsDirty,
    setProgressPanelCollapsed, setProgressAssignmentId, setProgressLoading, setProgressError, setProgressData, setProgressOnlyIncomplete,
    setProposalLoading, setProposalError, setProposals, setMemoryStatusFilter, setMemoryInsights,
    setExamId, setExamDate, setExamClassName, setExamPaperFiles, setExamScoreFiles, setExamAnswerFiles, setExamUploading,
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
  const [settingsLegacyFlat, setSettingsLegacyFlat] = useState(false)
  const [inlineRoutingOpen, setInlineRoutingOpen] = useState(false)
  const [settingsHasUnsavedDraft, setSettingsHasUnsavedDraft] = useState(false)
  const [settingsSection, setSettingsSection] = useState<RoutingSection>(() => {
    const raw = safeLocalStorageGetItem('teacherSettingsSection')
    return isRoutingSection(raw) ? raw : 'general'
  })
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
  const [mentionIndex, setMentionIndex] = useState(0)
  const [composerWarning, setComposerWarning] = useState('')
  const [chatQueueHint, setChatQueueHint] = useState('')
  const PENDING_CHAT_KEY = 'teacherPendingChatJob'
	  const [pendingChatJob, setPendingChatJob] = useState<PendingChatJob | null>(() => {
	    try {
	      const raw = safeLocalStorageGetItem(PENDING_CHAT_KEY)
	      return raw ? (JSON.parse(raw) as any) : null
	    } catch {
	      return null
	    }
	  })
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

  const { wheelScrollZoneRef, setWheelScrollZone, resolveWheelScrollTarget } = useWheelScrollZone({
    appRef, sessionSidebarOpen, skillsOpen, inlineRoutingOpen,
  })

  const chooseSkill = (skillId: string, pinned = true) => {
    setActiveSkillId(skillId)
    setSkillPinned(pinned)
  }

  const {
    refreshTeacherSessions, loadTeacherSessionMessages,
    refreshMemoryProposals, refreshMemoryInsights,
    submitMessage, fetchSkills, renderedMessages,
    appendMessage, updateMessage,
    activeSessionRef, sessionRequestRef,
    historyCursorRef, historyHasMoreRef, localDraftSessionIdsRef,
    pendingChatJobRef, markdownCacheRef,
  } = useTeacherChatApi({
    apiBase, activeSessionId, messages, sending, activeSkillId, skillPinned, skillList,
    pendingChatJob, memoryStatusFilter, skillsOpen, workbenchTab,
    setMessages, setSending, setActiveSessionId, setPendingChatJob, setChatQueueHint,
    setComposerWarning, setInput,
    setHistorySessions, setHistoryLoading, setHistoryError, setHistoryCursor, setHistoryHasMore,
    setLocalDraftSessionIds, setSessionLoading, setSessionError, setSessionCursor, setSessionHasMore,
    setProposalLoading, setProposalError, setProposals, setMemoryInsights,
    setSkillList, setSkillsLoading, setSkillsError,
    chooseSkill, enableAutoScroll, setWheelScrollZone,
  })

  useLocalStorageSync({
    apiBase, favorites, skillsOpen, workbenchTab, sessionSidebarOpen, settingsSection,
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
    assignmentWorkflowIndicator, assignmentWorkflowAutoState,
    computeLocalRequirementsMissing, updateDraftRequirement, updateDraftQuestion,
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
  }, [pendingChatJob?.session_id])

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
  }, [])

	  useEffect(() => {
	    if (pendingChatJob) safeLocalStorageSetItem(PENDING_CHAT_KEY, JSON.stringify(pendingChatJob))
	    else safeLocalStorageRemoveItem(PENDING_CHAT_KEY)
	  }, [pendingChatJob, PENDING_CHAT_KEY])

  useEffect(() => {
    if (!pendingChatJob?.job_id) return
    if (!activeSessionId || pendingChatJob.session_id !== activeSessionId) return
    setMessages((prev) => withPendingChatOverlay(prev, pendingChatJob, activeSessionId))
  }, [
    activeSessionId,
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


  const mention = useMemo(() => {
    const trigger = findInvocationTrigger(input, cursorPos)
    if (!trigger) return null
    const query = trigger.query
    const source: MentionOption[] = skillList.map((skill) => ({
      id: skill.id,
      title: skill.title,
      desc: skill.desc,
      type: 'skill' as const,
    }))

    const items = source.filter(
      (item) =>
        item.title.toLowerCase().includes(query) ||
        item.desc.toLowerCase().includes(query) ||
        item.id.toLowerCase().includes(query),
    )
    return { start: trigger.start, query, type: trigger.type, items }
  }, [cursorPos, input, skillList])

  useEffect(() => {
    if (mention && mention.items.length) {
      setMentionIndex(0)
    }
  }, [mention?.items.length])

  const filteredSkills = useMemo(() => {
    const query = skillQuery.trim().toLowerCase()
    let list = skillList.filter((skill) => {
      if (!query) return true
      return (
        skill.id.toLowerCase().includes(query) ||
        skill.title.toLowerCase().includes(query) ||
        skill.desc.toLowerCase().includes(query)
      )
    })
    if (showFavoritesOnly) {
      list = list.filter((skill) => favorites.includes(skill.id))
    }
    return list.sort((a, b) => {
      const aFav = favorites.includes(a.id)
      const bFav = favorites.includes(b.id)
      if (aFav === bFav) return a.title.localeCompare(b.title)
      return aFav ? -1 : 1
    })
  }, [skillQuery, showFavoritesOnly, favorites, skillList])

  const visibleHistorySessions = useMemo(() => {
    const archived = new Set(deletedSessionIds)
    const q = historyQuery.trim().toLowerCase()
    return historySessions.filter((item) => {
      const sid = String(item.session_id || '').trim()
      if (!sid) return false
      const title = (sessionTitleMap[sid] || '').toLowerCase()
      const preview = (item.preview || '').toLowerCase()
      const matched = !q || sid.toLowerCase().includes(q) || title.includes(q) || preview.includes(q)
      if (!matched) return false
      return showArchivedSessions ? archived.has(sid) : !archived.has(sid)
    })
  }, [historySessions, deletedSessionIds, historyQuery, sessionTitleMap, showArchivedSessions])

  const groupedHistorySessions = useMemo(() => {
    const buckets = new Map<string, SessionGroup<TeacherHistorySession>>()
    for (const item of visibleHistorySessions) {
      const info = sessionGroupFromIso(item.updated_at)
      const existing = buckets.get(info.key)
      if (existing) {
        existing.items.push(item)
      } else {
        buckets.set(info.key, { key: info.key, label: info.label, items: [item] })
      }
    }
    return Array.from(buckets.values()).sort((a, b) => {
      const oa = sessionGroupOrder[a.key] ?? 99
      const ob = sessionGroupOrder[b.key] ?? 99
      if (oa !== ob) return oa - ob
      return a.label.localeCompare(b.label)
    })
  }, [visibleHistorySessions])

  const getSessionTitle = useCallback(
    (sessionId: string) => {
      const sid = String(sessionId || '').trim()
      if (!sid) return '未命名会话'
      return sessionTitleMap[sid] || sid
    },
    [sessionTitleMap],
  )

  const isMobileViewport = useCallback(() => {
    if (typeof window === 'undefined') return false
    return window.matchMedia('(max-width: 900px)').matches
  }, [])

  const {
    startNewTeacherSession, renameSession, toggleSessionMenu,
    toggleSessionArchive, focusSessionMenuTrigger,
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

  const archiveDialogIsArchived = archiveDialogSessionId ? deletedSessionIds.includes(archiveDialogSessionId) : false
  const archiveDialogActionLabel = archiveDialogIsArchived ? '恢复' : '归档'

  const toggleSkillsWorkbench = useCallback(() => {
    if (skillsOpen) {
      setSkillsOpen(false)
      return
    }
    setSkillsOpen(true)
    if (isMobileViewport()) setSessionSidebarOpen(false)
  }, [isMobileViewport, skillsOpen])

  const activeSkill = useMemo(() => {
    if (!activeSkillId) return null
    return skillList.find((s) => s.id === activeSkillId) || null
  }, [activeSkillId, skillList])

  useEffect(() => {
    if (!activeSkillId) {
      setActiveSkillId('physics-teacher-ops')
      setSkillPinned(false)
      return
    }
    if (!activeSkill) {
      setActiveSkillId('physics-teacher-ops')
      setSkillPinned(false)
    }
  }, [activeSkillId, activeSkill])

  // Avoid any accidental key handlers interfering with draft editing.
  const stopKeyPropagation = (e: KeyboardEvent<HTMLElement>) => {
    e.stopPropagation()
  }

  const insertPrompt = (prompt: string) => {
    const nextValue = input ? `${input}\n${prompt}` : prompt
    setInput(nextValue)
    requestAnimationFrame(() => {
      if (!inputRef.current) return
      inputRef.current.focus()
      inputRef.current.setSelectionRange(nextValue.length, nextValue.length)
      setCursorPos(nextValue.length)
    })
  }

  const insertInvocationTokenAtCursor = (type: InvocationTriggerType, id: string) => {
    const token = buildInvocationToken(type, id)
    if (!token) return
    const before = input.slice(0, cursorPos)
    const after = input.slice(cursorPos)
    const leading = before && !/\s$/.test(before) ? ' ' : ''
    const trailing = after && !/^\s/.test(after) ? ' ' : ''
    const nextValue = `${before}${leading}${token}${trailing}${after}`
    const nextPos = (before + leading + token).length
    setInput(nextValue)
    setCursorPos(nextPos)

    const el = inputRef.current
    if (el) {
      try {
        el.value = nextValue
        el.focus()
        el.setSelectionRange(nextPos, nextPos)
      } catch {
        // ignore selection errors
      }
    }
  }

  const insertMention = (item: MentionOption) => {
    if (!mention) return
    const token = buildInvocationToken(item.type, item.id)
    if (!token) return
    chooseSkill(item.id, true)
    const before = input.slice(0, mention.start)
    const after = input.slice(cursorPos)
	    const nextValue = `${before}${token} ${after}`.replace(/\s+$/, ' ')
	    const nextPos = `${before}${token} `.length
	    setInput(nextValue)
	    setCursorPos(nextPos)

	    const el = inputRef.current
	    if (el) {
	      try {
	        // Ensure the cursor lands after the inserted token immediately, not only after the next render.
	        el.value = nextValue
	        el.focus()
	        el.setSelectionRange(nextPos, nextPos)
	      } catch {
	        // ignore selection errors
	      }
	    }
	  }

  const toggleFavorite = (skillId: string) => {
    setFavorites((prev) => (prev.includes(skillId) ? prev.filter((id) => id !== skillId) : [...prev, skillId]))
  }

  const handleSend = async (event: FormEvent) => {
    event.preventDefault()
    if (sending) return
    await submitMessage(input.trim())
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (mention && mention.items.length) {
      if (event.key === 'ArrowDown') {
        event.preventDefault()
        setMentionIndex((prev) => (prev + 1) % mention.items.length)
        return
      }
      if (event.key === 'ArrowUp') {
        event.preventDefault()
        setMentionIndex((prev) => (prev - 1 + mention.items.length) % mention.items.length)
        return
      }
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault()
        const item = mention.items[mentionIndex]
        if (item) insertMention(item)
        return
      }
    }

    if (event.key === 'Enter' && !event.shiftKey) {
      if ((event.nativeEvent as any)?.isComposing) return
      event.preventDefault()
      if (!input.trim()) return
      if (pendingChatJob?.job_id || sending) return
      void submitMessage(input.trim())
    }
  }

  const requestCloseSettings = useCallback(() => {
    if (settingsHasUnsavedDraft && typeof window !== 'undefined') {
      const confirmed = window.confirm('当前有未提交的路由草稿，确认关闭并丢弃吗？')
      if (!confirmed) return
    }
    setSettingsOpen(false)
    setSettingsLegacyFlat(false)
    setSettingsHasUnsavedDraft(false)
  }, [settingsHasUnsavedDraft])

  const toggleSettingsPanel = useCallback(() => {
    if (settingsOpen) {
      requestCloseSettings()
      return
    }
    setInlineRoutingOpen(false)
    setSettingsLegacyFlat(false)
    setSettingsOpen(true)
  }, [requestCloseSettings, settingsOpen])

  const openRoutingSettingsPanel = useCallback(() => {
    setInlineRoutingOpen(true)
    setSettingsSection('general')
    setSettingsLegacyFlat(false)
    if (settingsOpen) setSettingsOpen(false)
  }, [settingsOpen])

  const handleWorkbenchResizeReset = useCallback(() => {
    const panel = workbenchPanelRef.current
    if (!panel) return
    panel.resize(WORKBENCH_DEFAULT_WIDTH)
    panel.expand()
    if (!skillsOpen) setSkillsOpen(true)
  }, [skillsOpen])

  useEffect(() => {
    const panel = workbenchPanelRef.current
    if (!panel) return
    if (isMobileLayout || !skillsOpen) {
      panel.collapse()
      return
    }
    panel.expand()
    const currentWidth = panel.getSize().inPixels
    if (!Number.isFinite(currentWidth)) return
    const clamped = Math.min(workbenchMaxWidth, Math.max(WORKBENCH_MIN_WIDTH, Math.round(currentWidth)))
    if (Math.abs(clamped - currentWidth) > 1) {
      panel.resize(clamped)
    }
  }, [isMobileLayout, skillsOpen, workbenchMaxWidth])

  useEffect(() => {
    if (!isWorkbenchResizing || typeof window === 'undefined') return
    const stop = () => setIsWorkbenchResizing(false)
    window.addEventListener('pointerup', stop)
    window.addEventListener('pointercancel', stop)
    return () => {
      window.removeEventListener('pointerup', stop)
      window.removeEventListener('pointercancel', stop)
    }
  }, [isWorkbenchResizing])


  return (
    <div ref={appRef} className="h-dvh flex flex-col bg-bg overflow-hidden" style={{ ['--teacher-topbar-height' as any]: `${topbarHeight}px`, overscrollBehavior: 'none' }}>
      <header ref={topbarRef} className="flex justify-between items-center gap-[12px] px-4 py-[10px] bg-white/[0.94] border-b border-border sticky top-0 z-[25]" style={{ backdropFilter: 'saturate(180%) blur(8px)' }}>
        <div className="flex items-center gap-[10px] flex-wrap">
          <div className="font-bold text-[16px] tracking-[0.2px]">物理教学助手 · 老师端</div>
          <button className="ghost" type="button" onClick={toggleSessionSidebar}>
            {sessionSidebarOpen ? '收起会话' : '展开会话'}
          </button>
        </div>
        <div className="flex gap-[10px] items-center flex-wrap">
          <div className="role-badge teacher">身份：老师</div>
          <button className="ghost" type="button" onClick={openRoutingSettingsPanel}>
            模型路由
          </button>
          <button
            className="ghost"
            type="button"
            onClick={toggleSkillsWorkbench}
          >
            {skillsOpen ? '收起工作台' : '打开工作台'}
          </button>
          <button className="ghost border-none bg-transparent cursor-pointer p-[6px] rounded-lg text-[#6b7280] transition-[background] duration-150 ease-in-out hover:bg-surface-soft [&_svg]:block" onClick={toggleSettingsPanel} aria-label="设置">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
          </button>
        </div>
      </header>

      <SettingsModal
        open={settingsOpen}
        onClose={requestCloseSettings}
        sections={[
          { id: 'general', label: '通用' },
          { id: 'providers', label: 'Provider' },
          { id: 'channels', label: '渠道' },
          { id: 'rules', label: '路由规则' },
          { id: 'simulate', label: '仿真' },
          { id: 'history', label: '版本历史' },
        ]}
        activeSection={settingsSection}
        onSectionChange={(id) => {
          if (isRoutingSection(id)) setSettingsSection(id)
        }}
      >
        <RoutingPage
          apiBase={apiBase}
          onApiBaseChange={setApiBase}
          onDirtyChange={setSettingsHasUnsavedDraft}
          section={settingsSection}
          legacyFlat={settingsLegacyFlat}
        />
      </SettingsModal>

      <div
        className={`flex-1 min-h-0 grid relative bg-surface overflow-hidden ${sessionSidebarOpen ? 'grid-cols-[300px_minmax(0,1fr)] max-[900px]:grid-cols-[minmax(0,1fr)]' : 'grid-cols-[0_minmax(0,1fr)]'}`}
        style={{ overscrollBehavior: 'none' }}
      >
        <button
            type="button"
            className={`hidden max-[900px]:block max-[900px]:fixed max-[900px]:inset-0 max-[900px]:z-[15] max-[900px]:bg-black/[0.15] max-[900px]:transition-opacity max-[900px]:duration-200 max-[900px]:ease-in-out ${sessionSidebarOpen || skillsOpen ? 'max-[900px]:opacity-100 max-[900px]:pointer-events-auto' : 'max-[900px]:opacity-0 max-[900px]:pointer-events-none'}`}
            aria-label="关闭侧边栏"
            onClick={() => {
              setSessionSidebarOpen(false)
              setSkillsOpen(false)
            }}
          />
        <SessionSidebar
            open={sessionSidebarOpen}
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
            onSelectSession={(sid) => {
              setActiveSessionId(sid)
              setSessionCursor(-1)
              setSessionHasMore(false)
              setSessionError('')
              setOpenSessionMenuId('')
              closeSessionSidebarOnMobile()
            }}
            onToggleSessionMenu={toggleSessionMenu}
            onRenameSession={renameSession}
            onToggleSessionArchive={toggleSessionArchive}
            onLoadOlderMessages={() => void loadTeacherSessionMessages(activeSessionId, sessionCursor, true)}
            getSessionTitle={getSessionTitle}
            formatSessionUpdatedLabel={formatSessionUpdatedLabel}
          />

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
                      <main className={`flex-auto w-full min-w-0 min-h-0 flex flex-col gap-[10px] p-4 overflow-hidden bg-surface ${inlineRoutingOpen ? 'overflow-auto' : ''}`} style={inlineRoutingOpen ? { overscrollBehavior: 'contain' } : undefined}>
                        {inlineRoutingOpen ? (
                          <RoutingPage
                            apiBase={apiBase}
                            onApiBaseChange={setApiBase}
                            onDirtyChange={setSettingsHasUnsavedDraft}
                            section="general"
                            legacyFlat
                          />
                        ) : (
                          <>
                            <ChatMessages
                              renderedMessages={renderedMessages}
                              sending={sending}
                              hasPendingChatJob={Boolean(pendingChatJob?.job_id)}
                              typingTimeLabel={nowTime()}
                              messagesRef={messagesRef}
                              onMessagesScroll={handleMessagesScroll}
                              showScrollToBottom={showScrollToBottom}
                              onScrollToBottom={() => scrollMessagesToBottom('smooth')}
                            />

                            <ChatComposer
                              activeSkillId={activeSkillId || 'physics-teacher-ops'}
                              skillPinned={skillPinned}
                              input={input}
                              pendingChatJob={Boolean(pendingChatJob?.job_id)}
                              sending={sending}
                              chatQueueHint={chatQueueHint}
                              composerWarning={composerWarning}
                              inputRef={inputRef}
                              onSubmit={handleSend}
                              onInputChange={(value, selectionStart) => {
                                setInput(value)
                                setCursorPos(selectionStart)
                              }}
                              onInputClick={(selectionStart) => setCursorPos(selectionStart)}
                              onInputKeyUp={(selectionStart) => setCursorPos(selectionStart)}
                              onInputKeyDown={handleKeyDown}
                            />

	            	              {/* workflow panels moved to right workbench */}

                            <MentionPanel mention={mention} mentionIndex={mentionIndex} onInsert={insertMention} />
                          </>
                        )}
                      </main>
            </Panel>
            <Separator
              className={`w-2 cursor-col-resize flex items-center justify-center bg-transparent transition-[background] duration-150 ease-in-out shrink-0 hover:bg-[rgba(16,163,127,0.08)] ${isWorkbenchResizing ? 'bg-[rgba(16,163,127,0.08)]' : ''} ${!skillsOpen ? 'cursor-default pointer-events-none' : ''}`}
              onPointerDown={() => setIsWorkbenchResizing(true)}
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
                      <TeacherWorkbench
                          skillsOpen={skillsOpen}
                          setSkillsOpen={setSkillsOpen}
                          workbenchTab={workbenchTab}
                          setWorkbenchTab={setWorkbenchTab}
                          activeSkillId={activeSkillId}
                          activeWorkflowIndicator={activeWorkflowIndicator}
                          chooseSkill={chooseSkill}
                          difficultyLabel={difficultyLabel}
                          difficultyOptions={difficultyOptions}
                          draftActionError={draftActionError}
                          draftActionStatus={draftActionStatus}
                          draftError={draftError}
                          draftLoading={draftLoading}
                          draftPanelCollapsed={draftPanelCollapsed}
                          draftSaving={draftSaving}
                          examClassName={examClassName}
                          examConfirming={examConfirming}
                          examDate={examDate}
                          examDraft={examDraft}
                          examDraftActionError={examDraftActionError}
                          examDraftActionStatus={examDraftActionStatus}
                          examDraftError={examDraftError}
                          examDraftLoading={examDraftLoading}
                          examDraftPanelCollapsed={examDraftPanelCollapsed}
                          examDraftSaving={examDraftSaving}
                          examId={examId}
                          examJobInfo={examJobInfo}
                          examUploadError={examUploadError}
                          examUploadStatus={examUploadStatus}
                          examUploading={examUploading}
                          favorites={favorites}
                          fetchAssignmentProgress={fetchAssignmentProgress}
                          fetchSkills={fetchSkills}
                          filteredSkills={filteredSkills}
                          formatDraftSummary={formatDraftSummary}
                          formatExamDraftSummary={formatExamDraftSummary}
                          formatExamJobSummary={formatExamJobSummary}
                          formatMissingRequirements={formatMissingRequirements}
                          formatProgressSummary={formatProgressSummary}
                          formatUploadJobSummary={formatUploadJobSummary}
                          handleConfirmExamUpload={handleConfirmExamUpload}
                          handleConfirmUpload={handleConfirmUpload}
                          handleUploadAssignment={handleUploadAssignment}
                          handleUploadExam={handleUploadExam}
                          insertInvocationTokenAtCursor={insertInvocationTokenAtCursor}
                          insertPrompt={insertPrompt}
                          memoryInsights={memoryInsights}
                          memoryStatusFilter={memoryStatusFilter}
                          misconceptionsText={misconceptionsText}
                          normalizeDifficulty={normalizeDifficulty}
                          parseCommaList={parseCommaList}
                          parseLineList={parseLineList}
                          progressAssignmentId={progressAssignmentId}
                          progressData={progressData}
                          progressError={progressError}
                          progressLoading={progressLoading}
                          progressOnlyIncomplete={progressOnlyIncomplete}
                          progressPanelCollapsed={progressPanelCollapsed}
                          proposalError={proposalError}
                          proposalLoading={proposalLoading}
                          proposals={proposals}
                          questionShowCount={questionShowCount}
                          refreshMemoryInsights={refreshMemoryInsights}
                          refreshMemoryProposals={refreshMemoryProposals}
                          refreshWorkflowWorkbench={refreshWorkflowWorkbench}
                          saveDraft={saveDraft}
                          saveExamDraft={saveExamDraft}
                          scrollToWorkflowSection={scrollToWorkflowSection}
                          setComposerWarning={setComposerWarning}
                          setDraftPanelCollapsed={setDraftPanelCollapsed}
                          setExamAnswerFiles={setExamAnswerFiles}
                          setExamClassName={setExamClassName}
                          setExamDate={setExamDate}
                          setExamDraftPanelCollapsed={setExamDraftPanelCollapsed}
                          setExamId={setExamId}
                          setExamPaperFiles={setExamPaperFiles}
                          setExamScoreFiles={setExamScoreFiles}
                          setMemoryStatusFilter={setMemoryStatusFilter}
                          setMisconceptionsDirty={setMisconceptionsDirty}
                          setMisconceptionsText={setMisconceptionsText}
                          setProgressAssignmentId={setProgressAssignmentId}
                          setProgressOnlyIncomplete={setProgressOnlyIncomplete}
                          setProgressPanelCollapsed={setProgressPanelCollapsed}
                          setQuestionShowCount={setQuestionShowCount}
                          setShowFavoritesOnly={setShowFavoritesOnly}
                          setSkillPinned={setSkillPinned}
                          setSkillQuery={setSkillQuery}
                          setUploadAnswerFiles={setUploadAnswerFiles}
                          setUploadAssignmentId={setUploadAssignmentId}
                          setUploadCardCollapsed={setUploadCardCollapsed}
                          setUploadClassName={setUploadClassName}
                          setUploadDate={setUploadDate}
                          setUploadFiles={setUploadFiles}
                          setUploadMode={setUploadMode}
                          setUploadScope={setUploadScope}
                          setUploadStudentIds={setUploadStudentIds}
                          showFavoritesOnly={showFavoritesOnly}
                          skillPinned={skillPinned}
                          skillQuery={skillQuery}
                          skillsError={skillsError}
                          skillsLoading={skillsLoading}
                          stopKeyPropagation={stopKeyPropagation}
                          toggleFavorite={toggleFavorite}
                          updateDraftQuestion={updateDraftQuestion}
                          updateDraftRequirement={updateDraftRequirement}
                          updateExamAnswerKeyText={updateExamAnswerKeyText}
                          updateExamDraftMeta={updateExamDraftMeta}
                          updateExamScoreSchemaSelectedCandidate={updateExamScoreSchemaSelectedCandidate}
                          updateExamQuestionField={updateExamQuestionField}
                          uploadAssignmentId={uploadAssignmentId}
                          uploadCardCollapsed={uploadCardCollapsed}
                          uploadClassName={uploadClassName}
                          uploadConfirming={uploadConfirming}
                          uploadDate={uploadDate}
                          uploadDraft={uploadDraft}
                          uploadError={uploadError}
                          uploadJobInfo={uploadJobInfo}
                          uploadMode={uploadMode}
                          uploadScope={uploadScope}
                          uploadStatus={uploadStatus}
                          uploadStudentIds={uploadStudentIds}
                          uploading={uploading}
                        />
            </Panel>
          </Group>
        </div>
      </div>

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
