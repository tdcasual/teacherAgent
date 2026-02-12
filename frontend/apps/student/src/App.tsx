import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { makeId } from '../../shared/id'
import { renderMarkdown, absolutizeChartImageUrls } from '../../shared/markdown'
import { getNextMenuIndex } from '../../shared/sessionMenuNavigation'
import { sessionGroupFromIso, sessionGroupOrder } from '../../shared/sessionGrouping'
import { startVisibilityAwareBackoffPolling } from '../../shared/visibilityBackoffPolling'
import { safeLocalStorageGetItem, safeLocalStorageRemoveItem, safeLocalStorageSetItem } from '../../shared/storage'
import { nowTime, timeFromIso } from '../../shared/time'
import {
  STUDENT_LOCAL_DRAFT_SESSIONS_KEY_PREFIX,
  STUDENT_SESSION_VIEW_STATE_KEY_PREFIX,
  buildSessionViewStateSignature,
  compareSessionViewStateUpdatedAt,
  normalizeSessionViewStatePayload,
  readStudentLocalDraftSessionIds,
  readStudentLocalViewState,
  type SessionViewStatePayload,
} from './features/chat/viewState'
import { stripTransientPendingBubbles } from './features/chat/pendingOverlay'
import StudentChatPanel from './features/chat/StudentChatPanel'
import StudentSessionSidebar from './features/chat/StudentSessionSidebar'
import StudentTopbar from './features/layout/StudentTopbar'
import StudentSessionShell from './features/session/StudentSessionShell'
import StudentWorkbench from './features/workbench/StudentWorkbench'
import type {
  AssignmentDetail,
  ChatJobStatus,
  ChatStartResult,
  Message,
  PendingChatJob,
  RenderedMessage,
  SessionGroup,
  StudentHistorySession,
  StudentHistorySessionResponse,
  StudentHistorySessionsResponse,
  VerifiedStudent,
  VerifyResponse,
} from './appTypes'
import 'katex/dist/katex.min.css'

const PENDING_CHAT_KEY_PREFIX = 'studentPendingChatJob:'
const RECENT_COMPLETION_KEY_PREFIX = 'studentRecentCompletion:'
const SEND_LOCK_KEY_PREFIX = 'studentSendLock:'
const FALLBACK_SEND_LOCK_TTL_MS = 5000
const FALLBACK_SEND_LOCK_SETTLE_MS = 120
const FALLBACK_SEND_LOCK_RENEW_INTERVAL_MS = 1000
const RECENT_COMPLETION_TTL_MS = 3 * 60 * 1000

type RecentCompletedReply = {
  session_id: string
  user_text: string
  reply_text: string
  completed_at: number
}

const recentCompletionKeyOf = (item: RecentCompletedReply) =>
  `${item.session_id}::${item.completed_at}::${item.user_text}::${item.reply_text}`

const normalizeRecentCompletedReplies = (items: RecentCompletedReply[]) => {
  const now = Date.now()
  const sorted = items
    .map((item) => {
      const sessionId = String(item?.session_id || '').trim()
      const replyText = typeof item?.reply_text === 'string' ? item.reply_text : ''
      const userText = typeof item?.user_text === 'string' ? item.user_text : ''
      const completedAt = Number(item?.completed_at || 0)
      const normalized: RecentCompletedReply = {
        session_id: sessionId,
        user_text: userText,
        reply_text: replyText,
        completed_at: completedAt,
      }
      return normalized
    })
    .filter((item) => item.session_id && item.reply_text && Number.isFinite(item.completed_at) && item.completed_at > 0)
    .filter((item) => now - item.completed_at <= RECENT_COMPLETION_TTL_MS)
    .sort((a, b) => a.completed_at - b.completed_at)

  const seen = new Set<string>()
  const deduped: RecentCompletedReply[] = []
  for (const item of sorted) {
    const key = recentCompletionKeyOf(item)
    if (seen.has(key)) continue
    seen.add(key)
    deduped.push(item)
  }
  return deduped.slice(-20)
}

const parseRecentCompletedReplies = (raw: string | null): RecentCompletedReply[] => {
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) {
      const items = parsed
        .map((entry) => {
          const candidate = entry as Partial<RecentCompletedReply>
          return {
            session_id: String(candidate?.session_id || '').trim(),
            user_text: typeof candidate?.user_text === 'string' ? candidate.user_text : '',
            reply_text: typeof candidate?.reply_text === 'string' ? candidate.reply_text : '',
            completed_at: Number(candidate?.completed_at || 0),
          }
        })
        .filter((entry) => entry.session_id && entry.reply_text && Number.isFinite(entry.completed_at) && entry.completed_at > 0)
      return normalizeRecentCompletedReplies(items)
    }

    const candidate = parsed as Partial<RecentCompletedReply>
    const legacyItem: RecentCompletedReply = {
      session_id: String(candidate?.session_id || '').trim(),
      user_text: typeof candidate?.user_text === 'string' ? candidate.user_text : '',
      reply_text: typeof candidate?.reply_text === 'string' ? candidate.reply_text : '',
      completed_at: Number(candidate?.completed_at || 0),
    }
    return normalizeRecentCompletedReplies([legacyItem])
  } catch {
    return []
  }
}

const DEFAULT_API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const STUDENT_WELCOME_MESSAGE = '学生端已就绪。请先填写姓名完成验证，然后开始提问或进入作业讨论。'
const STUDENT_NEW_SESSION_MESSAGE = '已开启新会话。你可以继续提问，或输入“开始今天作业”。'

const todayDate = () => new Date().toLocaleDateString('sv-SE')

export default function App() {
  const [apiBase] = useState(() => safeLocalStorageGetItem('apiBaseStudent') || DEFAULT_API_URL)
  const [sidebarOpen, setSidebarOpen] = useState(() => safeLocalStorageGetItem('studentSidebarOpen') !== 'false')
  const [messages, setMessages] = useState<Message[]>(() => [
    {
      id: makeId(),
      role: 'assistant',
      content: STUDENT_WELCOME_MESSAGE,
      time: nowTime(),
    },
  ])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const endRef = useRef<HTMLDivElement | null>(null)
  const inputRef = useRef<HTMLTextAreaElement | null>(null)

  const [verifiedStudent, setVerifiedStudent] = useState<VerifiedStudent | null>(() => {
    const raw = safeLocalStorageGetItem('verifiedStudent')
    if (!raw) return null
    try {
      return JSON.parse(raw) as VerifiedStudent
    } catch {
      return null
    }
  })
  const [verifyOpen, setVerifyOpen] = useState(true)
  const [nameInput, setNameInput] = useState('')
  const [classInput, setClassInput] = useState('')
  const [verifying, setVerifying] = useState(false)
  const [verifyError, setVerifyError] = useState('')
  const [todayAssignment, setTodayAssignment] = useState<AssignmentDetail | null>(null)
  const [assignmentLoading, setAssignmentLoading] = useState(false)
  const [assignmentError, setAssignmentError] = useState('')
  const markdownCacheRef = useRef(new Map<string, { content: string; html: string; apiBase: string }>())

  const [pendingChatJob, setPendingChatJob] = useState<PendingChatJob | null>(() => {
    const sidRaw = safeLocalStorageGetItem('verifiedStudent')
    if (!sidRaw) return null
    try {
      const parsed = JSON.parse(sidRaw) as { student_id?: string }
      const sid = String(parsed?.student_id || '').trim()
      if (!sid) return null
      const raw = safeLocalStorageGetItem(`${PENDING_CHAT_KEY_PREFIX}${sid}`)
      return raw ? (JSON.parse(raw) as PendingChatJob) : null
    } catch {
      return null
    }
  })

  const [recentCompletedReplies, setRecentCompletedReplies] = useState<RecentCompletedReply[]>(() => {
    const sidRaw = safeLocalStorageGetItem('verifiedStudent')
    if (!sidRaw) return []
    try {
      const parsed = JSON.parse(sidRaw) as { student_id?: string }
      const sid = String(parsed?.student_id || '').trim()
      if (!sid) return []
      return parseRecentCompletedReplies(safeLocalStorageGetItem(`${RECENT_COMPLETION_KEY_PREFIX}${sid}`))
    } catch {
      return []
    }
  })

  const [sessions, setSessions] = useState<StudentHistorySession[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState('')
  const [historyCursor, setHistoryCursor] = useState(0)
  const [historyHasMore, setHistoryHasMore] = useState(false)
  const [historyQuery, setHistoryQuery] = useState('')
  const [showArchivedSessions, setShowArchivedSessions] = useState(false)
  const [sessionTitleMap, setSessionTitleMap] = useState<Record<string, string>>({})
  const [deletedSessionIds, setDeletedSessionIds] = useState<string[]>([])
  const [localDraftSessionIds, setLocalDraftSessionIds] = useState<string[]>([])
  const [openSessionMenuId, setOpenSessionMenuId] = useState('')
  const [renameDialogSessionId, setRenameDialogSessionId] = useState<string | null>(null)
  const [archiveDialogSessionId, setArchiveDialogSessionId] = useState<string | null>(null)
  const [activeSessionId, setActiveSessionId] = useState('')
  const [sessionLoading, setSessionLoading] = useState(false)
  const [sessionError, setSessionError] = useState('')
  const [sessionCursor, setSessionCursor] = useState(0)
  const [sessionHasMore, setSessionHasMore] = useState(false)
  const [viewStateUpdatedAt, setViewStateUpdatedAt] = useState(() => new Date().toISOString())
  const [viewStateSyncReady, setViewStateSyncReady] = useState(false)
  const [forceSessionLoadToken, setForceSessionLoadToken] = useState(0)
  const activeSessionRef = useRef('')
  const pendingChatJobRef = useRef<PendingChatJob | null>(pendingChatJob)
  const recentCompletedRepliesRef = useRef<RecentCompletedReply[]>(recentCompletedReplies)
  const pendingRecoveredFromStorageRef = useRef(false)
  const skipAutoSessionLoadIdRef = useRef('')
  const sessionMenuRefs = useRef<Record<string, HTMLDivElement | null>>({})
  const sessionMenuTriggerRefs = useRef<Record<string, HTMLButtonElement | null>>({})
  const historyRequestRef = useRef(0)
  const sessionRequestRef = useRef(0)
  const applyingViewStateRef = useRef(false)
  const currentViewStateRef = useRef<SessionViewStatePayload>(
    normalizeSessionViewStatePayload({
      title_map: {},
      hidden_ids: [],
      active_session_id: '',
      updated_at: new Date().toISOString(),
    }),
  )
  const lastSyncedViewStateSignatureRef = useRef('')
  const currentViewState = useMemo(
    () =>
      normalizeSessionViewStatePayload({
        title_map: sessionTitleMap,
        hidden_ids: deletedSessionIds,
        active_session_id: '',
        updated_at: viewStateUpdatedAt,
      }),
    [deletedSessionIds, sessionTitleMap, viewStateUpdatedAt],
  )

  const setActiveSession = useCallback((sessionId: string) => {
    const sid = String(sessionId || '').trim()
    activeSessionRef.current = sid
    setActiveSessionId(sid)
  }, [])

  useEffect(() => {
    safeLocalStorageSetItem('apiBaseStudent', apiBase)
    markdownCacheRef.current.clear()
  }, [apiBase])

  useEffect(() => {
    if (verifiedStudent) {
      safeLocalStorageSetItem('verifiedStudent', JSON.stringify(verifiedStudent))
    } else {
      safeLocalStorageRemoveItem('verifiedStudent')
    }
  }, [verifiedStudent])

  useEffect(() => {
    if (verifiedStudent) {
      setVerifyOpen(false)
    }
  }, [verifiedStudent])

  const toggleSessionMenu = useCallback(
    (sessionId: string) => {
      const sid = String(sessionId || '').trim()
      if (!sid) return
      setOpenSessionMenuId((prev) => (prev === sid ? '' : sid))
    },
    [],
  )

  const setSessionMenuRef = useCallback((sessionId: string, node: HTMLDivElement | null) => {
    const sid = String(sessionId || '').trim()
    if (!sid) return
    if (node) {
      sessionMenuRefs.current[sid] = node
      return
    }
    delete sessionMenuRefs.current[sid]
  }, [])

  const setSessionMenuTriggerRef = useCallback((sessionId: string, node: HTMLButtonElement | null) => {
    const sid = String(sessionId || '').trim()
    if (!sid) return
    if (node) {
      sessionMenuTriggerRefs.current[sid] = node
      return
    }
    delete sessionMenuTriggerRefs.current[sid]
  }, [])

  const focusSessionMenuItem = useCallback((sessionId: string, target: 'first' | 'last') => {
    const sid = String(sessionId || '').trim()
    if (!sid) return
    const menu = sessionMenuRefs.current[sid]
    if (!menu) return
    const items = Array.from(menu.querySelectorAll<HTMLButtonElement>('.session-menu-item:not([disabled])'))
    if (!items.length) return
    const index = target === 'last' ? items.length - 1 : 0
    items[index]?.focus()
  }, [])

  const handleSessionMenuTriggerKeyDown = useCallback(
    (sessionId: string, isMenuOpen: boolean, event: KeyboardEvent<HTMLButtonElement>) => {
      const sid = String(sessionId || '').trim()
      if (!sid) return
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault()
        event.stopPropagation()
        if (!isMenuOpen) toggleSessionMenu(sid)
        const target: 'first' | 'last' = event.key === 'ArrowUp' ? 'last' : 'first'
        window.setTimeout(() => focusSessionMenuItem(sid, target), 0)
        return
      }
      if (event.key === 'Escape' && isMenuOpen) {
        event.preventDefault()
        toggleSessionMenu(sid)
      }
    },
    [focusSessionMenuItem, toggleSessionMenu],
  )

  const handleSessionMenuKeyDown = useCallback(
    (sessionId: string, event: KeyboardEvent<HTMLDivElement>) => {
      const sid = String(sessionId || '').trim()
      if (!sid || openSessionMenuId !== sid) return
      const menu = sessionMenuRefs.current[sid]
      if (!menu) return
      const items = Array.from(menu.querySelectorAll<HTMLButtonElement>('.session-menu-item:not([disabled])'))
      if (!items.length) return
      const activeIndex = items.findIndex((item) => item === document.activeElement)

      if (event.key === 'Escape') {
        event.preventDefault()
        toggleSessionMenu(sid)
        sessionMenuTriggerRefs.current[sid]?.focus()
        return
      }
      if (event.key === 'Tab') {
        toggleSessionMenu(sid)
        return
      }

      let direction: 'next' | 'prev' | 'first' | 'last' | null = null
      if (event.key === 'ArrowDown') direction = 'next'
      else if (event.key === 'ArrowUp') direction = 'prev'
      else if (event.key === 'Home') direction = 'first'
      else if (event.key === 'End') direction = 'last'
      if (!direction) return

      event.preventDefault()
      const nextIndex = getNextMenuIndex(activeIndex, items.length, direction)
      if (nextIndex >= 0) items[nextIndex]?.focus()
    },
    [openSessionMenuId, toggleSessionMenu],
  )

  useEffect(() => {
    if (!openSessionMenuId) return
    const sid = openSessionMenuId
    const onPointerDown = (event: MouseEvent | TouchEvent) => {
      const target = event.target as HTMLElement | null
      if (target?.closest('.session-menu-wrap')) return
      setOpenSessionMenuId('')
    }
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') {
        sessionMenuTriggerRefs.current[sid]?.focus()
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
    if (!sidebarOpen) {
      setOpenSessionMenuId('')
    }
  }, [sidebarOpen])

  useEffect(() => {
    safeLocalStorageSetItem('studentSidebarOpen', sidebarOpen ? 'true' : 'false')
  }, [sidebarOpen])

  const renderedMessages = useMemo(() => {
    const cache = markdownCacheRef.current
    return messages.map((msg): RenderedMessage => {
      const cached = cache.get(msg.id)
      if (cached && cached.content === msg.content && cached.apiBase === apiBase) return { ...msg, html: cached.html }
      const html = absolutizeChartImageUrls(renderMarkdown(msg.content), apiBase)
      cache.set(msg.id, { content: msg.content, html, apiBase })
      return { ...msg, html }
    })
  }, [messages, apiBase])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  useEffect(() => {
    const el = inputRef.current
    if (!el) return
    el.style.height = '0px'
    const next = Math.min(220, Math.max(56, el.scrollHeight))
    el.style.height = `${next}px`
  }, [input, verifiedStudent, pendingChatJob?.job_id])

  useEffect(() => {
    const sid = verifiedStudent?.student_id?.trim() || ''
    if (!sid) {
      setTodayAssignment(null)
      setAssignmentError('')
      setAssignmentLoading(false)
      return
    }
    const controller = new AbortController()
    setAssignmentLoading(true)
    setAssignmentError('')
    const timer = setTimeout(async () => {
      try {
        const date = todayDate()
        const url = new URL(`${apiBase}/assignment/today`)
        url.searchParams.set('student_id', sid)
        url.searchParams.set('date', date)
        url.searchParams.set('auto_generate', 'true')
        url.searchParams.set('generate', 'true')
        const res = await fetch(url.toString(), { signal: controller.signal })
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `状态码 ${res.status}`)
        }
        const data = await res.json()
        setTodayAssignment(data.assignment || null)
      } catch (err: any) {
        if (err.name === 'AbortError') return
        setAssignmentError(err.message || '无法获取今日作业')
        setTodayAssignment(null)
      } finally {
        setAssignmentLoading(false)
      }
    }, 300)
    return () => {
      controller.abort()
      clearTimeout(timer)
    }
  }, [verifiedStudent, apiBase])

  useEffect(() => {
    const sid = verifiedStudent?.student_id?.trim() || ''
    if (!sid) {
      pendingRecoveredFromStorageRef.current = false
      setPendingChatJob(null)
      return
    }
    const key = `${PENDING_CHAT_KEY_PREFIX}${sid}`
    try {
      const raw = safeLocalStorageGetItem(key)
      if (!raw) {
        pendingRecoveredFromStorageRef.current = false
        setPendingChatJob(null)
        return
      }
      const parsed = JSON.parse(raw) as PendingChatJob
      pendingRecoveredFromStorageRef.current = Boolean(parsed?.job_id)
      setPendingChatJob(parsed)
    } catch {
      pendingRecoveredFromStorageRef.current = false
      setPendingChatJob(null)
    }
  }, [verifiedStudent?.student_id])

  useEffect(() => {
    const sid = verifiedStudent?.student_id?.trim() || ''
    if (!sid) {
      setRecentCompletedReplies([])
      return
    }
    const key = `${RECENT_COMPLETION_KEY_PREFIX}${sid}`
    const recentReplies = parseRecentCompletedReplies(safeLocalStorageGetItem(key))
    if (!recentReplies.length) {
      safeLocalStorageRemoveItem(key)
      setRecentCompletedReplies([])
      return
    }
    setRecentCompletedReplies(recentReplies)
  }, [verifiedStudent?.student_id])

  useEffect(() => {
    const sid = verifiedStudent?.student_id?.trim() || ''
    if (!sid) return
    const key = `${PENDING_CHAT_KEY_PREFIX}${sid}`
    try {
      if (pendingChatJob) safeLocalStorageSetItem(key, JSON.stringify(pendingChatJob))
      else safeLocalStorageRemoveItem(key)
    } catch {
      // ignore storage errors
    }
  }, [pendingChatJob, verifiedStudent?.student_id])

  useEffect(() => {
    const sid = verifiedStudent?.student_id?.trim() || ''
    if (!sid) return
    const key = `${RECENT_COMPLETION_KEY_PREFIX}${sid}`
    try {
      if (recentCompletedReplies.length) {
        safeLocalStorageSetItem(key, JSON.stringify(recentCompletedReplies))
      } else {
        safeLocalStorageRemoveItem(key)
      }
    } catch {
      // ignore storage errors
    }
  }, [recentCompletedReplies, verifiedStudent?.student_id])

  useEffect(() => {
    if (typeof window === 'undefined') return
    const sid = verifiedStudent?.student_id?.trim() || ''

    const samePendingJob = (a: PendingChatJob | null, b: PendingChatJob | null) => {
      if (!a && !b) return true
      if (!a || !b) return false
      return (
        a.job_id === b.job_id &&
        a.request_id === b.request_id &&
        a.placeholder_id === b.placeholder_id &&
        a.user_text === b.user_text &&
        a.session_id === b.session_id &&
        Number(a.created_at) === Number(b.created_at)
      )
    }

    const sameRecentReplies = (a: RecentCompletedReply[], b: RecentCompletedReply[]) => {
      if (a.length !== b.length) return false
      for (let index = 0; index < a.length; index += 1) {
        if (recentCompletionKeyOf(a[index]) !== recentCompletionKeyOf(b[index])) return false
      }
      return true
    }

    const clearVerifiedState = () => {
      setVerifiedStudent((prev) => (prev ? null : prev))
      setVerifyOpen(true)
      pendingRecoveredFromStorageRef.current = false
      if (pendingChatJobRef.current) {
        setPendingChatJob(null)
      }
      if (recentCompletedRepliesRef.current.length) {
        setRecentCompletedReplies([])
      }
      setSending(false)
    }

    const syncFromStorageSnapshot = () => {
      const rawVerified = safeLocalStorageGetItem('verifiedStudent')
      if (!rawVerified) {
        clearVerifiedState()
        return
      }

      let parsedVerified: VerifiedStudent
      try {
        parsedVerified = JSON.parse(rawVerified) as VerifiedStudent
      } catch {
        clearVerifiedState()
        return
      }

      const nextSid = String(parsedVerified?.student_id || '').trim()
      if (!nextSid) {
        clearVerifiedState()
        return
      }

      if (nextSid !== sid) {
        setVerifiedStudent((prev) => {
          const prevSid = String(prev?.student_id || '').trim()
          if (prevSid === nextSid) return prev
          return parsedVerified
        })
        return
      }

      const pendingKey = `${PENDING_CHAT_KEY_PREFIX}${sid}`
      let nextPending: PendingChatJob | null = null
      try {
        const rawPending = safeLocalStorageGetItem(pendingKey)
        if (rawPending) {
          const parsedPending = JSON.parse(rawPending) as PendingChatJob
          if (String(parsedPending?.job_id || '').trim()) {
            nextPending = parsedPending
          }
        }
      } catch {
        nextPending = null
      }

      if (!samePendingJob(pendingChatJobRef.current, nextPending)) {
        pendingRecoveredFromStorageRef.current = false
        setPendingChatJob(nextPending)
        if (!nextPending) setSending(false)
      }

      const recentCompletionKey = `${RECENT_COMPLETION_KEY_PREFIX}${sid}`
      const nextRecentReplies = parseRecentCompletedReplies(safeLocalStorageGetItem(recentCompletionKey))
      if (!nextRecentReplies.length) {
        safeLocalStorageRemoveItem(recentCompletionKey)
      }
      if (!sameRecentReplies(recentCompletedRepliesRef.current, nextRecentReplies)) {
        setRecentCompletedReplies(nextRecentReplies)
      }
    }

    const handleStorage = (event: StorageEvent) => {
      if (event.storageArea && event.storageArea !== window.localStorage) return
      const pendingKey = sid ? `${PENDING_CHAT_KEY_PREFIX}${sid}` : ''
      const recentCompletionKey = sid ? `${RECENT_COMPLETION_KEY_PREFIX}${sid}` : ''
      if (event.key && event.key !== 'verifiedStudent' && event.key !== pendingKey && event.key !== recentCompletionKey) {
        return
      }
      syncFromStorageSnapshot()
    }

    const handleFocusOrVisibility = () => {
      syncFromStorageSnapshot()
    }

    syncFromStorageSnapshot()
    window.addEventListener('storage', handleStorage)
    window.addEventListener('focus', handleFocusOrVisibility)
    document.addEventListener('visibilitychange', handleFocusOrVisibility)
    const syncTimer = window.setInterval(syncFromStorageSnapshot, 1200)

    return () => {
      window.removeEventListener('storage', handleStorage)
      window.removeEventListener('focus', handleFocusOrVisibility)
      document.removeEventListener('visibilitychange', handleFocusOrVisibility)
      window.clearInterval(syncTimer)
    }
  }, [verifiedStudent?.student_id])

  useEffect(() => {
    if (!pendingChatJob?.job_id) return
    if (!activeSessionId || pendingChatJob.session_id !== activeSessionId) return
    setMessages((prev) => {
      const base = stripTransientPendingBubbles(prev)
      const hasUserText = pendingChatJob.user_text
        ? base.some((m) => m.role === 'user' && m.content === pendingChatJob.user_text)
        : true
      const hasPlaceholder = base.some((m) => m.id === pendingChatJob.placeholder_id)
      const next = [...base]
      if (!hasUserText && pendingChatJob.user_text) {
        next.push({ id: makeId(), role: 'user' as const, content: pendingChatJob.user_text, time: nowTime() })
      }
      if (!hasPlaceholder) {
        next.push({ id: pendingChatJob.placeholder_id, role: 'assistant' as const, content: '正在恢复上一条回复…', time: nowTime() })
      }
      return next
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSessionId, pendingChatJob?.job_id, pendingChatJob?.session_id])

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
          const resolvedReply = data.reply || '已收到。'
          setMessages((prev) => {
            const base = stripTransientPendingBubbles(prev)
            const hasUserText = pendingChatJob.user_text
              ? base.some((m) => m.role === 'user' && m.content === pendingChatJob.user_text)
              : true
            const hasPlaceholder = base.some((m) => m.id === pendingChatJob.placeholder_id)
            const next = [...base]
            if (!hasUserText && pendingChatJob.user_text) {
              next.push({ id: makeId(), role: 'user' as const, content: pendingChatJob.user_text, time: nowTime() })
            }
            if (!hasPlaceholder) {
              next.push({ id: pendingChatJob.placeholder_id, role: 'assistant' as const, content: '正在恢复上一条回复…', time: nowTime() })
            }
            return next.map((m) =>
              m.id === pendingChatJob.placeholder_id ? { ...m, content: resolvedReply, time: nowTime() } : m,
            )
          })
          if (pendingChatJob.session_id) {
            const nextRecent: RecentCompletedReply = {
              session_id: pendingChatJob.session_id,
              user_text: pendingChatJob.user_text || '',
              reply_text: resolvedReply,
              completed_at: Date.now(),
            }
            setRecentCompletedReplies((prev) => normalizeRecentCompletedReplies([...prev, nextRecent]))
          }
          skipAutoSessionLoadIdRef.current = pendingChatJob.session_id || ''
          setPendingChatJob(null)
          setSending(false)
          void refreshSessions()
          return 'stop'
        }
        if (data.status === 'failed' || data.status === 'cancelled') {
          const msg = data.error_detail || data.error || '请求失败'
          setMessages((prev) => {
            const base = stripTransientPendingBubbles(prev)
            const hasUserText = pendingChatJob.user_text
              ? base.some((m) => m.role === 'user' && m.content === pendingChatJob.user_text)
              : true
            const hasPlaceholder = base.some((m) => m.id === pendingChatJob.placeholder_id)
            const next = [...base]
            if (!hasUserText && pendingChatJob.user_text) {
              next.push({ id: makeId(), role: 'user' as const, content: pendingChatJob.user_text, time: nowTime() })
            }
            if (!hasPlaceholder) {
              next.push({ id: pendingChatJob.placeholder_id, role: 'assistant' as const, content: '正在恢复上一条回复…', time: nowTime() })
            }
            return next.map((m) =>
              m.id === pendingChatJob.placeholder_id ? { ...m, content: `抱歉，请求失败：${msg}`, time: nowTime() } : m,
            )
          })
          skipAutoSessionLoadIdRef.current = pendingChatJob.session_id || ''
          setPendingChatJob(null)
          setSending(false)
          return 'stop'
        }
        return 'continue'
      },
      (err) => {
        const msg = (err as any)?.message || String(err)
        setMessages((prev) => {
          const base = stripTransientPendingBubbles(prev)
          const hasUserText = pendingChatJob.user_text
            ? base.some((m) => m.role === 'user' && m.content === pendingChatJob.user_text)
            : true
          const hasPlaceholder = base.some((m) => m.id === pendingChatJob.placeholder_id)
          const next = [...base]
          if (!hasUserText && pendingChatJob.user_text) {
            next.push({ id: makeId(), role: 'user' as const, content: pendingChatJob.user_text, time: nowTime() })
          }
          if (!hasPlaceholder) {
            next.push({ id: pendingChatJob.placeholder_id, role: 'assistant' as const, content: '正在恢复上一条回复…', time: nowTime() })
          }
          return next.map((m) =>
            m.id === pendingChatJob.placeholder_id ? { ...m, content: `网络波动，正在重试…（${msg}）`, time: nowTime() } : m,
          )
        })
      },
      { kickMode: 'direct' },
    )

    return cleanup
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingChatJob?.job_id, activeSessionId, apiBase])

  const refreshSessions = async (mode: 'reset' | 'more' = 'reset') => {
    const sid = verifiedStudent?.student_id?.trim() || ''
    if (!sid) return
    if (mode === 'more' && !historyHasMore) return
    const cursor = mode === 'more' ? historyCursor : 0
    const requestNo = ++historyRequestRef.current
    setHistoryLoading(true)
    if (mode === 'reset') setHistoryError('')
    try {
      const url = new URL(`${apiBase}/student/history/sessions`)
      url.searchParams.set('student_id', sid)
      url.searchParams.set('limit', '30')
      url.searchParams.set('cursor', String(cursor))
      const res = await fetch(url.toString())
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `状态码 ${res.status}`)
      }
      const data = (await res.json()) as StudentHistorySessionsResponse
      if (requestNo !== historyRequestRef.current) return
      const serverSessions = Array.isArray(data.sessions) ? data.sessions : []
      const serverIds = new Set(serverSessions.map((item) => String(item.session_id || '').trim()).filter(Boolean))
      setLocalDraftSessionIds((prev) => prev.filter((id) => !serverIds.has(id)))
      const nextCursor = typeof data.next_cursor === 'number' ? data.next_cursor : null
      setHistoryCursor(nextCursor ?? 0)
      setHistoryHasMore(nextCursor !== null)
      if (mode === 'more') {
        setSessions((prev) => {
          const merged = [...prev]
          const existingIds = new Set(prev.map((item) => item.session_id))
          for (const item of serverSessions) {
            if (existingIds.has(item.session_id)) continue
            merged.push(item)
          }
          return merged
        })
      } else {
        setSessions((prev) => {
          const draftItems = localDraftSessionIds
            .filter((id) => !serverIds.has(id))
            .map((id) => prev.find((item) => item.session_id === id) || { session_id: id, updated_at: new Date().toISOString(), message_count: 0 })
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
  }

  const loadSessionMessages = async (sessionId: string, cursor: number, append: boolean) => {
    const sid = verifiedStudent?.student_id?.trim() || ''
    if (!sid || !sessionId) return
    const targetSessionId = String(sessionId || '').trim()
    if (!targetSessionId) return
    const requestNo = ++sessionRequestRef.current
    setSessionLoading(true)
    setSessionError('')
    try {
      const LIMIT = 80
      const url = new URL(`${apiBase}/student/history/session`)
      url.searchParams.set('student_id', sid)
      url.searchParams.set('session_id', targetSessionId)
      url.searchParams.set('cursor', String(cursor))
      url.searchParams.set('limit', String(LIMIT))
      url.searchParams.set('direction', 'backward')
      const res = await fetch(url.toString())
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `状态码 ${res.status}`)
      }
      const data = (await res.json()) as StudentHistorySessionResponse
      if (requestNo !== sessionRequestRef.current) return
      const raw = Array.isArray(data.messages) ? data.messages : []
      const mapped: Message[] = raw
        .map((m, idx) => {
          const roleRaw = String(m.role || '').toLowerCase()
          const role = roleRaw === 'assistant' ? 'assistant' : roleRaw === 'user' ? 'user' : null
          const content = typeof m.content === 'string' ? m.content : ''
          if (!role || !content) return null
          return {
            id: `hist_${targetSessionId}_${cursor}_${idx}_${m.ts || ''}`,
            role,
            content,
            time: timeFromIso(m.ts),
          } as Message
        })
        .filter(Boolean) as Message[]
      const pending = pendingChatJobRef.current
      const mergedPending: Message[] =
        pending?.job_id && pending.session_id === targetSessionId
          ? (() => {
              const base = stripTransientPendingBubbles(mapped)
              const hasUserText = pending.user_text ? base.some((item) => item.role === 'user' && item.content === pending.user_text) : true
              const hasPlaceholder = base.some((item) => item.id === pending.placeholder_id)
              const next = [...base]
              if (!hasUserText && pending.user_text) {
                next.push({ id: makeId(), role: 'user', content: pending.user_text, time: nowTime() })
              }
              if (!hasPlaceholder) {
                next.push({ id: pending.placeholder_id, role: 'assistant', content: '正在恢复上一条回复…', time: nowTime() })
              }
              return next
            })()
          : mapped

      const recentReplies = recentCompletedRepliesRef.current
      const merged: Message[] =
        recentReplies.length && !(pending?.job_id && pending.session_id === targetSessionId)
          ? (() => {
              const now = Date.now()
              const assistantHistoryCandidates = raw
                .map((item) => {
                  const roleRaw = String(item.role || '').toLowerCase()
                  const content = typeof item.content === 'string' ? item.content : ''
                  if (roleRaw !== 'assistant' || !content) return null
                  const parsedTs = typeof item.ts === 'string' ? Date.parse(item.ts) : Number.NaN
                  return {
                    content,
                    ts_ms: Number.isFinite(parsedTs) ? parsedTs : Number.NaN,
                    used: false,
                  }
                })
                .filter(Boolean) as Array<{ content: string; ts_ms: number; used: boolean }>

              const userHistoryCounts = raw.reduce<Record<string, number>>((acc, item) => {
                const roleRaw = String(item.role || '').toLowerCase()
                const content = typeof item.content === 'string' ? item.content : ''
                if (roleRaw !== 'user' || !content) return acc
                acc[content] = (acc[content] || 0) + 1
                return acc
              }, {})

              const removableKeys = new Set<string>()
              const unresolvedRecent: RecentCompletedReply[] = []

              for (const recent of [...recentReplies].sort((a, b) => a.completed_at - b.completed_at)) {
                const recentKey = recentCompletionKeyOf(recent)
                if (now - recent.completed_at > RECENT_COMPLETION_TTL_MS) {
                  removableKeys.add(recentKey)
                  continue
                }
                if (recent.session_id !== targetSessionId) continue

                let matchedIndex = assistantHistoryCandidates.findIndex((candidate) => {
                  if (candidate.used) return false
                  if (candidate.content !== recent.reply_text) return false
                  if (!Number.isFinite(candidate.ts_ms)) return false
                  return candidate.ts_ms >= recent.completed_at - RECENT_COMPLETION_TTL_MS
                })

                if (matchedIndex < 0 && recent.user_text && (userHistoryCounts[recent.user_text] || 0) > 0) {
                  matchedIndex = assistantHistoryCandidates.findIndex((candidate) => {
                    if (candidate.used) return false
                    if (candidate.content !== recent.reply_text) return false
                    return !Number.isFinite(candidate.ts_ms)
                  })
                }

                if (matchedIndex >= 0) {
                  assistantHistoryCandidates[matchedIndex].used = true
                  removableKeys.add(recentKey)
                  continue
                }

                unresolvedRecent.push(recent)
              }

              const patched = [...mergedPending]
              for (const recent of unresolvedRecent) {
                if (recent.user_text) {
                  patched.push({ id: makeId(), role: 'user', content: recent.user_text, time: nowTime() })
                }
                patched.push({ id: makeId(), role: 'assistant', content: recent.reply_text, time: nowTime() })
              }

              if (removableKeys.size > 0) {
                setRecentCompletedReplies((prev) => prev.filter((item) => !removableKeys.has(recentCompletionKeyOf(item))))
              }
              return patched
            })()
          : mergedPending
      const next = typeof data.next_cursor === 'number' ? data.next_cursor : 0
      setSessionCursor(next)
      setSessionHasMore(merged.length >= 1 && next > 0)
      if (append) {
        setMessages((prev) => [...merged, ...prev])
      } else {
        setMessages(
          merged.length
            ? merged
            : [
                {
                  id: makeId(),
                  role: 'assistant',
                  content: STUDENT_NEW_SESSION_MESSAGE,
                  time: nowTime(),
                },
              ]
        )
      }
    } catch (err: any) {
      if (requestNo !== sessionRequestRef.current) return
      setSessionError(err.message || String(err))
    } finally {
      if (requestNo !== sessionRequestRef.current) return
      setSessionLoading(false)
    }
  }

  useEffect(() => {
    if (!verifiedStudent?.student_id) return
    void refreshSessions()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [verifiedStudent?.student_id, apiBase])

  useEffect(() => {
    if (!verifiedStudent?.student_id) return
    const timer = window.setInterval(() => {
      void refreshSessions()
    }, 30000)
    return () => window.clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [verifiedStudent?.student_id, apiBase])

  useEffect(() => {
    const sid = verifiedStudent?.student_id?.trim() || ''
    if (!sid) {
      setSessions([])
      setHistoryCursor(0)
      setHistoryHasMore(false)
      setSessionTitleMap({})
      setDeletedSessionIds([])
      setLocalDraftSessionIds([])
      setViewStateUpdatedAt(new Date().toISOString())
      setViewStateSyncReady(false)
      lastSyncedViewStateSignatureRef.current = ''
      return
    }
    setSessions([])
    setHistoryCursor(0)
    setHistoryHasMore(false)
    const localState = readStudentLocalViewState(sid)
    const localDraftSessionIds = readStudentLocalDraftSessionIds(sid)
    applyingViewStateRef.current = true
    setSessionTitleMap(localState.title_map)
    setDeletedSessionIds(localState.hidden_ids)
    setLocalDraftSessionIds(localDraftSessionIds)
    setActiveSession(localState.active_session_id || '')
    setViewStateUpdatedAt(localState.updated_at || '')
    lastSyncedViewStateSignatureRef.current = buildSessionViewStateSignature(localState)
    setViewStateSyncReady(false)

    let cancelled = false
    const bootstrap = async () => {
      try {
        const res = await fetch(`${apiBase}/student/session/view-state?student_id=${encodeURIComponent(sid)}`)
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `状态码 ${res.status}`)
        }
        const data = await res.json()
        const remoteState = normalizeSessionViewStatePayload(data?.state || {})
        const cmp = compareSessionViewStateUpdatedAt(remoteState.updated_at, localState.updated_at)
        if (cmp > 0) {
          if (cancelled) return
          applyingViewStateRef.current = true
          setSessionTitleMap(remoteState.title_map)
          setDeletedSessionIds(remoteState.hidden_ids)
          if (remoteState.active_session_id) {
            setActiveSession(remoteState.active_session_id)
          }
          setViewStateUpdatedAt(remoteState.updated_at || new Date().toISOString())
          lastSyncedViewStateSignatureRef.current = buildSessionViewStateSignature(remoteState)
          return
        }
        const payload = normalizeSessionViewStatePayload({
          ...localState,
          active_session_id: '',
        })
        const saveRes = await fetch(`${apiBase}/student/session/view-state`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ student_id: sid, state: payload }),
        })
        if (!saveRes.ok) {
          const text = await saveRes.text()
          throw new Error(text || `状态码 ${saveRes.status}`)
        }
        const savedData = await saveRes.json()
        const savedState = normalizeSessionViewStatePayload(savedData?.state || payload)
        if (cancelled) return
        lastSyncedViewStateSignatureRef.current = buildSessionViewStateSignature(savedState)
        if (savedState.updated_at && savedState.updated_at !== payload.updated_at) {
          applyingViewStateRef.current = true
          setViewStateUpdatedAt(savedState.updated_at)
        }
      } catch {
        lastSyncedViewStateSignatureRef.current = buildSessionViewStateSignature(localState)
      } finally {
        if (!cancelled) setViewStateSyncReady(true)
      }
    }
    void bootstrap()
    return () => {
      cancelled = true
    }
  }, [apiBase, verifiedStudent?.student_id])

  useEffect(() => {
    const sid = verifiedStudent?.student_id?.trim() || ''
    if (!sid || !viewStateSyncReady) return
    currentViewStateRef.current = currentViewState
    safeLocalStorageSetItem(`${STUDENT_SESSION_VIEW_STATE_KEY_PREFIX}${sid}`, JSON.stringify(currentViewState))
    safeLocalStorageSetItem(`studentSessionTitles:${sid}`, JSON.stringify(currentViewState.title_map))
    safeLocalStorageSetItem(`studentDeletedSessions:${sid}`, JSON.stringify(currentViewState.hidden_ids))
    if (activeSessionId) safeLocalStorageSetItem(`studentActiveSession:${sid}`, activeSessionId)
    else safeLocalStorageRemoveItem(`studentActiveSession:${sid}`)
  }, [activeSessionId, currentViewState, verifiedStudent?.student_id, viewStateSyncReady])

  useEffect(() => {
    const sid = verifiedStudent?.student_id?.trim() || ''
    if (!sid) return
    try {
      safeLocalStorageSetItem(`${STUDENT_LOCAL_DRAFT_SESSIONS_KEY_PREFIX}${sid}`, JSON.stringify(localDraftSessionIds))
    } catch {
      // ignore localStorage write errors
    }
  }, [localDraftSessionIds, verifiedStudent?.student_id])

  useEffect(() => {
    const sid = verifiedStudent?.student_id?.trim() || ''
    if (!sid || !viewStateSyncReady) return
    if (applyingViewStateRef.current) {
      applyingViewStateRef.current = false
      return
    }
    setViewStateUpdatedAt(new Date().toISOString())
  }, [deletedSessionIds, sessionTitleMap, verifiedStudent?.student_id, viewStateSyncReady])

  useEffect(() => {
    const sid = verifiedStudent?.student_id?.trim() || ''
    if (!sid || !viewStateSyncReady) return
    const signature = buildSessionViewStateSignature(currentViewState)
    if (signature === lastSyncedViewStateSignatureRef.current) return
    const timer = window.setTimeout(async () => {
      try {
        const payload = normalizeSessionViewStatePayload({
          ...currentViewState,
          active_session_id: '',
        })
        const res = await fetch(`${apiBase}/student/session/view-state`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ student_id: sid, state: payload }),
        })
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `状态码 ${res.status}`)
        }
        const data = await res.json()
        const savedState = normalizeSessionViewStatePayload(data?.state || payload)
        lastSyncedViewStateSignatureRef.current = buildSessionViewStateSignature(savedState)
        if (savedState.updated_at && savedState.updated_at !== payload.updated_at) {
          applyingViewStateRef.current = true
          setViewStateUpdatedAt(savedState.updated_at)
        }
      } catch {
        // keep local state and retry on next mutation
      }
    }, 260)
    return () => window.clearTimeout(timer)
  }, [apiBase, currentViewState, verifiedStudent?.student_id, viewStateSyncReady])

  useEffect(() => {
    activeSessionRef.current = activeSessionId
  }, [activeSessionId])

  useEffect(() => {
    pendingChatJobRef.current = pendingChatJob
  }, [pendingChatJob])

  useEffect(() => {
    recentCompletedRepliesRef.current = recentCompletedReplies
  }, [recentCompletedReplies])

  useEffect(() => {
    if (!pendingChatJob?.job_id) return
    if (!pendingRecoveredFromStorageRef.current) return
    pendingRecoveredFromStorageRef.current = false
    if (pendingChatJob.session_id && pendingChatJob.session_id !== activeSessionId) {
      setActiveSession(pendingChatJob.session_id)
    }
  }, [activeSessionId, pendingChatJob?.job_id, pendingChatJob?.session_id, setActiveSession])

  useEffect(() => {
    if (!verifiedStudent?.student_id) return
    if (!viewStateSyncReady) return
    if (pendingChatJob?.job_id) return
    if (activeSessionId) return
    const next = todayAssignment?.assignment_id || `general_${todayDate()}`
    setActiveSession(next)
  }, [verifiedStudent?.student_id, todayAssignment?.assignment_id, pendingChatJob?.job_id, activeSessionId, viewStateSyncReady, setActiveSession])

  useEffect(() => {
    if (!verifiedStudent?.student_id) return
    if (!activeSessionId) return
    if (skipAutoSessionLoadIdRef.current) {
      const skippedSessionId = skipAutoSessionLoadIdRef.current
      skipAutoSessionLoadIdRef.current = ''
      if (skippedSessionId === activeSessionId) return
    }
    if (pendingChatJob?.job_id) {
      if (pendingChatJob.session_id === activeSessionId) return
      void loadSessionMessages(activeSessionId, -1, false)
      return
    }
    if (sending) return
    void loadSessionMessages(activeSessionId, -1, false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSessionId, verifiedStudent?.student_id, apiBase, pendingChatJob?.job_id, pendingChatJob?.session_id, forceSessionLoadToken])

  const updateMessage = (id: string, patch: Partial<Message>) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...patch } : m)))
  }

  const composerHint = useMemo(() => {
    if (!verifiedStudent) return '请先完成身份验证'
    if (pendingChatJob?.job_id) return '正在生成回复，请稍候...'
    if (sending) return '正在提交请求...'
    return 'Enter 发送 · Shift+Enter 换行'
  }, [pendingChatJob?.job_id, sending, verifiedStudent])

  const handleInputKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter') return
    if (event.shiftKey) return
    if ((event.nativeEvent as any)?.isComposing) return
    event.preventDefault()
    if (!verifiedStudent) return
    if (sending || pendingChatJob?.job_id) return
    if (!input.trim()) return
    event.currentTarget.form?.requestSubmit()
  }

  const withStudentSendLock = useCallback(
    async (studentId: string, task: () => Promise<void>) => {
      const sid = String(studentId || '').trim()
      if (!sid) return false
      const lockManager = typeof navigator !== 'undefined' ? (navigator as any).locks : null
      if (lockManager?.request) {
        const acquired = await lockManager.request(
          `student-send-lock:${sid}`,
          { ifAvailable: true, mode: 'exclusive' },
          async (lock: any) => {
            if (!lock) return false
            await task()
            return true
          },
        )
        return Boolean(acquired)
      }

      const lockKey = `${SEND_LOCK_KEY_PREFIX}${sid}`
      const owner = `slock_${Date.now()}_${Math.random().toString(16).slice(2)}`
      const parseFallbackLock = (raw: string | null): { owner: string; expires_at: number } | null => {
        if (!raw) return null
        try {
          const parsed = JSON.parse(raw) as { owner?: string; expires_at?: number }
          const parsedOwner = String(parsed?.owner || '').trim()
          const parsedExpiresAt = Number(parsed?.expires_at || 0)
          if (!parsedOwner || !Number.isFinite(parsedExpiresAt)) return null
          return { owner: parsedOwner, expires_at: parsedExpiresAt }
        } catch {
          return null
        }
      }

      const now = Date.now()
      const existing = parseFallbackLock(safeLocalStorageGetItem(lockKey))
      if (existing && existing.expires_at > now) {
        return false
      }
      if (existing && existing.expires_at <= now) {
        safeLocalStorageRemoveItem(lockKey)
      }

      const wrote = safeLocalStorageSetItem(
        lockKey,
        JSON.stringify({
          owner,
          expires_at: now + FALLBACK_SEND_LOCK_TTL_MS,
        }),
      )
      if (!wrote) return false

      const settleStartedAt = Date.now()
      while (Date.now() - settleStartedAt < FALLBACK_SEND_LOCK_SETTLE_MS) {
        await new Promise((resolve) => window.setTimeout(resolve, 24))
        const observed = parseFallbackLock(safeLocalStorageGetItem(lockKey))
        if (!observed || observed.owner !== owner || observed.expires_at <= Date.now()) {
          return false
        }
      }

      const latest = parseFallbackLock(safeLocalStorageGetItem(lockKey))
      if (!latest || latest.owner !== owner || latest.expires_at <= Date.now()) {
        return false
      }

      const extendFallbackLock = () => {
        const current = parseFallbackLock(safeLocalStorageGetItem(lockKey))
        if (!current || current.owner !== owner) return false
        const renewed = safeLocalStorageSetItem(
          lockKey,
          JSON.stringify({
            owner,
            expires_at: Date.now() + FALLBACK_SEND_LOCK_TTL_MS,
          }),
        )
        if (!renewed) return false
        const observed = parseFallbackLock(safeLocalStorageGetItem(lockKey))
        return Boolean(observed && observed.owner === owner && observed.expires_at > Date.now())
      }

      if (!extendFallbackLock()) {
        return false
      }

      let renewTimer: number | null = window.setInterval(() => {
        if (extendFallbackLock()) return
        if (renewTimer !== null) {
          window.clearInterval(renewTimer)
          renewTimer = null
        }
      }, FALLBACK_SEND_LOCK_RENEW_INTERVAL_MS)

      try {
        await task()
        return true
      } finally {
        if (renewTimer !== null) {
          window.clearInterval(renewTimer)
          renewTimer = null
        }
        const current = parseFallbackLock(safeLocalStorageGetItem(lockKey))
        if (current?.owner === owner) {
          safeLocalStorageRemoveItem(lockKey)
        }
      }
    },
    [],
  )

  const handleSend = async (event: FormEvent) => {
    event.preventDefault()
    if (!verifiedStudent) {
      setVerifyError('请先填写姓名并完成验证。')
      setVerifyOpen(true)
      return
    }
    if (pendingChatJob?.job_id) return
    const trimmed = input.trim()
    if (!trimmed) return

    const studentId = verifiedStudent.student_id
    const pendingKey = `${PENDING_CHAT_KEY_PREFIX}${studentId}`

    const syncPendingFromStorage = () => {
      try {
        const raw = safeLocalStorageGetItem(pendingKey)
        if (!raw) {
          pendingRecoveredFromStorageRef.current = false
          setPendingChatJob(null)
          setSending(false)
          return false
        }
        const parsed = JSON.parse(raw) as PendingChatJob
        pendingRecoveredFromStorageRef.current = false
        setPendingChatJob(parsed)
        setSending(false)
        return true
      } catch {
        pendingRecoveredFromStorageRef.current = false
        setPendingChatJob(null)
        setSending(false)
        return false
      }
    }

    const waitPendingSync = async (timeoutMs = 2500) => {
      setSending(true)
      const started = Date.now()
      while (Date.now() - started < timeoutMs) {
        if (syncPendingFromStorage()) return true
        await new Promise((resolve) => window.setTimeout(resolve, 80))
      }
      setSending(false)
      return false
    }

    let startedSubmission = false

    const lockAcquired = await withStudentSendLock(studentId, async () => {
      if (syncPendingFromStorage()) return

      startedSubmission = true
      const sessionId = activeSessionId || todayAssignment?.assignment_id || `general_${todayDate()}`
      if (!activeSessionId) setActiveSession(sessionId)
      const requestId = `schat_${studentId}_${Date.now()}_${Math.random().toString(16).slice(2)}`
      const placeholderId = `asst_${Date.now()}_${Math.random().toString(16).slice(2)}`

      setMessages((prev) => {
        const next = stripTransientPendingBubbles(prev)
        return [
          ...next,
          { id: makeId(), role: 'user', content: trimmed, time: nowTime() },
          { id: placeholderId, role: 'assistant', content: '正在生成…', time: nowTime() },
        ]
      })
      setInput('')

      const contextMessages = [...messages, { id: 'temp', role: 'user' as const, content: trimmed, time: '' }]
        .slice(-40)
        .map((msg) => ({ role: msg.role, content: msg.content }))

      setSending(true)
      try {
        const inferredAssignmentId =
          sessionId && !sessionId.startsWith('general_')
            ? sessionId
            : todayAssignment?.assignment_id && sessionId === todayAssignment.assignment_id
              ? todayAssignment.assignment_id
              : undefined
        const res = await fetch(`${apiBase}/chat/start`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            request_id: requestId,
            session_id: sessionId,
            messages: contextMessages,
            role: 'student',
            student_id: studentId,
            assignment_id: inferredAssignmentId,
            assignment_date: todayDate(),
          }),
        })
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `状态码 ${res.status}`)
        }
        const data = (await res.json()) as ChatStartResult
        if (!data?.job_id) throw new Error('任务编号缺失')
        const nextPending: PendingChatJob = {
          job_id: data.job_id,
          request_id: requestId,
          placeholder_id: placeholderId,
          user_text: trimmed,
          session_id: sessionId,
          created_at: Date.now(),
        }
        pendingRecoveredFromStorageRef.current = false
        safeLocalStorageSetItem(pendingKey, JSON.stringify(nextPending))
        setPendingChatJob(nextPending)
      } catch (err: any) {
        updateMessage(placeholderId, { content: `抱歉，请求失败：${err.message || err}`, time: nowTime() })
        setSending(false)
        skipAutoSessionLoadIdRef.current = sessionId
        pendingRecoveredFromStorageRef.current = false
        setPendingChatJob(null)
      }
    })

    if (!lockAcquired) {
      await waitPendingSync()
      return
    }

    if (!startedSubmission) {
      syncPendingFromStorage()
    }
  }

  const handleVerify = async (event: FormEvent) => {
    event.preventDefault()
    const name = nameInput.trim()
    const className = classInput.trim()
    setVerifyError('')
    if (!name) {
      setVerifyError('请先输入姓名。')
      return
    }
    setVerifying(true)
    try {
      const res = await fetch(`${apiBase}/student/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, class_name: className || undefined }),
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `状态码 ${res.status}`)
      }
      const data = (await res.json()) as VerifyResponse
      if (data.ok && data.student) {
        setVerifiedStudent(data.student as VerifiedStudent)
        setVerifyOpen(false)
        setVerifyError('')
      } else if (data.error === 'multiple') {
        setVerifyError('同名学生，请补充班级。')
      } else {
        setVerifyError(data.message || '未找到该学生，请检查姓名或班级。')
      }
    } catch (err: any) {
      setVerifyError(err.message || String(err))
    } finally {
      setVerifying(false)
    }
  }

  const getSessionTitle = useCallback(
    (sessionId: string) => {
      const sid = String(sessionId || '').trim()
      if (!sid) return '未命名会话'
      return sessionTitleMap[sid] || sid
    },
    [sessionTitleMap],
  )

  const visibleSessions = useMemo(() => {
    const archived = new Set(deletedSessionIds)
    const q = historyQuery.trim().toLowerCase()
    return sessions.filter((item) => {
      const sid = String(item.session_id || '').trim()
      if (!sid) return false
      const title = (sessionTitleMap[sid] || '').toLowerCase()
      const preview = (item.preview || '').toLowerCase()
      const matched = !q || sid.toLowerCase().includes(q) || title.includes(q) || preview.includes(q)
      if (!matched) return false
      return showArchivedSessions ? archived.has(sid) : !archived.has(sid)
    })
  }, [sessions, deletedSessionIds, historyQuery, sessionTitleMap, showArchivedSessions])

  const groupedSessions = useMemo(() => {
    const buckets = new Map<string, SessionGroup<StudentHistorySession>>()
    for (const item of visibleSessions) {
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
  }, [visibleSessions])

  const closeSidebarOnMobile = useCallback(() => {
    if (typeof window === 'undefined') return
    if (window.matchMedia('(max-width: 900px)').matches) {
      setSidebarOpen(false)
    }
  }, [])

  const selectStudentSession = useCallback(
    (sessionId: string) => {
      const sid = String(sessionId || '').trim()
      if (!sid) return
      setForceSessionLoadToken((prev) => prev + 1)
      setActiveSession(sid)
      setSessionCursor(-1)
      setSessionHasMore(false)
      setSessionError('')
      setOpenSessionMenuId('')
      closeSidebarOnMobile()
    },
    [closeSidebarOnMobile, setActiveSession],
  )

  const resetVerification = useCallback(() => {
    setVerifiedStudent(null)
    setNameInput('')
    setClassInput('')
    setVerifyError('')
    setVerifyOpen(true)
  }, [])

  const startNewStudentSession = useCallback(() => {
    const next = `general_${todayDate()}_${Math.random().toString(16).slice(2, 6)}`
    sessionRequestRef.current += 1
    setLocalDraftSessionIds((prev) => (prev.includes(next) ? prev : [next, ...prev]))
    setShowArchivedSessions(false)
    setActiveSession(next)
    setSessionCursor(-1)
    setSessionHasMore(false)
    setSessionError('')
    setOpenSessionMenuId('')
    setPendingChatJob(null)
    setSending(false)
    setInput('')
    setSessions((prev) => {
      if (prev.some((item) => item.session_id === next)) return prev
      const nowIso = new Date().toISOString()
      return [
        { session_id: next, updated_at: nowIso, message_count: 0, preview: '' },
        ...prev,
      ]
    })
    setMessages([
      {
        id: makeId(),
        role: 'assistant',
        content: STUDENT_NEW_SESSION_MESSAGE,
        time: nowTime(),
      },
    ])
    closeSidebarOnMobile()
  }, [closeSidebarOnMobile, setActiveSession])

  const renameSession = useCallback(
    (sessionId: string) => {
      const sid = String(sessionId || '').trim()
      if (!sid) return
      setRenameDialogSessionId(sid)
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
    const triggerId = `student-session-menu-${domSafe}-trigger`
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
    setArchiveDialogSessionId(null)
  }, [])

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
      const next = visibleSessions.find((item) => item.session_id !== sid)?.session_id
      if (next) {
        setActiveSession(next)
        setSessionCursor(-1)
        setSessionHasMore(false)
        setSessionError('')
      } else {
        startNewStudentSession()
      }
    }
  }, [activeSessionId, archiveDialogSessionId, deletedSessionIds, startNewStudentSession, visibleSessions, setActiveSession])

  const archiveDialogIsArchived = archiveDialogSessionId ? deletedSessionIds.includes(archiveDialogSessionId) : false
  const archiveDialogActionLabel = archiveDialogIsArchived ? '恢复' : '归档'

  return (
    <div className="app">
      <StudentTopbar verifiedStudent={verifiedStudent} sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} startNewStudentSession={startNewStudentSession} />
      <StudentSessionShell
        sidebarOpen={sidebarOpen}
        workbench={
          <StudentWorkbench>
            <StudentSessionSidebar
              apiBase={apiBase}
              sidebarOpen={sidebarOpen}
              setSidebarOpen={setSidebarOpen}
              verifiedStudent={verifiedStudent}
              historyLoading={historyLoading}
              historyError={historyError}
              historyHasMore={historyHasMore}
              refreshSessions={refreshSessions}
              showArchivedSessions={showArchivedSessions}
              setShowArchivedSessions={setShowArchivedSessions}
              historyQuery={historyQuery}
              setHistoryQuery={setHistoryQuery}
              visibleSessionCount={visibleSessions.length}
              groupedSessions={groupedSessions}
              deletedSessionIds={deletedSessionIds}
              activeSessionId={activeSessionId}
              onSelectSession={selectStudentSession}
              getSessionTitle={getSessionTitle}
              openSessionMenuId={openSessionMenuId}
              toggleSessionMenu={toggleSessionMenu}
              handleSessionMenuTriggerKeyDown={handleSessionMenuTriggerKeyDown}
              handleSessionMenuKeyDown={handleSessionMenuKeyDown}
              setSessionMenuTriggerRef={setSessionMenuTriggerRef}
              setSessionMenuRef={setSessionMenuRef}
              renameSession={renameSession}
              toggleSessionArchive={toggleSessionArchive}
              sessionHasMore={sessionHasMore}
              sessionLoading={sessionLoading}
              sessionCursor={sessionCursor}
              loadSessionMessages={loadSessionMessages}
              sessionError={sessionError}
              verifyOpen={verifyOpen}
              setVerifyOpen={setVerifyOpen}
              handleVerify={handleVerify}
              nameInput={nameInput}
              setNameInput={setNameInput}
              classInput={classInput}
              setClassInput={setClassInput}
              verifying={verifying}
              verifyError={verifyError}
              todayAssignment={todayAssignment}
              assignmentLoading={assignmentLoading}
              assignmentError={assignmentError}
              todayDate={todayDate}
              resetVerification={resetVerification}
              startNewStudentSession={startNewStudentSession}
              renameDialogSessionId={renameDialogSessionId}
              archiveDialogSessionId={archiveDialogSessionId}
              archiveDialogActionLabel={archiveDialogActionLabel}
              archiveDialogIsArchived={archiveDialogIsArchived}
              cancelRenameDialog={cancelRenameDialog}
              confirmRenameDialog={confirmRenameDialog}
              cancelArchiveDialog={cancelArchiveDialog}
              confirmArchiveDialog={confirmArchiveDialog}
            />
          </StudentWorkbench>
        }
        chatPanel={
          <StudentChatPanel
            renderedMessages={renderedMessages}
            sending={sending}
            pendingChatJobId={pendingChatJob?.job_id || ''}
            verifiedStudent={verifiedStudent}
            endRef={endRef}
            inputRef={inputRef}
            input={input}
            setInput={setInput}
            handleInputKeyDown={handleInputKeyDown}
            handleSend={handleSend}
            composerHint={composerHint}
          />
        }
      />
    </div>
  )
}
