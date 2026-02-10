import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { makeId } from '../../shared/id'
import { renderMarkdown, absolutizeChartImageUrls } from '../../shared/markdown'
import { getNextMenuIndex } from '../../shared/sessionMenuNavigation'
import { sessionGroupFromIso, sessionGroupOrder } from '../../shared/sessionGrouping'
import { startVisibilityAwareBackoffPolling } from '../../shared/visibilityBackoffPolling'
import { safeLocalStorageGetItem, safeLocalStorageRemoveItem, safeLocalStorageSetItem } from '../../shared/storage'
import { formatSessionUpdatedLabel, nowTime, timeFromIso } from '../../shared/time'
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
import StudentSessionSidebar from './features/chat/StudentSessionSidebar'
import StudentTopbar from './features/layout/StudentTopbar'
import type {
  AssignmentDetail,
  ChatJobStatus,
  ChatResponse,
  ChatStartResult,
  Message,
  PendingChatJob,
  RenderedMessage,
  SessionGroup,
  StudentHistoryMessage,
  StudentHistorySession,
  StudentHistorySessionResponse,
  StudentHistorySessionsResponse,
  VerifiedStudent,
  VerifyResponse,
} from './appTypes'
import 'katex/dist/katex.min.css'

const DEFAULT_API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const STUDENT_WELCOME_MESSAGE = '学生端已就绪。请先填写姓名完成验证，然后开始提问或进入作业讨论。'
const STUDENT_NEW_SESSION_MESSAGE = '已开启新会话。你可以继续提问，或输入“开始今天作业”。'

const todayDate = () => new Date().toLocaleDateString('sv-SE')

const toDomSafeId = (value: string) => String(value || '').replace(/[^a-zA-Z0-9_-]/g, '_')

export default function App() {
  const [apiBase, setApiBase] = useState(() => safeLocalStorageGetItem('apiBaseStudent') || DEFAULT_API_URL)
  const [sidebarOpen, setSidebarOpen] = useState(true)
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

  const [pendingChatJob, setPendingChatJob] = useState<PendingChatJob | null>(null)

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
  const activeSessionRef = useRef('')
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
      setPendingChatJob(null)
      return
    }
    const key = `studentPendingChatJob:${sid}`
    try {
      const raw = safeLocalStorageGetItem(key)
      setPendingChatJob(raw ? (JSON.parse(raw) as any) : null)
    } catch {
      setPendingChatJob(null)
    }
  }, [verifiedStudent?.student_id])

  useEffect(() => {
    const sid = verifiedStudent?.student_id?.trim() || ''
    if (!sid) return
    const key = `studentPendingChatJob:${sid}`
    try {
      if (pendingChatJob) safeLocalStorageSetItem(key, JSON.stringify(pendingChatJob))
      else safeLocalStorageRemoveItem(key)
    } catch {
      // ignore storage errors
    }
  }, [pendingChatJob, verifiedStudent?.student_id])

  useEffect(() => {
    if (!pendingChatJob?.job_id) return
    setMessages((prev) => {
      const next = stripTransientPendingBubbles(prev)
      if (next.some((m) => m.id === pendingChatJob.placeholder_id)) return next
      return [
        ...next,
        ...(pendingChatJob.user_text
          ? [{ id: makeId(), role: 'user' as const, content: pendingChatJob.user_text, time: nowTime() }]
          : []),
        { id: pendingChatJob.placeholder_id, role: 'assistant', content: '正在恢复上一条回复…', time: nowTime() },
      ]
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingChatJob?.job_id])

  useEffect(() => {
    if (!pendingChatJob?.job_id) return
    const cleanup = startVisibilityAwareBackoffPolling(
      async () => {
        const res = await fetch(`${apiBase}/chat/status?job_id=${encodeURIComponent(pendingChatJob.job_id)}`)
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `状态码 ${res.status}`)
        }
        const data = (await res.json()) as ChatJobStatus
        if (data.status === 'done') {
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
              m.id === pendingChatJob.placeholder_id ? { ...m, content: data.reply || '已收到。', time: nowTime() } : m,
            )
          })
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
      { kickMode: 'timeout0' },
    )

    return cleanup
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingChatJob?.job_id, apiBase])

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
      if (requestNo !== sessionRequestRef.current || activeSessionRef.current !== targetSessionId) return
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
      const next = typeof data.next_cursor === 'number' ? data.next_cursor : 0
      setSessionCursor(next)
      setSessionHasMore(mapped.length >= 1 && next > 0)
      if (append) {
        setMessages((prev) => [...mapped, ...prev])
      } else {
        setMessages(
          mapped.length
            ? mapped
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
      if (requestNo !== sessionRequestRef.current || activeSessionRef.current !== targetSessionId) return
      setSessionError(err.message || String(err))
    } finally {
      if (requestNo !== sessionRequestRef.current || activeSessionRef.current !== targetSessionId) return
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
    setActiveSessionId(localState.active_session_id || '')
    setViewStateUpdatedAt(localState.updated_at || new Date().toISOString())
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
    if (!sid) return
    currentViewStateRef.current = currentViewState
    safeLocalStorageSetItem(`${STUDENT_SESSION_VIEW_STATE_KEY_PREFIX}${sid}`, JSON.stringify(currentViewState))
    safeLocalStorageSetItem(`studentSessionTitles:${sid}`, JSON.stringify(currentViewState.title_map))
    safeLocalStorageSetItem(`studentDeletedSessions:${sid}`, JSON.stringify(currentViewState.hidden_ids))
    if (activeSessionId) safeLocalStorageSetItem(`studentActiveSession:${sid}`, activeSessionId)
    else safeLocalStorageRemoveItem(`studentActiveSession:${sid}`)
  }, [activeSessionId, currentViewState, verifiedStudent?.student_id])

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
    if (!verifiedStudent?.student_id) return
    if (!viewStateSyncReady) return
    if (pendingChatJob?.job_id) return
    if (activeSessionId) return
    const next = todayAssignment?.assignment_id || `general_${todayDate()}`
    setActiveSessionId(next)
  }, [verifiedStudent?.student_id, todayAssignment?.assignment_id, pendingChatJob?.job_id, activeSessionId, viewStateSyncReady])

  useEffect(() => {
    if (!verifiedStudent?.student_id) return
    if (!activeSessionId) return
    if (pendingChatJob?.job_id) return
    if (sending) return
    void loadSessionMessages(activeSessionId, -1, false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSessionId, verifiedStudent?.student_id, apiBase])

  const appendMessage = (roleType: 'user' | 'assistant', content: string) => {
    setMessages((prev) => [...prev, { id: makeId(), role: roleType, content, time: nowTime() }])
  }

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

    const sessionId = activeSessionId || todayAssignment?.assignment_id || `general_${todayDate()}`
    if (!activeSessionId) setActiveSessionId(sessionId)
    const requestId = `schat_${verifiedStudent.student_id}_${Date.now()}_${Math.random().toString(16).slice(2)}`
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
          student_id: verifiedStudent.student_id,
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
      setPendingChatJob({
        job_id: data.job_id,
        request_id: requestId,
        placeholder_id: placeholderId,
        user_text: trimmed,
        session_id: sessionId,
        created_at: Date.now(),
      })
    } catch (err: any) {
      updateMessage(placeholderId, { content: `抱歉，请求失败：${err.message || err}`, time: nowTime() })
      setSending(false)
      setPendingChatJob(null)
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
      setActiveSessionId(sid)
      setSessionCursor(-1)
      setSessionHasMore(false)
      setSessionError('')
      setOpenSessionMenuId('')
      closeSidebarOnMobile()
    },
    [closeSidebarOnMobile],
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
    setActiveSessionId(next)
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
  }, [closeSidebarOnMobile])

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
        setActiveSessionId(next)
        setSessionCursor(-1)
        setSessionHasMore(false)
        setSessionError('')
      } else {
        startNewStudentSession()
      }
    }
  }, [activeSessionId, archiveDialogSessionId, deletedSessionIds, startNewStudentSession, visibleSessions])

  const archiveDialogIsArchived = archiveDialogSessionId ? deletedSessionIds.includes(archiveDialogSessionId) : false
  const archiveDialogActionLabel = archiveDialogIsArchived ? '恢复' : '归档'

  return (
    <div className="app">
      <StudentTopbar verifiedStudent={verifiedStudent} sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} startNewStudentSession={startNewStudentSession} />

      <div className={`student-layout ${sidebarOpen ? 'sidebar-open' : 'sidebar-collapsed'}`}>
        <StudentSessionSidebar
          apiBase={apiBase} sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} verifiedStudent={verifiedStudent}
          historyLoading={historyLoading} historyError={historyError} historyHasMore={historyHasMore} refreshSessions={refreshSessions}
          showArchivedSessions={showArchivedSessions} setShowArchivedSessions={setShowArchivedSessions} historyQuery={historyQuery} setHistoryQuery={setHistoryQuery}
          visibleSessionCount={visibleSessions.length} groupedSessions={groupedSessions} deletedSessionIds={deletedSessionIds}
          activeSessionId={activeSessionId} onSelectSession={selectStudentSession} getSessionTitle={getSessionTitle}
          openSessionMenuId={openSessionMenuId} toggleSessionMenu={toggleSessionMenu}
          handleSessionMenuTriggerKeyDown={handleSessionMenuTriggerKeyDown} handleSessionMenuKeyDown={handleSessionMenuKeyDown}
          setSessionMenuTriggerRef={setSessionMenuTriggerRef} setSessionMenuRef={setSessionMenuRef} renameSession={renameSession} toggleSessionArchive={toggleSessionArchive}
          sessionHasMore={sessionHasMore} sessionLoading={sessionLoading} sessionCursor={sessionCursor} loadSessionMessages={loadSessionMessages} sessionError={sessionError}
          verifyOpen={verifyOpen} setVerifyOpen={setVerifyOpen} handleVerify={handleVerify} nameInput={nameInput} setNameInput={setNameInput} classInput={classInput} setClassInput={setClassInput} verifying={verifying} verifyError={verifyError}
          todayAssignment={todayAssignment} assignmentLoading={assignmentLoading} assignmentError={assignmentError} todayDate={todayDate} resetVerification={resetVerification} startNewStudentSession={startNewStudentSession}
          renameDialogSessionId={renameDialogSessionId} archiveDialogSessionId={archiveDialogSessionId} archiveDialogActionLabel={archiveDialogActionLabel} archiveDialogIsArchived={archiveDialogIsArchived}
          cancelRenameDialog={cancelRenameDialog} confirmRenameDialog={confirmRenameDialog} cancelArchiveDialog={cancelArchiveDialog} confirmArchiveDialog={confirmArchiveDialog}
        />

        <main className="chat-shell">
        <div className="messages">
          <div className="messages-inner">
            {renderedMessages.map((msg) => (
              <div key={msg.id} className={`message ${msg.role}`}>
                <div className="bubble">
                  <div className="meta">
                    {msg.role === 'user' ? '我' : '助手'} · {msg.time}
                  </div>
                  <div className="text markdown" dangerouslySetInnerHTML={{ __html: msg.html }} />
                </div>
              </div>
            ))}
            {sending && !pendingChatJob?.job_id && (
              <div className="message assistant">
                <div className="bubble typing">
                  <div className="meta">助手 · {nowTime()}</div>
                  <div className="text">正在思考…</div>
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>
        </div>

        <form
          className={`composer ${!verifiedStudent || pendingChatJob?.job_id ? 'disabled' : ''}`}
          onSubmit={handleSend}
        >
          <div className="composer-inner">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleInputKeyDown}
              placeholder={verifiedStudent ? '输入问题，例如：牛顿第三定律是什么' : '请先填写姓名完成验证'}
              rows={1}
              disabled={!verifiedStudent || Boolean(pendingChatJob?.job_id)}
            />
            <div className="composer-actions">
              <span className="composer-hint">{composerHint}</span>
              <button type="submit" className="send-btn" disabled={sending || !verifiedStudent || Boolean(pendingChatJob?.job_id)}>
                发送
              </button>
            </div>
          </div>
        </form>
      </main>
      </div>
    </div>
  )
}
