import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { absolutizeChartImageUrls, renderMarkdown } from './features/chat/markdown'
import RoutingPage, { type RoutingSection } from './features/routing/RoutingPage'
import SettingsModal from './features/settings/SettingsModal'
import {
  buildInvocationToken,
  findInvocationTrigger,
  parseInvocationInput,
  type InvocationTriggerType,
} from './features/chat/invocation'
import { decideSkillRouting } from './features/chat/requestRouting'
import { useChatScroll } from './features/chat/useChatScroll'
import {
  readTeacherLocalDraftSessionIds,
  readTeacherLocalViewState,
  TEACHER_LOCAL_DRAFT_SESSIONS_KEY,
  type SessionViewStatePayload,
} from './features/chat/viewState'
import { useTeacherSessionViewStateSync } from './features/chat/useTeacherSessionViewStateSync'
import { stripTransientPendingBubbles, withPendingChatOverlay } from './features/chat/pendingOverlay'
import { buildSkill, fallbackAgents, fallbackSkills, TEACHER_GREETING } from './features/chat/catalog'
import ChatComposer from './features/chat/ChatComposer'
import ChatMessages from './features/chat/ChatMessages'
import MentionPanel from './features/chat/MentionPanel'
import SessionSidebar from './features/chat/SessionSidebar'
import TeacherWorkbench from './features/workbench/TeacherWorkbench'
import { useWorkbenchResize } from './features/workbench/useWorkbenchResize'
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
import { buildAssignmentWorkflowIndicator, buildExamWorkflowIndicator } from './features/workbench/workflowIndicators'
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
import { startVisibilityAwareBackoffPolling } from '../../shared/visibilityBackoffPolling'
import { safeLocalStorageGetItem, safeLocalStorageRemoveItem, safeLocalStorageSetItem } from './utils/storage'
import { makeId } from './utils/id'
import { formatSessionUpdatedLabel, nowTime, timeFromIso } from './utils/time'
import { useTeacherWorkbenchState } from './features/state/useTeacherWorkbenchState'
import { useTeacherSessionState } from './features/state/useTeacherSessionState'
import type {
  AgentOption,
  AssignmentProgress,
  ChatJobStatus,
  ChatResponse,
  ChatStartResult,
  ExamUploadDraft,
  ExamUploadJobStatus,
  MentionOption,
  Message,
  PendingChatJob,
  RenderedMessage,
  SessionGroup,
  Skill,
  SkillResponse,
  TeacherHistoryMessage,
  TeacherHistorySession,
  TeacherHistorySessionResponse,
  TeacherHistorySessionsResponse,
  TeacherMemoryInsightsResponse,
  TeacherMemoryProposal,
  TeacherMemoryProposalListResponse,
  UploadDraft,
  UploadJobStatus,
  WheelScrollZone,
  WorkbenchTab,
  WorkflowIndicator,
  WorkflowIndicatorTone,
  WorkflowStepItem,
  WorkflowStepState,
} from './appTypes'
import 'katex/dist/katex.min.css'

const DEFAULT_API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const ROUTING_SECTIONS: RoutingSection[] = ['general', 'providers', 'channels', 'rules', 'simulate', 'history']

const isRoutingSection = (value: string | null | undefined): value is RoutingSection =>
  Boolean(value && ROUTING_SECTIONS.includes(value as RoutingSection))

export default function App() {
  const initialViewStateRef = useRef<SessionViewStatePayload>(readTeacherLocalViewState())
  const workbench = useTeacherWorkbenchState()
  const { isDragging: isResizeDragging, onResizeMouseDown } = useWorkbenchResize()
  const session = useTeacherSessionState(initialViewStateRef.current)
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
  const [activeAgentId, setActiveAgentId] = useState(() => safeLocalStorageGetItem('teacherActiveAgentId') || 'default')
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
  const wheelScrollZoneRef = useRef<WheelScrollZone>('chat')
  const markdownCacheRef = useRef(new Map<string, { content: string; html: string; apiBase: string }>())
  const activeSessionRef = useRef(activeSessionId)
  const historyRequestRef = useRef(0)
  const sessionRequestRef = useRef(0)
  const historyCursorRef = useRef(0)
  const historyHasMoreRef = useRef(false)
  const localDraftSessionIdsRef = useRef<string[]>([])
  const pendingChatJobRef = useRef<PendingChatJob | null>(pendingChatJob)

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

	  useEffect(() => {
	    safeLocalStorageSetItem('apiBaseTeacher', apiBase)
	    markdownCacheRef.current.clear()
	  }, [apiBase])

	  useEffect(() => {
	    safeLocalStorageSetItem('teacherSkillFavorites', JSON.stringify(favorites))
	  }, [favorites])

	  useEffect(() => {
	    safeLocalStorageSetItem('teacherSkillsOpen', String(skillsOpen))
	  }, [skillsOpen])

	  useEffect(() => {
	    safeLocalStorageSetItem('teacherWorkbenchTab', workbenchTab)
	  }, [workbenchTab])

	  useEffect(() => {
	    safeLocalStorageSetItem('teacherSessionSidebarOpen', String(sessionSidebarOpen))
	  }, [sessionSidebarOpen])

	  useEffect(() => {
	    safeLocalStorageSetItem('teacherSettingsSection', settingsSection)
	  }, [settingsSection])

  useEffect(() => {
    if (typeof window === 'undefined') return
    const el = topbarRef.current
    if (!el) return
    const updateHeight = () => {
      setTopbarHeight(Math.max(56, Math.round(el.getBoundingClientRect().height)))
    }
    updateHeight()
    let observer: ResizeObserver | null = null
    if (typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(updateHeight)
      observer.observe(el)
    }
    window.addEventListener('resize', updateHeight)
    return () => {
      window.removeEventListener('resize', updateHeight)
      observer?.disconnect()
    }
  }, [])

	  useEffect(() => {
	    if (activeAgentId) safeLocalStorageSetItem('teacherActiveAgentId', activeAgentId)
	    else safeLocalStorageRemoveItem('teacherActiveAgentId')
	  }, [activeAgentId])

	  useEffect(() => {
	    if (activeSkillId) safeLocalStorageSetItem('teacherActiveSkillId', activeSkillId)
	    else safeLocalStorageRemoveItem('teacherActiveSkillId')
	  }, [activeSkillId])

	  useEffect(() => {
	    safeLocalStorageSetItem('teacherSkillPinned', String(skillPinned))
	  }, [skillPinned])

  useEffect(() => {
    if (!composerWarning) return
    if (!input.trim()) return
    setComposerWarning('')
  }, [composerWarning, input])

  useEffect(() => {
    activeSessionRef.current = activeSessionId
  }, [activeSessionId])

  useEffect(() => {
    historyCursorRef.current = historyCursor
  }, [historyCursor])

  useEffect(() => {
    historyHasMoreRef.current = historyHasMore
  }, [historyHasMore])

  useEffect(() => {
    localDraftSessionIdsRef.current = localDraftSessionIds
  }, [localDraftSessionIds])

	  useEffect(() => {
	    try {
	      safeLocalStorageSetItem(TEACHER_LOCAL_DRAFT_SESSIONS_KEY, JSON.stringify(localDraftSessionIds))
	    } catch {
	      // ignore localStorage write errors
	    }
	  }, [localDraftSessionIds])

  useEffect(() => {
    pendingChatJobRef.current = pendingChatJob
  }, [pendingChatJob])

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
    if (!openSessionMenuId) return
    const onPointerDown = (event: MouseEvent | TouchEvent) => {
      const target = event.target as HTMLElement | null
      if (target?.closest('.session-menu-wrap')) return
      setOpenSessionMenuId('')
    }
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpenSessionMenuId('')
      }
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('touchstart', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('touchstart', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [openSessionMenuId])

  useEffect(() => {
    if (!sessionSidebarOpen) {
      setOpenSessionMenuId('')
    }
  }, [sessionSidebarOpen])

  useEffect(() => {
    if (activeSessionId) safeLocalStorageSetItem('teacherActiveSessionId', activeSessionId)
    else safeLocalStorageRemoveItem('teacherActiveSessionId')
  }, [activeSessionId])

	  useEffect(() => {
	    safeLocalStorageSetItem('teacherUploadMode', uploadMode)
	  }, [uploadMode])

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

  useEffect(() => {
    const el = inputRef.current
    if (!el) return
    el.style.height = '0px'
    const next = Math.min(220, Math.max(56, el.scrollHeight))
    el.style.height = `${next}px`
  }, [input, pendingChatJob?.job_id])

  const renderedMessages = useMemo(() => {
    const cache = markdownCacheRef.current
    return messages.map((msg): RenderedMessage => {
      const cached = cache.get(msg.id)
      if (cached && cached.content === msg.content && cached.apiBase === apiBase) {
        return { ...msg, html: cached.html }
      }
      const html = absolutizeChartImageUrls(renderMarkdown(msg.content), apiBase)
      cache.set(msg.id, { content: msg.content, html, apiBase })
      return { ...msg, html }
    })
  }, [messages, apiBase])

  useEffect(() => {
    if (uploadError && uploadCardCollapsed) setUploadCardCollapsed(false)
  }, [uploadError, uploadCardCollapsed])

  useEffect(() => {
    if (examUploadError && uploadCardCollapsed) setUploadCardCollapsed(false)
  }, [examUploadError, uploadCardCollapsed])

  useEffect(() => {
    if ((draftError || draftActionError) && draftPanelCollapsed) setDraftPanelCollapsed(false)
  }, [draftError, draftActionError, draftPanelCollapsed])

  useEffect(() => {
    if ((examDraftError || examDraftActionError) && examDraftPanelCollapsed) setExamDraftPanelCollapsed(false)
  }, [examDraftError, examDraftActionError, examDraftPanelCollapsed])

  const fetchSkills = useCallback(async () => {
    setSkillsLoading(true)
      setSkillsError('')
      try {
        const res = await fetch(`${apiBase}/skills`)
      if (!res.ok) throw new Error(`状态码 ${res.status}`)
      const data = (await res.json()) as SkillResponse
      const raw = Array.isArray(data.skills) ? data.skills : []
      const teacherSkills = raw.filter((skill) => {
        const roles = skill.allowed_roles
        return !Array.isArray(roles) || roles.includes('teacher')
      })
      if (teacherSkills.length === 0) {
        setSkillList(fallbackSkills)
        return
      }
      setSkillList(teacherSkills.map((skill) => buildSkill(skill)))
    } catch (err: any) {
      setSkillsError(err.message || '无法加载技能列表')
      setSkillList(fallbackSkills)
    } finally {
      setSkillsLoading(false)
    }
  }, [apiBase])

  useEffect(() => {
    void fetchSkills()
  }, [fetchSkills])

  useEffect(() => {
    if (!skillsOpen || workbenchTab !== 'skills') return
    void fetchSkills()
  }, [skillsOpen, workbenchTab, fetchSkills])

  useEffect(() => {
    if (!skillsOpen || workbenchTab !== 'skills') return
    const timer = window.setInterval(() => {
      void fetchSkills()
    }, 30000)
    return () => window.clearInterval(timer)
  }, [skillsOpen, workbenchTab, fetchSkills])

  const refreshTeacherSessions = useCallback(
    async (mode: 'reset' | 'more' = 'reset') => {
      if (mode === 'more' && !historyHasMoreRef.current) return
      const cursor = mode === 'more' ? historyCursorRef.current : 0
      const requestNo = ++historyRequestRef.current
      setHistoryLoading(true)
      if (mode === 'reset') setHistoryError('')
      try {
        const url = new URL(`${apiBase}/teacher/history/sessions`)
        url.searchParams.set('limit', '40')
        url.searchParams.set('cursor', String(cursor))
        const res = await fetch(url.toString())
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `状态码 ${res.status}`)
        }
        const data = (await res.json()) as TeacherHistorySessionsResponse
        if (requestNo !== historyRequestRef.current) return
        const serverSessions = Array.isArray(data.sessions) ? data.sessions : []
        const serverIds = new Set(serverSessions.map((item) => String(item.session_id || '').trim()).filter(Boolean))
        setLocalDraftSessionIds((prev) => prev.filter((id) => !serverIds.has(id)))
        const nextCursor = typeof data.next_cursor === 'number' ? data.next_cursor : null
        setHistoryCursor(nextCursor ?? 0)
        setHistoryHasMore(nextCursor !== null)
        if (mode === 'more') {
          setHistorySessions((prev) => {
            const merged = [...prev]
            const existingIds = new Set(prev.map((item) => item.session_id))
            for (const item of serverSessions) {
              if (existingIds.has(item.session_id)) continue
              merged.push(item)
            }
            return merged
          })
        } else {
          setHistorySessions((prev) => {
            const draftItems = localDraftSessionIdsRef.current
              .filter((id) => !serverIds.has(id))
              .map((id) => prev.find((item) => item.session_id === id) || { session_id: id, updated_at: new Date().toISOString(), message_count: 0, preview: '' })
            const seeded = [...draftItems, ...serverSessions]
            const seen = new Set(seeded.map((item) => item.session_id))
            for (const item of prev) {
              if (seen.has(item.session_id)) continue
              seeded.push(item)
            }
            return seeded
          })
        }
      } catch (err: any) {
        if (requestNo !== historyRequestRef.current) return
        setHistoryError(err.message || String(err))
      } finally {
        if (requestNo !== historyRequestRef.current) return
        setHistoryLoading(false)
      }
    },
    [apiBase]
  )

  const loadTeacherSessionMessages = useCallback(
    async (sessionId: string, cursor: number, append: boolean) => {
      const targetSessionId = (sessionId || '').trim()
      if (!targetSessionId) return
      const requestNo = ++sessionRequestRef.current
      setSessionLoading(true)
      setSessionError('')
      try {
        const LIMIT = 80
        const url = new URL(`${apiBase}/teacher/history/session`)
        url.searchParams.set('session_id', targetSessionId)
        url.searchParams.set('cursor', String(cursor))
        url.searchParams.set('limit', String(LIMIT))
        url.searchParams.set('direction', 'backward')
        const res = await fetch(url.toString())
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `状态码 ${res.status}`)
        }
        const data = (await res.json()) as TeacherHistorySessionResponse
        if (requestNo !== sessionRequestRef.current || activeSessionRef.current !== targetSessionId) return
        const raw = Array.isArray(data.messages) ? data.messages : []
        const mapped: Message[] = raw
          .map((m, idx) => {
            const roleRaw = String(m.role || '').toLowerCase()
            const role = roleRaw === 'user' ? 'user' : roleRaw === 'assistant' ? 'assistant' : null
            const content = typeof m.content === 'string' ? m.content : ''
            if (!role || !content) return null
            return {
              id: `thist_${targetSessionId}_${cursor}_${idx}_${m.ts || ''}`,
              role,
              content,
              time: timeFromIso(m.ts),
            } as Message
          })
          .filter(Boolean) as Message[]
        const mappedWithPending = append
          ? mapped
          : withPendingChatOverlay(mapped, pendingChatJobRef.current, targetSessionId)
        const next = typeof data.next_cursor === 'number' ? data.next_cursor : 0
        setSessionCursor(next)
        setSessionHasMore(mapped.length >= 1 && next > 0)
        if (append) {
          setMessages((prev) => [...mapped, ...prev])
        } else {
          setMessages(
            mappedWithPending.length
              ? mappedWithPending
              : [
                  {
                    id: makeId(),
                    role: 'assistant',
                    content: TEACHER_GREETING,
                    time: nowTime(),
                  },
                ]
          )
        }
      } catch (err: any) {
        if (requestNo !== sessionRequestRef.current || activeSessionRef.current !== targetSessionId) return
        setSessionError(err.message || String(err))
      } finally {
        if (requestNo !== sessionRequestRef.current || activeSessionRef.current !== targetSessionId) return
        setSessionLoading(false)
      }
    },
    [apiBase]
  )

  useEffect(() => {
    void refreshTeacherSessions()
  }, [refreshTeacherSessions])

  useEffect(() => {
    if (!activeSessionId) return
    void loadTeacherSessionMessages(activeSessionId, -1, false)
  }, [activeSessionId, loadTeacherSessionMessages])

  useEffect(() => {
    const timer = window.setInterval(() => {
      void refreshTeacherSessions()
    }, 30000)
    return () => window.clearInterval(timer)
  }, [refreshTeacherSessions])

  const refreshMemoryProposals = useCallback(async () => {
    setProposalLoading(true)
    setProposalError('')
    try {
      const url = new URL(`${apiBase}/teacher/memory/proposals`)
      if (memoryStatusFilter !== 'all') {
        url.searchParams.set('status', memoryStatusFilter)
      }
      url.searchParams.set('limit', '30')
      const res = await fetch(url.toString())
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `状态码 ${res.status}`)
      }
      const data = (await res.json()) as TeacherMemoryProposalListResponse
      setProposals(Array.isArray(data.proposals) ? data.proposals : [])
    } catch (err: any) {
      setProposalError(err.message || String(err))
    } finally {
      setProposalLoading(false)
    }
  }, [apiBase, memoryStatusFilter])

  const refreshMemoryInsights = useCallback(async () => {
    try {
      const url = new URL(`${apiBase}/teacher/memory/insights`)
      url.searchParams.set('days', '14')
      const res = await fetch(url.toString())
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `状态码 ${res.status}`)
      }
      const data = (await res.json()) as TeacherMemoryInsightsResponse
      setMemoryInsights(data)
    } catch (err) {
      // Keep panel usable even if insights endpoint is temporarily unavailable.
      setMemoryInsights(null)
    }
  }, [apiBase])

  useEffect(() => {
    if (!skillsOpen) return
    if (workbenchTab !== 'memory') return
    void refreshMemoryProposals()
    void refreshMemoryInsights()
  }, [skillsOpen, workbenchTab, refreshMemoryInsights, refreshMemoryProposals])

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

  const assignmentWorkflowIndicator = useMemo<WorkflowIndicator>(() => {
    return buildAssignmentWorkflowIndicator({
      uploadJobId,
      uploadJobInfoStatus: uploadJobInfo?.status,
      uploading,
      uploadConfirming,
      uploadDraft,
      uploadError,
      draftError,
      draftActionError,
    })
  }, [draftActionError, draftError, uploadConfirming, uploadDraft, uploadError, uploadJobId, uploadJobInfo?.status, uploading])

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

  const readWorkflowStepState = useCallback((indicator: WorkflowIndicator, stepKey: string): WorkflowStepState => {
    return indicator.steps.find((step) => step.key === stepKey)?.state || 'todo'
  }, [])

  const assignmentWorkflowAutoState = useMemo(() => {
    const uploadStep = readWorkflowStepState(assignmentWorkflowIndicator, 'upload')
    const parseStep = readWorkflowStepState(assignmentWorkflowIndicator, 'parse')
    const reviewStep = readWorkflowStepState(assignmentWorkflowIndicator, 'review')
    const confirmStep = readWorkflowStepState(assignmentWorkflowIndicator, 'confirm')
    if (parseStep === 'error') return 'parse-error'
    if (reviewStep === 'error') return 'review-error'
    if (confirmStep === 'error') return 'confirm-error'
    if (confirmStep === 'done') return 'confirmed'
    if (confirmStep === 'active') return 'confirming'
    if (reviewStep === 'active') return 'review'
    if (parseStep === 'active') return 'parsing'
    if (uploadStep === 'active') return 'uploading'
    return 'idle'
  }, [assignmentWorkflowIndicator, readWorkflowStepState])

  const examWorkflowAutoState = useMemo(() => {
    const uploadStep = readWorkflowStepState(examWorkflowIndicator, 'upload')
    const parseStep = readWorkflowStepState(examWorkflowIndicator, 'parse')
    const reviewStep = readWorkflowStepState(examWorkflowIndicator, 'review')
    const confirmStep = readWorkflowStepState(examWorkflowIndicator, 'confirm')
    if (parseStep === 'error') return 'parse-error'
    if (reviewStep === 'error') return 'review-error'
    if (confirmStep === 'error') return 'confirm-error'
    if (confirmStep === 'done') return 'confirmed'
    if (confirmStep === 'active') return 'confirming'
    if (reviewStep === 'active') return 'review'
    if (parseStep === 'active') return 'parsing'
    if (uploadStep === 'active') return 'uploading'
    return 'idle'
  }, [examWorkflowIndicator, readWorkflowStepState])

  const assignmentAutoStateRef = useRef('')
  const examAutoStateRef = useRef('')

  useEffect(() => {
    if (uploadMode !== 'assignment') return
    if (assignmentAutoStateRef.current === assignmentWorkflowAutoState) return
    assignmentAutoStateRef.current = assignmentWorkflowAutoState
    switch (assignmentWorkflowAutoState) {
      case 'uploading':
      case 'parsing':
      case 'parse-error':
        setUploadCardCollapsed(false)
        break
      case 'review':
      case 'confirming':
        setUploadCardCollapsed(true)
        setDraftPanelCollapsed(false)
        break
      case 'review-error':
      case 'confirm-error':
        setDraftPanelCollapsed(false)
        break
      case 'confirmed':
        setUploadCardCollapsed(true)
        setDraftPanelCollapsed(true)
        if ((progressAssignmentId || uploadAssignmentId || uploadDraft?.assignment_id || '').trim()) {
          setProgressPanelCollapsed(false)
        }
        break
      default:
        break
    }
  }, [assignmentWorkflowAutoState, progressAssignmentId, uploadAssignmentId, uploadDraft?.assignment_id, uploadMode])

  useEffect(() => {
    if (uploadMode !== 'exam') return
    if (examAutoStateRef.current === examWorkflowAutoState) return
    examAutoStateRef.current = examWorkflowAutoState
    switch (examWorkflowAutoState) {
      case 'uploading':
      case 'parsing':
      case 'parse-error':
        setUploadCardCollapsed(false)
        break
      case 'review':
      case 'confirming':
        setUploadCardCollapsed(true)
        setExamDraftPanelCollapsed(false)
        break
      case 'review-error':
      case 'confirm-error':
        setExamDraftPanelCollapsed(false)
        break
      case 'confirmed':
        setUploadCardCollapsed(true)
        setExamDraftPanelCollapsed(true)
        break
      default:
        break
    }
  }, [examWorkflowAutoState, uploadMode])

  useEffect(() => {
    if (!uploadJobId) return
    if (!uploadJobInfo) return
    if (uploadJobInfo.status !== 'done' && uploadJobInfo.status !== 'confirmed') return
    let active = true
    const loadDraft = async () => {
      setDraftError('')
      setDraftLoading(true)
      try {
        const res = await fetch(`${apiBase}/assignment/upload/draft?job_id=${encodeURIComponent(uploadJobId)}`)
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `状态码 ${res.status}`)
        }
        const data = await res.json()
        if (!active) return
        const draft = data?.draft as UploadDraft
        if (!draft || !draft.questions) throw new Error('draft 数据缺失')
        setUploadDraft(draft)
        setDraftPanelCollapsed(false)
        setQuestionShowCount(20)
      } catch (err: any) {
        if (!active) return
        setDraftError(err.message || String(err))
      } finally {
        if (!active) return
        setDraftLoading(false)
      }
    }
    loadDraft()
    return () => {
      active = false
    }
  }, [uploadJobId, uploadJobInfo?.status, apiBase])

  useEffect(() => {
    // Keep draft textarea editable (allow empty trailing lines while typing).
    if (!uploadDraft) return
    if (misconceptionsDirty) return
    const list = Array.isArray(uploadDraft.requirements?.misconceptions) ? uploadDraft.requirements.misconceptions : []
    setMisconceptionsText(list.join('\n'))
  }, [uploadDraft?.job_id, uploadDraft?.draft_version, misconceptionsDirty])

  useEffect(() => {
    if (!examJobId) return
    if (!examJobInfo) return
    if (examJobInfo.status !== 'done' && examJobInfo.status !== 'confirmed') return
    let active = true
    const loadDraft = async () => {
      setExamDraftError('')
      setExamDraftLoading(true)
      try {
        const res = await fetch(`${apiBase}/exam/upload/draft?job_id=${encodeURIComponent(examJobId)}`)
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `状态码 ${res.status}`)
        }
        const data = await res.json()
        if (!active) return
        const draft = data?.draft as ExamUploadDraft
        if (!draft || !draft.questions) throw new Error('draft 数据缺失')
        setExamDraft(draft)
        setExamDraftPanelCollapsed(false)
      } catch (err: any) {
        if (!active) return
        setExamDraftError(err.message || String(err))
      } finally {
        if (!active) return
        setExamDraftLoading(false)
      }
    }
    loadDraft()
    return () => {
      active = false
    }
  }, [examJobId, examJobInfo?.status, apiBase])

  const appendMessage = (roleType: 'user' | 'assistant', content: string) => {
    setMessages((prev) => [...prev, { id: makeId(), role: roleType, content, time: nowTime() }])
  }

  const updateMessage = (id: string, patch: Partial<Message>) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...patch } : m)))
  }

  useEffect(() => {
    if (!pendingChatJob?.job_id) return
    const cleanup = startVisibilityAwareBackoffPolling(
      async () => {
        if (pendingChatJob.session_id && activeSessionId && pendingChatJob.session_id !== activeSessionId) {
          return 'continue'
        }

        const res = await fetch(`${apiBase}/chat/status?job_id=${encodeURIComponent(pendingChatJob.job_id)}`)
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `状态码 ${res.status}`)
        }
        const data = (await res.json()) as ChatJobStatus
        if (data.status === 'done') {
          setMessages((prev) => {
            const overlaid = withPendingChatOverlay(prev, pendingChatJob, activeSessionId || pendingChatJob.session_id || 'main')
            return overlaid.map((msg) =>
              msg.id === pendingChatJob.placeholder_id ? { ...msg, content: data.reply || '已收到。', time: nowTime() } : msg,
            )
          })
          setPendingChatJob(null)
          setChatQueueHint('')
          setSending(false)
          void refreshTeacherSessions()
          return 'stop'
        }
        if (data.status === 'failed' || data.status === 'cancelled') {
          const msg = data.error_detail || data.error || '请求失败'
          setMessages((prev) => {
            const overlaid = withPendingChatOverlay(prev, pendingChatJob, activeSessionId || pendingChatJob.session_id || 'main')
            return overlaid.map((item) =>
              item.id === pendingChatJob.placeholder_id ? { ...item, content: `抱歉，请求失败：${msg}`, time: nowTime() } : item,
            )
          })
          setPendingChatJob(null)
          setChatQueueHint('')
          setSending(false)
          return 'stop'
        }
        const lanePos = Number((data as any).lane_queue_position || 0)
        const laneSize = Number((data as any).lane_queue_size || 0)
        if (data.status === 'queued') {
          setChatQueueHint(lanePos > 0 ? `排队中，前方 ${lanePos} 条（队列 ${laneSize}）` : '排队中...')
        } else if (data.status === 'processing') {
          setChatQueueHint('处理中...')
        } else {
          setChatQueueHint('')
        }
        return 'continue'
      },
      (err) => {
        const msg = (err as any)?.message || String(err)
        setMessages((prev) => {
          const overlaid = withPendingChatOverlay(prev, pendingChatJob, activeSessionId || pendingChatJob.session_id || 'main')
          return overlaid.map((item) =>
            item.id === pendingChatJob.placeholder_id ? { ...item, content: `网络波动，正在重试…（${msg}）`, time: nowTime() } : item,
          )
        })
      },
      { kickMode: 'direct' },
    )

    return () => {
      setChatQueueHint('')
      cleanup()
    }
  }, [pendingChatJob?.job_id, apiBase, refreshTeacherSessions])

  const agentList = useMemo(() => fallbackAgents, [])

  const mention = useMemo(() => {
    const trigger = findInvocationTrigger(input, cursorPos)
    if (!trigger) return null
    const query = trigger.query
    const source: MentionOption[] =
      trigger.type === 'skill'
        ? skillList.map((skill) => ({
            id: skill.id,
            title: skill.title,
            desc: skill.desc,
            type: 'skill' as const,
          }))
        : agentList.map((agent) => ({
            id: agent.id,
            title: agent.title,
            desc: agent.desc,
            type: 'agent' as const,
          }))

    const items = source.filter(
      (item) =>
        item.title.toLowerCase().includes(query) ||
        item.desc.toLowerCase().includes(query) ||
        item.id.toLowerCase().includes(query),
    )
    return { start: trigger.start, query, type: trigger.type, items }
  }, [agentList, cursorPos, input, skillList])

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

  const setWheelScrollZone = useCallback((zone: WheelScrollZone) => {
    wheelScrollZoneRef.current = zone
  }, [])

  const resolveWheelScrollTarget = useCallback(
    (zone: WheelScrollZone) => {
      const root = appRef.current
      if (!root) return null
      if (zone === 'session') {
        if (!sessionSidebarOpen) return null
        return root.querySelector('.session-groups') as HTMLElement | null
      }
      if (zone === 'workbench') {
        if (!skillsOpen) return null
        return (
          (root.querySelector('.skills-panel.open .skills-body') as HTMLElement | null) ||
          (root.querySelector('.skills-panel.open .workbench-memory') as HTMLElement | null)
        )
      }
      return root.querySelector('.messages') as HTMLElement | null
    },
    [sessionSidebarOpen, skillsOpen],
  )

  useEffect(() => {
    if (wheelScrollZoneRef.current === 'session' && !sessionSidebarOpen) {
      setWheelScrollZone('chat')
    }
    if (wheelScrollZoneRef.current === 'workbench' && !skillsOpen) {
      setWheelScrollZone('chat')
    }
  }, [sessionSidebarOpen, setWheelScrollZone, skillsOpen])

  useEffect(() => {
    if (typeof document === 'undefined') return
    const enabled = !isMobileViewport()
    if (!enabled) {
      setWheelScrollZone('chat')
      return
    }
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as HTMLElement | null
      if (!target) return
      const root = appRef.current
      if (!root || !root.contains(target)) return
      if (sessionSidebarOpen && target.closest('.session-sidebar')) {
        setWheelScrollZone('session')
        return
      }
      if (skillsOpen && target.closest('.skills-panel')) {
        setWheelScrollZone('workbench')
        return
      }
      if (target.closest('.chat-shell')) {
        setWheelScrollZone('chat')
      }
    }
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') setWheelScrollZone('chat')
    }
    document.addEventListener('pointerdown', onPointerDown, true)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('pointerdown', onPointerDown, true)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [isMobileViewport, sessionSidebarOpen, setWheelScrollZone, skillsOpen])

	  useEffect(() => {
	    if (typeof document === 'undefined') return
	    const enabled = !isMobileViewport()
	    if (!enabled) return

	    const onWheel = (event: WheelEvent) => {
	      if (event.defaultPrevented || event.ctrlKey) return
	      const target = event.target as HTMLElement | null
	      if (!target) return
	      const root = appRef.current
	      if (!root || !root.contains(target)) return
	      if (target.closest('textarea, input, select, [contenteditable="true"]')) return

	      const tryScroll = (el: HTMLElement | null) => {
	        if (!el) return false
	        const beforeTop = el.scrollTop
	        const beforeLeft = el.scrollLeft
	        if (event.deltaY) el.scrollTop += event.deltaY
	        if (event.deltaX) el.scrollLeft += event.deltaX
	        return el.scrollTop !== beforeTop || el.scrollLeft !== beforeLeft
	      }

	      let zone = wheelScrollZoneRef.current
	      if (zone === 'session' && !sessionSidebarOpen) zone = 'chat'
	      if (zone === 'workbench' && !skillsOpen) zone = 'chat'

	      // Important: always consume the wheel event while the app is in desktop chat mode.
	      // This prevents native scrolling of whichever panel happens to be under the cursor
	      // until the user explicitly activates a panel via pointer interaction.
	      event.preventDefault()

	      const destination = resolveWheelScrollTarget(zone)
	      tryScroll(destination)
	    }

	    document.addEventListener('wheel', onWheel, { passive: false, capture: true })
	    return () => {
	      document.removeEventListener('wheel', onWheel, true)
	    }
	  }, [isMobileViewport, resolveWheelScrollTarget, sessionSidebarOpen, skillsOpen])

  const closeSessionSidebarOnMobile = useCallback(() => {
    if (isMobileViewport()) {
      setSessionSidebarOpen(false)
    }
  }, [isMobileViewport])

  const toggleSessionSidebar = useCallback(() => {
    setSessionSidebarOpen((prev) => {
      const next = !prev
      if (next && isMobileViewport()) setSkillsOpen(false)
      return next
    })
  }, [isMobileViewport])

  const toggleSkillsWorkbench = useCallback(() => {
    if (skillsOpen) {
      setSkillsOpen(false)
      return
    }
    setSkillsOpen(true)
    if (isMobileViewport()) setSessionSidebarOpen(false)
  }, [isMobileViewport, skillsOpen])

  const startNewTeacherSession = useCallback(() => {
    const next = `session_${new Date().toISOString().slice(0, 10)}_${Math.random().toString(16).slice(2, 6)}`
    sessionRequestRef.current += 1
    setLocalDraftSessionIds((prev) => (prev.includes(next) ? prev : [next, ...prev]))
    setShowArchivedSessions(false)
    setActiveSessionId(next)
    setSessionCursor(-1)
    setSessionHasMore(false)
    setSessionError('')
    setOpenSessionMenuId('')
    setPendingChatJob(null)
    setSending(false)
    setInput('')
    setChatQueueHint('')
    setHistorySessions((prev) => {
      if (prev.some((item) => item.session_id === next)) return prev
      const nowIso = new Date().toISOString()
      return [{ session_id: next, updated_at: nowIso, message_count: 0, preview: '' }, ...prev]
    })
    setMessages([
      {
        id: makeId(),
        role: 'assistant',
        content: TEACHER_GREETING,
        time: nowTime(),
      },
    ])
    closeSessionSidebarOnMobile()
  }, [closeSessionSidebarOnMobile])

  const renameSession = useCallback(
    (sessionId: string) => {
      const sid = String(sessionId || '').trim()
      if (!sid) return
      setRenameDialogSessionId(sid)
    },
    [],
  )

  const toggleSessionMenu = useCallback(
    (sessionId: string) => {
      const sid = String(sessionId || '').trim()
      if (!sid) return
      setOpenSessionMenuId((prev) => (prev === sid ? '' : sid))
    },
    [],
  )

  const toggleSessionArchive = useCallback(
    (sessionId: string) => {
      const sid = String(sessionId || '').trim()
      if (!sid) return
      setArchiveDialogSessionId(sid)
    },
    [],
  )

  const focusSessionMenuTrigger = useCallback((sessionId: string) => {
    const sid = String(sessionId || '').trim()
    if (!sid) return
    const domSafe = sid.replace(/[^a-zA-Z0-9_-]/g, '_')
    const triggerId = `teacher-session-menu-${domSafe}-trigger`
    window.setTimeout(() => {
      const node = document.getElementById(triggerId) as HTMLButtonElement | null
      node?.focus?.()
    }, 0)
  }, [])

  const cancelRenameDialog = useCallback(() => {
    const sid = renameDialogSessionId
    setRenameDialogSessionId(null)
    setOpenSessionMenuId('')
    if (sid) focusSessionMenuTrigger(sid)
  }, [focusSessionMenuTrigger, renameDialogSessionId])

  const confirmRenameDialog = useCallback(
    (nextTitle: string) => {
      const sid = renameDialogSessionId
      if (!sid) return
      const title = String(nextTitle || '').trim()
      setSessionTitleMap((prev) => {
        const next = { ...prev }
        if (title) next[sid] = title
        else delete next[sid]
        return next
      })
      setRenameDialogSessionId(null)
      setOpenSessionMenuId('')
      focusSessionMenuTrigger(sid)
    },
    [focusSessionMenuTrigger, renameDialogSessionId],
  )

  const cancelArchiveDialog = useCallback(() => {
    const sid = archiveDialogSessionId
    setArchiveDialogSessionId(null)
    setOpenSessionMenuId('')
    if (sid) focusSessionMenuTrigger(sid)
  }, [archiveDialogSessionId, focusSessionMenuTrigger])

  const confirmArchiveDialog = useCallback(() => {
    const sid = archiveDialogSessionId
    if (!sid) return
    const isArchived = deletedSessionIds.includes(sid)
    setArchiveDialogSessionId(null)
    setOpenSessionMenuId('')
    setDeletedSessionIds((prev) => {
      if (isArchived) return prev.filter((id) => id !== sid)
      if (prev.includes(sid)) return prev
      return [...prev, sid]
    })
    focusSessionMenuTrigger(sid)
    if (!isArchived && activeSessionId === sid) {
      const next = visibleHistorySessions.find((item) => item.session_id !== sid)?.session_id
      if (next) {
        setActiveSessionId(next)
        setSessionCursor(-1)
        setSessionHasMore(false)
        setSessionError('')
      } else {
        startNewTeacherSession()
      }
    }
  }, [activeSessionId, archiveDialogSessionId, deletedSessionIds, startNewTeacherSession, visibleHistorySessions])

  const archiveDialogIsArchived = archiveDialogSessionId ? deletedSessionIds.includes(archiveDialogSessionId) : false
  const archiveDialogActionLabel = archiveDialogIsArchived ? '恢复' : '归档'

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

  useEffect(() => {
    if (!activeAgentId) {
      setActiveAgentId('default')
      return
    }
    if (!agentList.some((item) => item.id === activeAgentId)) {
      setActiveAgentId('default')
    }
  }, [activeAgentId, agentList])

  const computeLocalRequirementsMissing = (req: Record<string, any>) => {
    const missing: string[] = []
    const subject = String(req?.subject || '').trim()
    const topic = String(req?.topic || '').trim()
    const grade = String(req?.grade_level || '').trim()
    const classLevel = String(req?.class_level || '').trim()
    const core = Array.isArray(req?.core_concepts) ? req.core_concepts : []
    const typical = String(req?.typical_problem || '').trim()
    const misconceptions = Array.isArray(req?.misconceptions) ? req.misconceptions : []
    const duration = Number(req?.duration_minutes || 0)
    const prefs = Array.isArray(req?.preferences) ? req.preferences : []

    if (!subject) missing.push('subject')
    if (!topic) missing.push('topic')
    if (!grade) missing.push('grade_level')
    if (!['偏弱', '中等', '较强', '混合'].includes(classLevel)) missing.push('class_level')
    if (core.filter(Boolean).length < 3) missing.push('core_concepts')
    if (!typical) missing.push('typical_problem')
    if (misconceptions.filter(Boolean).length < 4) missing.push('misconceptions')
    if (![20, 40, 60].includes(duration)) missing.push('duration_minutes')
    if (prefs.filter(Boolean).length < 1) missing.push('preferences')

    return missing
  }

  const updateDraftRequirement = (key: string, value: any) => {
    setUploadDraft((prev) => {
      if (!prev) return prev
      const nextRequirements = {
        ...(prev.requirements || {}),
        [key]: value,
      }
      const nextMissing = computeLocalRequirementsMissing(nextRequirements)
      return {
        ...prev,
        requirements: nextRequirements,
        requirements_missing: nextMissing,
      }
    })
  }

  const updateDraftQuestion = (index: number, patch: Record<string, any>) => {
    setUploadDraft((prev) => {
      if (!prev) return prev
      const next = [...(prev.questions || [])]
      const cur = next[index] || {}
      next[index] = { ...cur, ...patch }
      return { ...prev, questions: next }
    })
  }

  const updateExamDraftMeta = (key: string, value: any) => {
    setExamDraft((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        meta: {
          ...(prev.meta || {}),
          [key]: value,
        },
      }
    })
  }

  const updateExamQuestionField = (index: number, patch: Record<string, any>) => {
    setExamDraft((prev) => {
      if (!prev) return prev
      const next = [...(prev.questions || [])]
      const cur = next[index] || {}
      next[index] = { ...cur, ...patch }
      return { ...prev, questions: next }
    })
  }

  const updateExamAnswerKeyText = (value: string) => {
    setExamDraft((prev) => {
      if (!prev) return prev
      return { ...prev, answer_key_text: value }
    })
  }

  // Avoid any accidental key handlers interfering with draft editing.
  const stopKeyPropagation = (e: KeyboardEvent<HTMLElement>) => {
    e.stopPropagation()
  }

  const chooseSkill = (skillId: string, pinned = true) => {
    setActiveSkillId(skillId)
    setSkillPinned(pinned)
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
	    if (item.type === 'skill') {
	      chooseSkill(item.id, true)
	    } else {
	      setActiveAgentId(item.id)
	    }
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

	  const submitMessage = async () => {
	    if (pendingChatJob?.job_id) return
	    const trimmed = input.trim()
	    if (!trimmed) return
	    const parsedInvocation = parseInvocationInput(trimmed, {
	      knownAgentIds: agentList.map((item) => item.id),
	      knownSkillIds: skillList.map((item) => item.id),
	      activeAgentId,
	      activeSkillId: activeSkillId || 'physics-teacher-ops',
	      defaultAgentId: 'default',
	    })
    const cleanedText = parsedInvocation.cleanedInput.trim()
    if (!cleanedText) {
      setComposerWarning('请在召唤后补充问题内容。')
      return
    }
    const routingDecision = decideSkillRouting({
      parsedInvocation,
      activeSkillId,
      skillPinned,
    })
    if (routingDecision.normalizedWarnings.length) {
      setComposerWarning(routingDecision.normalizedWarnings.join('；'))
    } else {
      setComposerWarning('')
    }
    if (routingDecision.shouldPinEffectiveSkill && parsedInvocation.effectiveSkillId) {
      chooseSkill(parsedInvocation.effectiveSkillId, true)
    }
    if (parsedInvocation.effectiveAgentId && parsedInvocation.effectiveAgentId !== activeAgentId) {
      setActiveAgentId(parsedInvocation.effectiveAgentId)
    }

    const sessionId = activeSessionId || 'main'
    if (!activeSessionId) setActiveSessionId(sessionId)
    const requestId = `tchat_${Date.now()}_${Math.random().toString(16).slice(2)}`
    const placeholderId = `asst_${Date.now()}_${Math.random().toString(16).slice(2)}`
    const routingTeacherId = (safeLocalStorageGetItem('teacherRoutingTeacherId') || '').trim()

    setWheelScrollZone('chat')
    enableAutoScroll()
    setMessages((prev) => {
      const next = stripTransientPendingBubbles(prev)
      return [
        ...next,
        { id: makeId(), role: 'user', content: cleanedText, time: nowTime() },
        { id: placeholderId, role: 'assistant', content: '正在生成…', time: nowTime() },
      ]
    })
    setInput('')

    const contextMessages = [...messages, { id: 'temp', role: 'user' as const, content: cleanedText, time: '' }]
      .slice(-40)
      .map((msg) => ({ role: msg.role, content: msg.content }))

    setSending(true)
    try {
      const res = await fetch(`${apiBase}/chat/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          request_id: requestId,
          session_id: sessionId,
          messages: contextMessages,
          role: 'teacher',
          teacher_id: routingTeacherId || undefined,
          agent_id: parsedInvocation.effectiveAgentId || activeAgentId || undefined,
          skill_id: routingDecision.skillIdForRequest,
        }),
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `状态码 ${res.status}`)
      }
      const data = (await res.json()) as ChatStartResult
      if (!data?.job_id) throw new Error('任务编号缺失')
      const lanePos = Number(data.lane_queue_position || 0)
      const laneSize = Number(data.lane_queue_size || 0)
      setChatQueueHint(lanePos > 0 ? `排队中，前方 ${lanePos} 条（队列 ${laneSize}）` : '处理中...')
      setPendingChatJob({
        job_id: data.job_id,
        request_id: requestId,
        placeholder_id: placeholderId,
        user_text: cleanedText,
        session_id: sessionId,
        lane_id: data.lane_id,
        created_at: Date.now(),
      })
    } catch (err: any) {
      updateMessage(placeholderId, { content: `抱歉，请求失败：${err.message || err}`, time: nowTime() })
      setSending(false)
      setChatQueueHint('')
      setPendingChatJob(null)
    }
  }

  const handleSend = async (event: FormEvent) => {
    event.preventDefault()
    if (sending) return
    await submitMessage()
  }

  const handleUploadAssignment = async (event: FormEvent) => {
    event.preventDefault()
    setUploadError('')
    setUploadStatus('')
    setUploadJobId('')
    setUploadJobInfo(null)
    setUploadDraft(null)
    setDraftPanelCollapsed(false)
    setDraftError('')
    setDraftActionStatus('')
    setDraftActionError('')
    setUploadCardCollapsed(false)
    if (!uploadAssignmentId.trim()) {
      setUploadError('请填写作业编号')
      return
    }
    if (!uploadFiles.length) {
      setUploadError('请至少上传一份作业文件（文档或图片）')
      return
    }
    if (uploadScope === 'student' && !uploadStudentIds.trim()) {
      setUploadError('私人作业请填写学生编号')
      return
    }
    if (uploadScope === 'class' && !uploadClassName.trim()) {
      setUploadError('班级作业请填写班级')
      return
    }
    setUploading(true)
    try {
      const fd = new FormData()
      fd.append('assignment_id', uploadAssignmentId.trim())
      if (uploadDate.trim()) fd.append('date', uploadDate.trim())
      fd.append('scope', uploadScope)
      if (uploadClassName.trim()) fd.append('class_name', uploadClassName.trim())
      if (uploadStudentIds.trim()) fd.append('student_ids', uploadStudentIds.trim())
      uploadFiles.forEach((file) => fd.append('files', file))
      uploadAnswerFiles.forEach((file) => fd.append('answer_files', file))

      const res = await fetch(`${apiBase}/assignment/upload/start`, { method: 'POST', body: fd })
      if (!res.ok) {
        const text = await res.text()
        let message = text || `状态码 ${res.status}`
        try {
          const parsed = JSON.parse(text)
          const detail = parsed?.detail || parsed
          if (typeof detail === 'string') {
            message = detail
          } else if (detail?.message) {
            const hints = Array.isArray(detail.hints) ? detail.hints.join('；') : ''
            message = `${detail.message}${hints ? `（${hints}）` : ''}`
          }
        } catch (err) {
          // ignore JSON parse errors
        }
        throw new Error(message)
      }
      const data = await res.json()
      if (data && typeof data === 'object') {
        if (data.job_id) {
	          const jid = String(data.job_id)
	          setUploadJobId(jid)
	          try {
	            safeLocalStorageSetItem('teacherActiveUpload', JSON.stringify({ type: 'assignment', job_id: jid }))
	          } catch {
	            // ignore
	          }
	        }
        const message = data.message || '解析任务已创建，后台处理中。'
        setUploadStatus(message)
      } else {
        setUploadStatus(typeof data === 'string' ? data : JSON.stringify(data, null, 2))
      }
      setUploadFiles([])
      setUploadAnswerFiles([])
    } catch (err: any) {
      setUploadError(err.message || String(err))
    } finally {
      setUploading(false)
    }
  }

  const handleUploadExam = async (event: FormEvent) => {
    event.preventDefault()
    setExamUploadError('')
    setExamUploadStatus('')
    setExamJobId('')
    setExamJobInfo(null)
    setExamDraft(null)
    setExamDraftPanelCollapsed(false)
    setExamDraftError('')
    setExamDraftActionStatus('')
    setExamDraftActionError('')
    setUploadCardCollapsed(false)
    if (!examPaperFiles.length) {
      setExamUploadError('请至少上传一份试卷文件（文档或图片）')
      return
    }
    if (!examScoreFiles.length) {
      setExamUploadError('请至少上传一份成绩文件（表格文件或文档/图片）')
      return
    }
    setExamUploading(true)
    try {
      const fd = new FormData()
      if (examId.trim()) fd.append('exam_id', examId.trim())
      if (examDate.trim()) fd.append('date', examDate.trim())
      if (examClassName.trim()) fd.append('class_name', examClassName.trim())
      examPaperFiles.forEach((file) => fd.append('paper_files', file))
      examScoreFiles.forEach((file) => fd.append('score_files', file))
      examAnswerFiles.forEach((file) => fd.append('answer_files', file))

      const res = await fetch(`${apiBase}/exam/upload/start`, { method: 'POST', body: fd })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `状态码 ${res.status}`)
      }
      const data = await res.json()
      if (data && typeof data === 'object') {
        if (data.job_id) {
	          const jid = String(data.job_id)
	          setExamJobId(jid)
	          try {
	            safeLocalStorageSetItem('teacherActiveUpload', JSON.stringify({ type: 'exam', job_id: jid }))
	          } catch {
	            // ignore
	          }
	        }
        const message = data.message || '考试解析任务已创建，后台处理中。'
        setExamUploadStatus(message)
      } else {
        setExamUploadStatus(typeof data === 'string' ? data : JSON.stringify(data, null, 2))
      }
      setExamPaperFiles([])
      setExamScoreFiles([])
      setExamAnswerFiles([])
    } catch (err: any) {
      setExamUploadError(err.message || String(err))
    } finally {
      setExamUploading(false)
    }
  }

  async function saveDraft(draft: UploadDraft) {
    setDraftSaving(true)
    setUploadError('')
    setDraftActionError('')
    setDraftActionStatus('正在保存草稿…')
    try {
      const normalizedRequirements = {
        ...(draft.requirements || {}),
        misconceptions: parseLineList(misconceptionsText),
      }
      const res = await fetch(`${apiBase}/assignment/upload/draft/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_id: draft.job_id,
          requirements: normalizedRequirements,
          questions: draft.questions,
        }),
      })
      if (!res.ok) {
        const text = await res.text()
        let message = text || `状态码 ${res.status}`
        try {
          const parsed = JSON.parse(text)
          const detail = parsed?.detail || parsed
          if (typeof detail === 'string') message = detail
          if (detail?.message) message = detail.message
        } catch {
          // ignore
        }
        throw new Error(message)
      }
      const data = await res.json()
      if (data?.requirements_missing) {
        setUploadDraft((prev) =>
          prev
            ? {
                ...prev,
                requirements_missing: data.requirements_missing,
                requirements: normalizedRequirements,
                draft_saved: true,
              }
            : prev
        )
      }
      const msg = data?.message || '草稿已保存。'
      setDraftActionStatus(msg)
      setUploadStatus((prev) => `${prev ? prev + '\n\n' : ''}${msg}`)
      setMisconceptionsDirty(false)
      return data
    } catch (err: any) {
      const message = err?.message || String(err)
      setDraftActionError(message)
      throw err
    } finally {
      setDraftSaving(false)
    }
  }

  const fetchAssignmentProgress = async (assignmentId?: string) => {
    const aid = (assignmentId || progressAssignmentId || '').trim()
    if (!aid) {
      setProgressError('请先填写作业编号')
      return
    }
    setProgressLoading(true)
    setProgressError('')
    try {
      const res = await fetch(
        `${apiBase}/teacher/assignment/progress?assignment_id=${encodeURIComponent(aid)}&include_students=true`
      )
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `状态码 ${res.status}`)
      }
      const data = (await res.json()) as AssignmentProgress
      if (!data?.ok) {
        throw new Error('获取作业完成情况失败')
      }
      setProgressData(data)
      setProgressAssignmentId(data.assignment_id || aid)
    } catch (err: any) {
      setProgressError(err?.message || String(err))
    } finally {
      setProgressLoading(false)
    }
  }

  const refreshWorkflowWorkbench = () => {
    setUploadStatusPollNonce((n) => n + 1)
    setExamStatusPollNonce((n) => n + 1)
    const assignmentId = (progressAssignmentId || uploadAssignmentId || uploadDraft?.assignment_id || '').trim()
    if (assignmentId) {
      void fetchAssignmentProgress(assignmentId)
    }
  }

  const scrollToWorkflowSection = useCallback((sectionId: string) => {
    if (typeof document === 'undefined') return
    const node = document.getElementById(sectionId)
    if (!node) return
    node.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  const handleConfirmUpload = async () => {
    const resolvedJobId = (() => {
      const jobId = String(uploadJobId || '').trim()
      if (jobId) return jobId
      try {
        const raw = safeLocalStorageGetItem('teacherActiveUpload')
        if (!raw) return ''
        const active = JSON.parse(raw)
        if (active?.type === 'assignment' && active?.job_id) return String(active.job_id).trim()
      } catch {
        // ignore
      }
      return ''
    })()
    if (!resolvedJobId) return
    if (!uploadJobId) setUploadJobId(resolvedJobId)
    setUploadError('')
    setDraftActionError('')
    setDraftActionStatus('正在创建作业…')
    setUploadConfirming(true)
    try {
      // If parsing is still running, don't attempt to confirm. Force a status refresh and keep polling.
      if (uploadJobInfo && uploadJobInfo.status !== 'done' && uploadJobInfo.status !== 'confirmed' && uploadJobInfo.status !== 'created') {
        const message = '解析尚未完成，请等待解析完成后再创建作业。'
        setUploadError(message)
        setDraftActionError(message)
        setUploadStatusPollNonce((n) => n + 1)
        return
      }
      // Optimistic UI: show confirming state immediately while backend is working.
      setUploadJobInfo((prev) =>
        prev
          ? {
              ...prev,
              status: prev.status === 'confirmed' || prev.status === 'created' ? 'confirmed' : 'confirming',
              step: 'confirming',
              progress: prev.progress ?? 0,
            }
          : {
              job_id: resolvedJobId,
              status: 'confirming',
              step: 'confirming',
              progress: 0,
            }
      )
      // Ensure latest edits are saved before confirm
      if (uploadDraft) {
        await saveDraft(uploadDraft)
      }
      const res = await fetch(`${apiBase}/assignment/upload/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: resolvedJobId, strict_requirements: true }),
      })
      if (!res.ok) {
        const text = await res.text()
        let message = text || `状态码 ${res.status}`
        try {
          const parsed = JSON.parse(text)
          const detail = parsed?.detail || parsed
          if (typeof detail === 'string') message = detail
          if (detail?.message) message = detail.message
          if (detail?.error === 'job_not_ready') {
            // Re-enable polling and show progress hints.
            const progress = detail?.progress !== undefined ? `（进度 ${detail.progress}%）` : ''
            message = `${detail.message || '解析尚未完成'}${progress}`
            setUploadStatusPollNonce((n) => n + 1)
          }
          if (detail?.missing && Array.isArray(detail.missing)) {
            message = `${detail.message || '作业要求未补全'}：${formatMissingRequirements(detail.missing)}`
          }
        } catch {
          // ignore
        }
        throw new Error(message)
      }
      const data = await res.json()
      if (data && typeof data === 'object') {
        const lines: string[] = []
        lines.push(data.message || '作业已确认创建。')
        if (data.assignment_id) lines.push(`作业编号：${data.assignment_id}`)
        if (data.question_count !== undefined) lines.push(`题目数量：${data.question_count}`)
        if (Array.isArray(data.requirements_missing) && data.requirements_missing.length) {
          lines.push(`作业要求缺失项：${formatMissingRequirements(data.requirements_missing)}`)
        }
        if (Array.isArray(data.warnings) && data.warnings.length) {
          lines.push(`解析提示：${data.warnings.join('；')}`)
        }
        const msg = lines.join('\n')
        setDraftActionStatus(msg)
        setUploadStatus(msg)
        setUploadJobInfo((prev) =>
          prev ? { ...prev, status: 'confirmed' } : { job_id: resolvedJobId, status: 'confirmed' },
        )
        setDraftPanelCollapsed(true)
        try {
          const raw = safeLocalStorageGetItem('teacherActiveUpload')
          if (raw) {
            const active = JSON.parse(raw)
            if (active?.type === 'assignment' && active?.job_id === resolvedJobId) safeLocalStorageRemoveItem('teacherActiveUpload')
          }
        } catch {
          // ignore
        }
        if (data.assignment_id) {
          setProgressAssignmentId(data.assignment_id)
          setProgressPanelCollapsed(false)
          void fetchAssignmentProgress(data.assignment_id)
        }
      }
    } catch (err: any) {
      const message = err?.message || String(err)
      setUploadError(message)
      setDraftActionError(message)
    } finally {
      setUploadConfirming(false)
    }
  }

  async function saveExamDraft(draft: ExamUploadDraft) {
    setExamDraftSaving(true)
    setExamUploadError('')
    setExamDraftActionError('')
    setExamDraftActionStatus('正在保存考试草稿…')
    try {
      const res = await fetch(`${apiBase}/exam/upload/draft/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          job_id: draft.job_id,
          meta: draft.meta,
          questions: draft.questions,
          score_schema: draft.score_schema || {},
          answer_key_text: draft.answer_key_text ?? '',
        }),
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `状态码 ${res.status}`)
      }
      const data = await res.json()
      const msg = data?.message || '考试草稿已保存。'
      setExamDraftActionStatus(msg)
      setExamUploadStatus((prev) => `${prev ? prev + '\n\n' : ''}${msg}`)
      setExamDraft((prev) =>
        prev
          ? {
              ...prev,
              draft_saved: true,
              draft_version: data?.draft_version ?? prev.draft_version,
            }
          : prev
      )
      return data
    } catch (err: any) {
      const message = err?.message || String(err)
      setExamDraftActionError(message)
      throw err
    } finally {
      setExamDraftSaving(false)
    }
  }

  const handleConfirmExamUpload = async () => {
    if (!examJobId) return
    setExamUploadError('')
    setExamDraftActionError('')
    setExamDraftActionStatus('正在创建考试…')
    setExamConfirming(true)
    try {
      if (examJobInfo && examJobInfo.status !== 'done' && examJobInfo.status !== 'confirmed') {
        const message = '解析尚未完成，请等待解析完成后再创建考试。'
        setExamUploadError(message)
        setExamDraftActionError(message)
        setExamStatusPollNonce((n) => n + 1)
        return
      }
      setExamJobInfo((prev) =>
        prev
          ? {
              ...prev,
              status: prev.status === 'confirmed' ? 'confirmed' : 'confirming',
              step: 'confirming',
              progress: prev.progress ?? 0,
            }
          : prev
      )
      if (examDraft) {
        await saveExamDraft(examDraft)
      }
      const res = await fetch(`${apiBase}/exam/upload/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: examJobId }),
      })
      if (!res.ok) {
        const text = await res.text()
        let message = text || `状态码 ${res.status}`
        try {
          const parsed = JSON.parse(text)
          const detail = parsed?.detail || parsed
          if (typeof detail === 'string') message = detail
          if (detail?.message) message = detail.message
          if (detail?.error === 'job_not_ready') {
            const progress = detail?.progress !== undefined ? `（进度 ${detail.progress}%）` : ''
            message = `${detail.message || '解析尚未完成'}${progress}`
            setExamStatusPollNonce((n) => n + 1)
          }
        } catch {
          // ignore
        }
        throw new Error(message)
      }
      const data = await res.json()
      if (data && typeof data === 'object') {
        const lines: string[] = []
        lines.push(data.message || '考试已确认创建。')
        if (data.exam_id) lines.push(`考试编号：${data.exam_id}`)
        const msg = lines.join('\n')
        setExamDraftActionStatus(msg)
        setExamUploadStatus(msg)
	        setExamJobInfo((prev) => (prev ? { ...prev, status: 'confirmed' } : prev))
	        setExamDraftPanelCollapsed(true)
	        try {
	          const raw = safeLocalStorageGetItem('teacherActiveUpload')
	          if (raw) {
	            const active = JSON.parse(raw)
	            if (active?.type === 'exam' && active?.job_id === examJobId) safeLocalStorageRemoveItem('teacherActiveUpload')
	          }
	        } catch {
	          // ignore
	        }
	      }
    } catch (err: any) {
      const message = err?.message || String(err)
      setExamUploadError(message)
      setExamDraftActionError(message)
    } finally {
      setExamConfirming(false)
    }
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
      void submitMessage()
    }
  }

  const requestCloseSettings = useCallback(() => {
    if (settingsHasUnsavedDraft && typeof window !== 'undefined') {
      const confirmed = window.confirm('当前有未提交的路由草稿，确认关闭并丢弃吗？')
      if (!confirmed) return
    }
    setSettingsOpen(false)
    setSettingsHasUnsavedDraft(false)
  }, [settingsHasUnsavedDraft])

  const toggleSettingsPanel = useCallback(() => {
    if (settingsOpen) {
      requestCloseSettings()
      return
    }
    setSettingsOpen(true)
  }, [requestCloseSettings, settingsOpen])

  return (
    <div ref={appRef} className="app teacher" style={{ ['--teacher-topbar-height' as any]: `${topbarHeight}px` }}>
      <header ref={topbarRef} className="topbar">
        <div className="top-left">
          <div className="brand">物理教学助手 · 老师端</div>
          <button className="ghost" type="button" onClick={toggleSessionSidebar}>
            {sessionSidebarOpen ? '收起会话' : '展开会话'}
          </button>
        </div>
        <div className="top-actions">
          <div className="role-badge teacher">身份：老师</div>
          <button
            className="ghost"
            type="button"
            onClick={toggleSkillsWorkbench}
          >
            {skillsOpen ? '收起工作台' : '打开工作台'}
          </button>
          <button className="ghost settings-gear" onClick={toggleSettingsPanel} aria-label="设置">
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
        />
      </SettingsModal>

      <div
        className={`teacher-layout chat-view ${sessionSidebarOpen ? 'session-open' : 'session-collapsed'} ${skillsOpen ? 'workbench-open' : ''}`}
      >
        <button
            type="button"
            className={`layout-overlay ${sessionSidebarOpen || skillsOpen ? 'show' : ''}`}
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

        <main className="chat-shell">

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
            activeAgentId={activeAgentId || 'default'}
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
        </main>

        <TeacherWorkbench
            skillsOpen={skillsOpen}
            setSkillsOpen={setSkillsOpen}
            onResizeMouseDown={onResizeMouseDown}
            isResizeDragging={isResizeDragging}
            workbenchTab={workbenchTab}
            setWorkbenchTab={setWorkbenchTab}
            activeAgentId={activeAgentId}
            activeSkillId={activeSkillId}
            activeWorkflowIndicator={activeWorkflowIndicator}
            agentList={agentList}
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
            setActiveAgentId={setActiveAgentId}
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
