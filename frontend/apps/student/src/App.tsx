import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { makeId } from '../../shared/id'
import { renderMarkdown, absolutizeChartImageUrls } from '../../shared/markdown'
import { startVisibilityAwareBackoffPolling } from '../../shared/visibilityBackoffPolling'
import { safeLocalStorageGetItem, safeLocalStorageRemoveItem, safeLocalStorageSetItem } from '../../shared/storage'
import { nowTime, timeFromIso } from '../../shared/time'
import { useSmartAutoScroll, useScrollPositionLock, evictOldestEntries } from '../../shared/useSmartAutoScroll'
import { useWheelScrollZone } from '../../shared/useWheelScrollZone'
import { stripTransientPendingBubbles } from './features/chat/pendingOverlay'
import { parsePendingChatJobFromStorage, PENDING_CHAT_MAX_AGE_MS } from './features/chat/pendingChatJob'
import { useStudentSendFlow } from './features/chat/useStudentSendFlow'
import StudentChatPanel from './features/chat/StudentChatPanel'
import StudentSessionSidebar from './features/chat/StudentSessionSidebar'
import StudentTopbar from './features/layout/StudentTopbar'
import StudentSessionShell from './features/session/StudentSessionShell'
import { useStudentSessionActions } from './features/session/useStudentSessionActions'
import { useStudentSessionSidebarState } from './features/session/useStudentSessionSidebarState'
import { useStudentSessionViewStateSync } from './features/session/useStudentSessionViewStateSync'
import StudentWorkbench from './features/workbench/StudentWorkbench'
import type {
  AssignmentDetail,
  ChatJobStatus,
  Message,
  PendingChatJob,
  RenderedMessage,
  StudentHistorySession,
  StudentHistorySessionResponse,
  StudentHistorySessionsResponse,
  VerifiedStudent,
  VerifyResponse,
} from './appTypes'
import 'katex/dist/katex.min.css'

const PENDING_CHAT_KEY_PREFIX = 'studentPendingChatJob:'
const RECENT_COMPLETION_KEY_PREFIX = 'studentRecentCompletion:'
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

const isAbortError = (error: unknown): boolean => {
  if (error instanceof DOMException) return error.name === 'AbortError'
  if (!error || typeof error !== 'object') return false
  return (error as { name?: unknown }).name === 'AbortError'
}

const toErrorMessage = (error: unknown, fallback = '请求失败') => {
  if (error instanceof Error) {
    const message = error.message.trim()
    if (message) return message
  }
  const raw = String(error || '').trim()
  return raw || fallback
}

export default function App() {
  const [apiBase] = useState(() => safeLocalStorageGetItem('apiBaseStudent') || DEFAULT_API_URL)
  const {
    sidebarOpen,
    setSidebarOpen,
    openSessionMenuId,
    setOpenSessionMenuId,
    toggleSessionMenu,
    setSessionMenuRef,
    setSessionMenuTriggerRef,
    handleSessionMenuTriggerKeyDown,
    handleSessionMenuKeyDown,
  } = useStudentSessionSidebarState()
  const appRef = useRef<HTMLDivElement>(null)
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
  const { messagesRef, endRef, isNearBottom, scrollToBottom, autoScroll } = useSmartAutoScroll()
  const { saveScrollHeight, restoreScrollPosition } = useScrollPositionLock(messagesRef)
  useWheelScrollZone({
    appRef,
    defaultZone: 'chat' as const,
    resolveTarget: (zone: string) => {
      const root = appRef.current
      if (!root) return null
      if (zone === 'sidebar') return root.querySelector('.session-groups') as HTMLElement | null
      return root.querySelector('.messages') as HTMLElement | null
    },
    detectors: [
      { zone: 'sidebar', selector: '.session-sidebar', when: () => sidebarOpen },
      { zone: 'chat', selector: '.chat-shell' },
    ],
    resetWhen: [{ zone: 'sidebar', condition: !sidebarOpen }],
  })
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
      return parsePendingChatJobFromStorage(raw)
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
  const [renameDialogSessionId, setRenameDialogSessionId] = useState<string | null>(null)
  const [archiveDialogSessionId, setArchiveDialogSessionId] = useState<string | null>(null)
  const [activeSessionId, setActiveSessionId] = useState('')
  const [sessionLoading, setSessionLoading] = useState(false)
  const [sessionError, setSessionError] = useState('')
  const [sessionCursor, setSessionCursor] = useState(0)
  const [sessionHasMore, setSessionHasMore] = useState(false)
  const [forceSessionLoadToken, setForceSessionLoadToken] = useState(0)
  const activeSessionRef = useRef('')
  const pendingChatJobRef = useRef<PendingChatJob | null>(pendingChatJob)
  const recentCompletedRepliesRef = useRef<RecentCompletedReply[]>(recentCompletedReplies)
  const pendingRecoveredFromStorageRef = useRef(false)
  const skipAutoSessionLoadIdRef = useRef('')
  const historyRequestRef = useRef(0)
  const sessionRequestRef = useRef(0)

  const setActiveSession = useCallback((sessionId: string) => {
    const sid = String(sessionId || '').trim()
    activeSessionRef.current = sid
    setActiveSessionId(sid)
  }, [])

  const { viewStateSyncReady } = useStudentSessionViewStateSync({
    apiBase,
    verifiedStudentId: verifiedStudent?.student_id,
    activeSessionId,
    sessionTitleMap,
    deletedSessionIds,
    localDraftSessionIds,
    setSessions,
    setHistoryCursor,
    setHistoryHasMore,
    setSessionTitleMap,
    setDeletedSessionIds,
    setLocalDraftSessionIds,
    setActiveSession,
  })

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

  const renderedMessages = useMemo(() => {
    const cache = markdownCacheRef.current
    evictOldestEntries(cache)
    return messages.map((msg): RenderedMessage => {
      const cached = cache.get(msg.id)
      if (cached && cached.content === msg.content && cached.apiBase === apiBase) return { ...msg, html: cached.html }
      const html = absolutizeChartImageUrls(renderMarkdown(msg.content), apiBase)
      cache.set(msg.id, { content: msg.content, html, apiBase })
      return { ...msg, html }
    })
  }, [messages, apiBase])

  useEffect(() => {
    autoScroll()
  }, [messages, sending, autoScroll])

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
      } catch (err: unknown) {
        if (isAbortError(err)) return
        setAssignmentError(toErrorMessage(err, '无法获取今日作业'))
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
    const raw = safeLocalStorageGetItem(key)
    if (!raw) {
      pendingRecoveredFromStorageRef.current = false
      setPendingChatJob(null)
      return
    }
    const parsed = parsePendingChatJobFromStorage(raw)
    if (!parsed) {
      safeLocalStorageRemoveItem(key)
      pendingRecoveredFromStorageRef.current = false
      setPendingChatJob(null)
      return
    }
    pendingRecoveredFromStorageRef.current = Boolean(parsed.job_id)
    setPendingChatJob(parsed)
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
      const rawPending = safeLocalStorageGetItem(pendingKey)
      if (rawPending) {
        nextPending = parsePendingChatJobFromStorage(rawPending)
        if (!nextPending) safeLocalStorageRemoveItem(pendingKey)
      }

      if (!samePendingJob(pendingChatJobRef.current, nextPending)) {
        pendingRecoveredFromStorageRef.current = Boolean(nextPending?.job_id)
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
        next.push({ id: pendingChatJob.placeholder_id, role: 'assistant' as const, content: '正在回复中…', time: nowTime() })
      }
      return next
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSessionId, pendingChatJob?.job_id, pendingChatJob?.session_id])

  useEffect(() => {
    if (!pendingChatJob?.job_id) return
    const cleanup = startVisibilityAwareBackoffPolling(
      async () => {
        const pendingAgeMs = Date.now() - Number(pendingChatJob.created_at || 0)
        if (!Number.isFinite(pendingAgeMs) || pendingAgeMs > PENDING_CHAT_MAX_AGE_MS) {
          const staleMsg = '上一条请求已过期，请重新发送。'
          setMessages((prev) => {
            const base = stripTransientPendingBubbles(prev)
            const hasPlaceholder = base.some((item) => item.id === pendingChatJob.placeholder_id)
            if (!hasPlaceholder) return base
            return base.map((item) =>
              item.id === pendingChatJob.placeholder_id ? { ...item, content: staleMsg, time: nowTime() } : item,
            )
          })
          skipAutoSessionLoadIdRef.current = pendingChatJob.session_id || ''
          setPendingChatJob(null)
          setSending(false)
          return 'stop'
        }
        if (pendingChatJob.session_id && activeSessionId && pendingChatJob.session_id !== activeSessionId) {
          return 'continue'
        }
        const res = await fetch(`${apiBase}/chat/status?job_id=${encodeURIComponent(pendingChatJob.job_id)}`)
        if (res.status === 404) {
          setMessages((prev) => stripTransientPendingBubbles(prev))
          skipAutoSessionLoadIdRef.current = pendingChatJob.session_id || ''
          setPendingChatJob(null)
          setSending(false)
          return 'stop'
        }
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
              next.push({ id: pendingChatJob.placeholder_id, role: 'assistant' as const, content: '正在回复中…', time: nowTime() })
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
              next.push({ id: pendingChatJob.placeholder_id, role: 'assistant' as const, content: '正在回复中…', time: nowTime() })
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
        const msg = toErrorMessage(err)
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
            next.push({ id: pendingChatJob.placeholder_id, role: 'assistant' as const, content: '正在回复中…', time: nowTime() })
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
    } catch (err: unknown) {
      if (requestNo !== historyRequestRef.current) return
      setHistoryError(toErrorMessage(err))
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
                next.push({ id: pending.placeholder_id, role: 'assistant', content: '正在回复中…', time: nowTime() })
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
        saveScrollHeight()
        setMessages((prev) => [...merged, ...prev])
        requestAnimationFrame(() => restoreScrollPosition())
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
    } catch (err: unknown) {
      if (requestNo !== sessionRequestRef.current) return
      setSessionError(toErrorMessage(err))
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
    if (event.nativeEvent.isComposing) return
    event.preventDefault()
    if (!verifiedStudent) return
    if (sending || pendingChatJob?.job_id) return
    if (!input.trim()) return
    event.currentTarget.form?.requestSubmit()
  }

  const { handleSend } = useStudentSendFlow({
    apiBase,
    input,
    messages,
    activeSessionId,
    todayAssignment,
    verifiedStudent,
    pendingChatJob,
    pendingChatKeyPrefix: PENDING_CHAT_KEY_PREFIX,
    todayDate,
    setVerifyError,
    setVerifyOpen,
    setSending,
    setInput,
    setActiveSession,
    setPendingChatJob,
    setMessages,
    updateMessage,
    pendingRecoveredFromStorageRef,
    skipAutoSessionLoadIdRef,
  })

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
    } catch (err: unknown) {
      setVerifyError(toErrorMessage(err))
    } finally {
      setVerifying(false)
    }
  }

  const {
    getSessionTitle,
    visibleSessions,
    groupedSessions,
    selectStudentSession,
    resetVerification,
    startNewStudentSession,
    renameSession,
    toggleSessionArchive,
    cancelRenameDialog,
    confirmRenameDialog,
    cancelArchiveDialog,
    confirmArchiveDialog,
    archiveDialogIsArchived,
    archiveDialogActionLabel,
  } = useStudentSessionActions({
    sessions,
    deletedSessionIds,
    historyQuery,
    sessionTitleMap,
    showArchivedSessions,
    activeSessionId,
    renameDialogSessionId,
    archiveDialogSessionId,
    sessionRequestRef,
    todayDate,
    newSessionMessage: STUDENT_NEW_SESSION_MESSAGE,
    setSidebarOpen,
    setForceSessionLoadToken,
    setActiveSession,
    setSessionCursor,
    setSessionHasMore,
    setSessionError,
    setOpenSessionMenuId,
    setVerifiedStudent,
    setNameInput,
    setClassInput,
    setVerifyError,
    setVerifyOpen,
    setLocalDraftSessionIds,
    setShowArchivedSessions,
    setPendingChatJob,
    setSending,
    setInput,
    setSessions,
    setMessages,
    setRenameDialogSessionId,
    setArchiveDialogSessionId,
    setSessionTitleMap,
    setDeletedSessionIds,
  })

  return (
    <div className="app flex h-dvh flex-col bg-bg overflow-hidden" ref={appRef}>
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
            messagesRef={messagesRef}
            endRef={endRef}
            isNearBottom={isNearBottom}
            scrollToBottom={scrollToBottom}
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
