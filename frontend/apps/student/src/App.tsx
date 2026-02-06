import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { unified } from 'unified'
import remarkParse from 'remark-parse'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import remarkRehype from 'remark-rehype'
import rehypeKatex from 'rehype-katex'
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize'
import rehypeStringify from 'rehype-stringify'
import { visit } from 'unist-util-visit'
import 'katex/dist/katex.min.css'

const DEFAULT_API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const STUDENT_WELCOME_MESSAGE = '学生端已就绪。请先填写姓名完成验证，然后开始提问或进入作业讨论。'
const STUDENT_NEW_SESSION_MESSAGE = '已开启新会话。你可以继续提问，或输入“开始今天作业”。'
const STUDENT_SESSION_VIEW_STATE_KEY_PREFIX = 'studentSessionViewState:'

type Message = {
  id: string
  role: 'user' | 'assistant'
  content: string
  time: string
}

type RenderedMessage = Message & { html: string }

type ChatResponse = {
  reply: string
}

type ChatJobStatus = {
  job_id: string
  status: 'queued' | 'processing' | 'done' | 'failed' | 'cancelled' | string
  step?: string
  reply?: string
  error?: string
  error_detail?: string
  updated_at?: string
}

type ChatStartResult = {
  ok: boolean
  job_id: string
  status: string
}

type StudentHistorySession = {
  session_id: string
  updated_at?: string
  message_count?: number
  preview?: string
  assignment_id?: string
  date?: string
}

type SessionGroup<T> = {
  key: string
  label: string
  items: T[]
}

type StudentHistorySessionsResponse = {
  ok: boolean
  student_id: string
  sessions: StudentHistorySession[]
  next_cursor?: number | null
  total?: number
}

type SessionViewStatePayload = {
  title_map: Record<string, string>
  hidden_ids: string[]
  active_session_id: string
  updated_at: string
}

type StudentHistoryMessage = {
  ts?: string
  role?: string
  content?: string
  [k: string]: any
}

type StudentHistorySessionResponse = {
  ok: boolean
  student_id: string
  session_id: string
  messages: StudentHistoryMessage[]
  next_cursor: number
}

type AssignmentQuestion = {
  question_id?: string
  kp_id?: string
  difficulty?: string
  stem_text?: string
}

type AssignmentDetail = {
  assignment_id: string
  date?: string
  question_count?: number
  meta?: { target_kp?: string[] }
  questions?: AssignmentQuestion[]
  delivery?: { mode?: string; files?: Array<{ name: string; url: string }> }
}

type VerifiedStudent = {
  student_id: string
  student_name: string
  class_name?: string
}

type VerifyResponse = {
  ok: boolean
  error?: string
  message?: string
  student?: VerifiedStudent
}

const makeId = () => `${Date.now()}-${Math.random().toString(16).slice(2)}`

const nowTime = () => new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
const todayDate = () => new Date().toLocaleDateString('sv-SE')
const timeFromIso = (ts?: string) => {
  if (!ts) return nowTime()
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return nowTime()
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const formatSessionUpdatedLabel = (ts?: string) => {
  if (!ts) return ''
  const d = new Date(ts)
  if (Number.isNaN(d.getTime())) return ''
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const target = new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const diffDays = Math.floor((today.getTime() - target.getTime()) / (24 * 60 * 60 * 1000))
  if (diffDays <= 0) return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  if (diffDays === 1) return '昨天'
  if (diffDays < 7) {
    const names = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
    return names[d.getDay()] || ''
  }
  return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }).replace('/', '-')
}

const sessionGroupFromIso = (updatedAt?: string) => {
  if (!updatedAt) return { key: 'older', label: '更早' }
  const date = new Date(updatedAt)
  if (Number.isNaN(date.getTime())) return { key: 'older', label: '更早' }
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const target = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()
  const diffDays = Math.floor((today - target) / (24 * 60 * 60 * 1000))
  if (diffDays <= 0) return { key: 'today', label: '今天' }
  if (diffDays === 1) return { key: 'yesterday', label: '昨天' }
  if (diffDays <= 7) return { key: 'week', label: '近 7 天' }
  return { key: 'older', label: '更早' }
}

const sessionGroupOrder: Record<string, number> = {
  today: 0,
  yesterday: 1,
  week: 2,
  older: 3,
}

const parseOptionalIso = (value?: string) => {
  const raw = String(value || '').trim()
  if (!raw) return null
  const ms = Date.parse(raw)
  return Number.isNaN(ms) ? null : ms
}

const compareSessionViewStateUpdatedAt = (a?: string, b?: string) => {
  const ma = parseOptionalIso(a)
  const mb = parseOptionalIso(b)
  if (ma !== null && mb !== null) {
    if (ma > mb) return 1
    if (ma < mb) return -1
    return 0
  }
  if (ma !== null) return 1
  if (mb !== null) return -1
  return 0
}

const normalizeSessionViewStatePayload = (raw: any): SessionViewStatePayload => {
  const titleRaw = raw && typeof raw === 'object' && raw.title_map && typeof raw.title_map === 'object' ? raw.title_map : {}
  const titleMap: Record<string, string> = {}
  for (const [key, value] of Object.entries(titleRaw)) {
    const sid = String(key || '').trim()
    const title = String(value || '').trim()
    if (!sid || !title) continue
    titleMap[sid] = title
  }
  const hiddenRaw: unknown[] = Array.isArray(raw?.hidden_ids) ? raw.hidden_ids : []
  const hiddenIds = Array.from(new Set(hiddenRaw.map((item: unknown) => String(item || '').trim()).filter(Boolean)))
  const activeSessionId = String(raw?.active_session_id || '').trim()
  const updatedAt = parseOptionalIso(raw?.updated_at) !== null ? String(raw?.updated_at) : ''
  return {
    title_map: titleMap,
    hidden_ids: hiddenIds,
    active_session_id: activeSessionId,
    updated_at: updatedAt,
  }
}

const buildSessionViewStateSignature = (state: SessionViewStatePayload) => {
  const titleEntries = Object.entries(state.title_map).sort((a, b) => a[0].localeCompare(b[0]))
  const normalized = {
    title_map: Object.fromEntries(titleEntries),
    hidden_ids: [...state.hidden_ids],
    active_session_id: state.active_session_id || '',
    updated_at: state.updated_at || '',
  }
  return JSON.stringify(normalized)
}

const readStudentLocalViewState = (studentId: string): SessionViewStatePayload => {
  const sid = String(studentId || '').trim()
  if (!sid) {
    return normalizeSessionViewStatePayload({
      title_map: {},
      hidden_ids: [],
      active_session_id: '',
      updated_at: new Date().toISOString(),
    })
  }
  try {
    const raw = localStorage.getItem(`${STUDENT_SESSION_VIEW_STATE_KEY_PREFIX}${sid}`)
    if (raw) {
      const parsed = normalizeSessionViewStatePayload(JSON.parse(raw))
      if (parsed.updated_at) return parsed
    }
  } catch {
    // ignore
  }
  let titleMap: Record<string, string> = {}
  let hiddenIds: string[] = []
  const activeSessionId = String(localStorage.getItem(`studentActiveSession:${sid}`) || '').trim()
  try {
    const parsed = JSON.parse(localStorage.getItem(`studentSessionTitles:${sid}`) || '{}')
    if (parsed && typeof parsed === 'object') titleMap = parsed
  } catch {
    titleMap = {}
  }
  try {
    const parsed = JSON.parse(localStorage.getItem(`studentDeletedSessions:${sid}`) || '[]')
    if (Array.isArray(parsed)) hiddenIds = parsed.map((item) => String(item || '').trim()).filter(Boolean)
  } catch {
    hiddenIds = []
  }
  return normalizeSessionViewStatePayload({
    title_map: titleMap,
    hidden_ids: hiddenIds,
    active_session_id: activeSessionId,
    updated_at: new Date().toISOString(),
  })
}

const removeEmptyParagraphs = () => {
  return (tree: any) => {
    visit(tree, 'paragraph', (node: any, index: number | null | undefined, parent: any) => {
      if (!parent || typeof index !== 'number') return
      if (!node.children || node.children.length === 0) {
        parent.children.splice(index, 1)
      }
    })
  }
}

const remarkLatexBrackets = () => {
  return (tree: any) => {
    visit(tree, 'text', (node: any, index: number | null | undefined, parent: any) => {
      if (!parent || typeof index !== 'number') return
      if (parent.type === 'inlineMath' || parent.type === 'math') return

      const value = String(node.value || '')
      if (!value.includes('\\[') && !value.includes('\\(')) return

      const nodes: any[] = []
      let pos = 0

      const findUnescaped = (token: string, start: number) => {
        let idx = value.indexOf(token, start)
        while (idx > 0 && value[idx - 1] === '\\') {
          idx = value.indexOf(token, idx + 1)
        }
        return idx
      }

      while (pos < value.length) {
        const nextDisplay = findUnescaped('\\[', pos)
        const nextInline = findUnescaped('\\(', pos)
        let next = -1
        let mode: 'display' | 'inline' | '' = ''

        if (nextDisplay !== -1 && (nextInline === -1 || nextDisplay < nextInline)) {
          next = nextDisplay
          mode = 'display'
        } else if (nextInline !== -1) {
          next = nextInline
          mode = 'inline'
        }

        if (next === -1) {
          nodes.push({ type: 'text', value: value.slice(pos) })
          break
        }

        if (next > pos) nodes.push({ type: 'text', value: value.slice(pos, next) })

        const closeToken = mode === 'display' ? '\\]' : '\\)'
        const end = findUnescaped(closeToken, next + 2)
        if (end === -1) {
          nodes.push({ type: 'text', value: value.slice(next) })
          break
        }

        const mathValue = value.slice(next + 2, end)
        nodes.push({ type: mode === 'display' ? 'math' : 'inlineMath', value: mathValue })
        pos = end + 2
      }

      if (nodes.length) {
        parent.children.splice(index, 1, ...nodes)
        return index + nodes.length
      }
    })
  }
}

const katexSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    span: [...(defaultSchema.attributes?.span || []), 'className', 'style'],
    div: [...(defaultSchema.attributes?.div || []), 'className', 'style'],
    code: [...(defaultSchema.attributes?.code || []), 'className'],
  },
}

const processor = unified()
  .use(remarkParse)
  .use(remarkGfm)
  .use(remarkMath)
  .use(removeEmptyParagraphs)
  .use(remarkLatexBrackets)
  .use(remarkRehype)
  .use(rehypeKatex)
  .use(rehypeSanitize, katexSchema)
  .use(rehypeStringify)

const normalizeMathDelimiters = (content: string) => {
  if (!content) return ''
  return content
    .replace(/\\\[/g, '$$')
    .replace(/\\\]/g, '$$')
    .replace(/\\\(/g, '$')
    .replace(/\\\)/g, '$')
}

const renderMarkdown = (content: string) => {
  const normalized = normalizeMathDelimiters(content || '')
  const result = processor.processSync(normalized)
  return String(result)
}

const absolutizeChartImageUrls = (html: string, apiBase: string) => {
  const base = (apiBase || '').trim().replace(/\/+$/, '')
  if (!base) return html
  return html.replace(/(<img\b[^>]*\bsrc=["'])(\/charts\/[^"']+)(["'])/gi, (_, p1, p2, p3) => `${p1}${base}${p2}${p3}`)
}

export default function App() {
  const [apiBase, setApiBase] = useState(() => localStorage.getItem('apiBaseStudent') || DEFAULT_API_URL)
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
  const [settingsOpen, setSettingsOpen] = useState(false)
  const endRef = useRef<HTMLDivElement | null>(null)
  const inputRef = useRef<HTMLTextAreaElement | null>(null)

  const [verifiedStudent, setVerifiedStudent] = useState<VerifiedStudent | null>(() => {
    const raw = localStorage.getItem('verifiedStudent')
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

  const [pendingChatJob, setPendingChatJob] = useState<{
    job_id: string
    request_id: string
    placeholder_id: string
    user_text: string
    session_id: string
    created_at: number
  } | null>(null)

  const [sessions, setSessions] = useState<StudentHistorySession[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState('')
  const [historyCursor, setHistoryCursor] = useState(0)
  const [historyHasMore, setHistoryHasMore] = useState(false)
  const [historyQuery, setHistoryQuery] = useState('')
  const [sessionTitleMap, setSessionTitleMap] = useState<Record<string, string>>({})
  const [deletedSessionIds, setDeletedSessionIds] = useState<string[]>([])
  const [localDraftSessionIds, setLocalDraftSessionIds] = useState<string[]>([])
  const [openSessionMenuId, setOpenSessionMenuId] = useState('')
  const [activeSessionId, setActiveSessionId] = useState('')
  const [sessionLoading, setSessionLoading] = useState(false)
  const [sessionError, setSessionError] = useState('')
  const [sessionCursor, setSessionCursor] = useState(0)
  const [sessionHasMore, setSessionHasMore] = useState(false)
  const [viewStateUpdatedAt, setViewStateUpdatedAt] = useState(() => new Date().toISOString())
  const [viewStateSyncReady, setViewStateSyncReady] = useState(false)
  const activeSessionRef = useRef('')
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
        active_session_id: activeSessionId,
        updated_at: viewStateUpdatedAt,
      }),
    [activeSessionId, deletedSessionIds, sessionTitleMap, viewStateUpdatedAt],
  )

  useEffect(() => {
    localStorage.setItem('apiBaseStudent', apiBase)
    markdownCacheRef.current.clear()
  }, [apiBase])

  useEffect(() => {
    if (verifiedStudent) {
      localStorage.setItem('verifiedStudent', JSON.stringify(verifiedStudent))
    } else {
      localStorage.removeItem('verifiedStudent')
    }
  }, [verifiedStudent])

  useEffect(() => {
    if (verifiedStudent) {
      setVerifyOpen(false)
    }
  }, [verifiedStudent])

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
      const raw = localStorage.getItem(key)
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
      if (pendingChatJob) localStorage.setItem(key, JSON.stringify(pendingChatJob))
      else localStorage.removeItem(key)
    } catch {
      // ignore storage errors
    }
  }, [pendingChatJob, verifiedStudent?.student_id])

  useEffect(() => {
    if (!pendingChatJob?.job_id) return
    const alreadyHasPlaceholder = messages.some((m) => m.id === pendingChatJob.placeholder_id)
    if (alreadyHasPlaceholder) return
    setMessages((prev) => [
      ...prev,
      ...(pendingChatJob.user_text
        ? [{ id: makeId(), role: 'user' as const, content: pendingChatJob.user_text, time: nowTime() }]
        : []),
      { id: pendingChatJob.placeholder_id, role: 'assistant', content: '正在恢复上一条回复…', time: nowTime() },
    ])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingChatJob?.job_id])

  useEffect(() => {
    if (!pendingChatJob?.job_id) return
    let cancelled = false
    let timeoutId: number | null = null
    let inFlight = false
    let delayMs = 800

    const clearTimer = () => {
      if (timeoutId) window.clearTimeout(timeoutId)
      timeoutId = null
    }

    const jitter = (ms: number) => Math.round(ms * (0.85 + Math.random() * 0.3))

    const abortInFlight = () => {
      // fetch in this file doesn't pass AbortController (keep simple)
    }

    const poll = async () => {
      if (cancelled || inFlight) return
      if (document.visibilityState === 'hidden') {
        timeoutId = window.setTimeout(poll, jitter(Math.min(8000, delayMs)))
        return
      }
      inFlight = true
      try {
        const res = await fetch(`${apiBase}/chat/status?job_id=${encodeURIComponent(pendingChatJob.job_id)}`)
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `状态码 ${res.status}`)
        }
        const data = (await res.json()) as ChatJobStatus
        if (cancelled) return
        if (data.status === 'done') {
          updateMessage(pendingChatJob.placeholder_id, { content: data.reply || '已收到。', time: nowTime() })
          setPendingChatJob(null)
          setSending(false)
          void refreshSessions()
          return
        }
        if (data.status === 'failed' || data.status === 'cancelled') {
          const msg = data.error_detail || data.error || '请求失败'
          updateMessage(pendingChatJob.placeholder_id, { content: `抱歉，请求失败：${msg}`, time: nowTime() })
          setPendingChatJob(null)
          setSending(false)
          return
        }
        delayMs = Math.min(8000, Math.round(delayMs * 1.4))
        timeoutId = window.setTimeout(poll, jitter(delayMs))
      } catch (err: any) {
        if (cancelled) return
        const msg = err?.message || String(err)
        updateMessage(pendingChatJob.placeholder_id, { content: `网络波动，正在重试…（${msg}）`, time: nowTime() })
        delayMs = Math.min(8000, Math.round(delayMs * 1.6))
        timeoutId = window.setTimeout(poll, jitter(delayMs))
      } finally {
        inFlight = false
      }
    }

    const onVisibilityChange = () => {
      if (cancelled) return
      if (document.visibilityState === 'visible') {
        delayMs = 800
        if (inFlight) return
        clearTimer()
        timeoutId = window.setTimeout(poll, 0)
      }
    }
    document.addEventListener('visibilitychange', onVisibilityChange)
    void poll()

    return () => {
      cancelled = true
      document.removeEventListener('visibilitychange', onVisibilityChange)
      clearTimer()
      abortInFlight()
    }
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
    applyingViewStateRef.current = true
    setSessionTitleMap(localState.title_map)
    setDeletedSessionIds(localState.hidden_ids)
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
          setActiveSessionId(remoteState.active_session_id || '')
          setViewStateUpdatedAt(remoteState.updated_at || new Date().toISOString())
          lastSyncedViewStateSignatureRef.current = buildSessionViewStateSignature(remoteState)
          return
        }
        const payload = normalizeSessionViewStatePayload(localState)
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
    localStorage.setItem(`${STUDENT_SESSION_VIEW_STATE_KEY_PREFIX}${sid}`, JSON.stringify(currentViewState))
    localStorage.setItem(`studentSessionTitles:${sid}`, JSON.stringify(currentViewState.title_map))
    localStorage.setItem(`studentDeletedSessions:${sid}`, JSON.stringify(currentViewState.hidden_ids))
    if (currentViewState.active_session_id) localStorage.setItem(`studentActiveSession:${sid}`, currentViewState.active_session_id)
    else localStorage.removeItem(`studentActiveSession:${sid}`)
  }, [currentViewState, verifiedStudent?.student_id])

  useEffect(() => {
    const sid = verifiedStudent?.student_id?.trim() || ''
    if (!sid || !viewStateSyncReady) return
    if (applyingViewStateRef.current) {
      applyingViewStateRef.current = false
      return
    }
    setViewStateUpdatedAt(new Date().toISOString())
  }, [activeSessionId, deletedSessionIds, sessionTitleMap, verifiedStudent?.student_id, viewStateSyncReady])

  useEffect(() => {
    const sid = verifiedStudent?.student_id?.trim() || ''
    if (!sid || !viewStateSyncReady) return
    const signature = buildSessionViewStateSignature(currentViewState)
    if (signature === lastSyncedViewStateSignatureRef.current) return
    const timer = window.setTimeout(async () => {
      try {
        const payload = normalizeSessionViewStatePayload(currentViewState)
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

    setMessages((prev) => [
      ...prev,
      { id: makeId(), role: 'user', content: trimmed, time: nowTime() },
      { id: placeholderId, role: 'assistant', content: '正在生成…', time: nowTime() },
    ])
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
    const deleted = new Set(deletedSessionIds)
    const q = historyQuery.trim().toLowerCase()
    return sessions.filter((item) => {
      const sid = String(item.session_id || '').trim()
      if (!sid || deleted.has(sid)) return false
      if (!q) return true
      const title = (sessionTitleMap[sid] || '').toLowerCase()
      const preview = (item.preview || '').toLowerCase()
      return sid.toLowerCase().includes(q) || title.includes(q) || preview.includes(q)
    })
  }, [sessions, deletedSessionIds, historyQuery, sessionTitleMap])

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

  const startNewStudentSession = useCallback(() => {
    const next = `general_${todayDate()}_${Math.random().toString(16).slice(2, 6)}`
    sessionRequestRef.current += 1
    setLocalDraftSessionIds((prev) => (prev.includes(next) ? prev : [next, ...prev]))
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
      const nextTitle = window.prompt('输入会话名称', getSessionTitle(sid))
      if (nextTitle == null) {
        setOpenSessionMenuId('')
        return
      }
      const title = nextTitle.trim()
      setSessionTitleMap((prev) => {
        const next = { ...prev }
        if (title) next[sid] = title
        else delete next[sid]
        return next
      })
      setOpenSessionMenuId('')
    },
    [getSessionTitle],
  )

  const toggleSessionMenu = useCallback(
    (sessionId: string) => {
      const sid = String(sessionId || '').trim()
      if (!sid) return
      setOpenSessionMenuId((prev) => (prev === sid ? '' : sid))
    },
    [],
  )

  const deleteSession = useCallback(
    (sessionId: string) => {
      const sid = String(sessionId || '').trim()
      if (!sid) return
      if (!window.confirm(`确认删除会话 ${getSessionTitle(sid)}？`)) return
      setOpenSessionMenuId('')
      setDeletedSessionIds((prev) => (prev.includes(sid) ? prev : [...prev, sid]))
      setLocalDraftSessionIds((prev) => prev.filter((id) => id !== sid))
      if (activeSessionId === sid) {
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
    },
    [activeSessionId, getSessionTitle, startNewStudentSession, visibleSessions],
  )

  return (
    <div className="app">
      <header className="topbar">
        <div className="top-left">
          <div className="brand">物理学习助手 · 学生端</div>
          <button className="ghost" type="button" onClick={() => setSidebarOpen((prev) => !prev)}>
            {sidebarOpen ? '收起会话' : '展开会话'}
          </button>
          <button className="ghost" onClick={startNewStudentSession}>
            新会话
          </button>
        </div>
        <div className="top-actions">
          <div className="role-badge student">身份：学生</div>
          <button className="ghost" onClick={() => setSettingsOpen((prev) => !prev)}>
            设置
          </button>
        </div>
      </header>

      {settingsOpen && (
        <section className="settings">
          <div className="settings-row">
            <label>接口地址</label>
            <input value={apiBase} onChange={(e) => setApiBase(e.target.value)} placeholder="http://localhost:8000" />
          </div>
          <div className="settings-hint">
            修改后立即生效。{verifiedStudent?.student_id ? ` 当前学生：${verifiedStudent.student_id}` : ''}
          </div>
        </section>
      )}

      <div className={`student-layout ${sidebarOpen ? 'sidebar-open' : 'sidebar-collapsed'}`}>
        <button
          type="button"
          className={`sidebar-overlay ${sidebarOpen ? 'show' : ''}`}
          aria-label="关闭会话侧栏"
          onClick={() => setSidebarOpen(false)}
        />
        <aside className={`session-sidebar ${sidebarOpen ? 'open' : 'collapsed'}`}>
          <div className="session-sidebar-header">
            <strong>历史会话</strong>
            <div className="session-sidebar-actions">
              <button type="button" className="ghost" onClick={startNewStudentSession}>
                新建
              </button>
              <button
                type="button"
                className="ghost"
                disabled={!verifiedStudent || historyLoading}
                onClick={() => void refreshSessions()}
              >
                {historyLoading ? '刷新中…' : '刷新'}
              </button>
            </div>
          </div>
          <div className="session-search">
            <input
              value={historyQuery}
              onChange={(e) => setHistoryQuery(e.target.value)}
              placeholder="搜索会话"
              disabled={!verifiedStudent}
            />
          </div>
          {!verifiedStudent && <div className="history-hint">请先完成姓名验证后查看历史记录。</div>}
          {historyError && <div className="status err">{historyError}</div>}
          {verifiedStudent && !historyLoading && visibleSessions.length === 0 && !historyError && (
            <div className="history-hint">暂无历史记录。</div>
          )}
          <div className="session-groups">
            {groupedSessions.map((group) => (
              <div key={group.key} className="session-group">
                <div className="session-group-title">{group.label}</div>
                <div className="session-list">
                  {group.items.map((item) => {
                    const sid = item.session_id
                    const isActive = sid === activeSessionId
                    const isMenuOpen = sid === openSessionMenuId
                    const updatedLabel = formatSessionUpdatedLabel(item.updated_at)
                    return (
                      <div key={sid} className={`session-item ${isActive ? 'active' : ''}`}>
                        <button
                          type="button"
                          className="session-select"
                          onClick={() => {
                            setActiveSessionId(sid)
                            setSessionCursor(-1)
                            setSessionHasMore(false)
                            setSessionError('')
                            setOpenSessionMenuId('')
                            closeSidebarOnMobile()
                          }}
                        >
                          <div className="session-main">
                            <div className="session-id">{getSessionTitle(sid)}</div>
                            <div className="session-meta">
                              {(item.message_count || 0).toString()} 条{updatedLabel ? ` · ${updatedLabel}` : ''}
                            </div>
                          </div>
                          {item.preview ? <div className="session-preview">{item.preview}</div> : null}
                        </button>
                        <div className="session-menu-wrap">
                          <button
                            type="button"
                            className="session-menu-trigger"
                            aria-haspopup="menu"
                            aria-expanded={isMenuOpen}
                            aria-label={`会话 ${getSessionTitle(sid)} 操作`}
                            onClick={(e) => {
                              e.stopPropagation()
                              toggleSessionMenu(sid)
                            }}
                          >
                            ⋯
                          </button>
                          {isMenuOpen ? (
                            <div className="session-menu" role="menu">
                              <button
                                type="button"
                                className="session-menu-item"
                                onClick={() => {
                                  renameSession(sid)
                                }}
                              >
                                重命名
                              </button>
                              <button
                                type="button"
                                className="session-menu-item danger"
                                onClick={() => {
                                  deleteSession(sid)
                                }}
                              >
                                删除
                              </button>
                            </div>
                          ) : null}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
          {verifiedStudent && (
            <div className="history-footer">
              <button type="button" className="ghost" disabled={!historyHasMore || historyLoading} onClick={() => void refreshSessions('more')}>
                {historyLoading ? '加载中…' : historyHasMore ? '加载更多会话' : '已显示全部会话'}
              </button>
            </div>
          )}
          {verifiedStudent && activeSessionId && (
            <div className="history-footer">
              <button
                type="button"
                className="ghost"
                disabled={!sessionHasMore || sessionLoading}
                onClick={() => void loadSessionMessages(activeSessionId, sessionCursor, true)}
              >
                {sessionLoading ? '加载中…' : sessionHasMore ? '加载更早消息' : '没有更早消息'}
              </button>
              {sessionError && <div className="status err">{sessionError}</div>}
            </div>
          )}

          <section className="student-side-card">
            <div className="student-side-header">
              <strong>学习信息</strong>
              <button type="button" className="ghost" onClick={() => setVerifyOpen((prev) => !prev)}>
                {verifyOpen ? '收起' : '展开'}
              </button>
            </div>
            {verifiedStudent ? (
              <div className="history-hint">
                已验证：{verifiedStudent.class_name ? `${verifiedStudent.class_name} · ` : ''}
                {verifiedStudent.student_name}
              </div>
            ) : (
              <div className="history-hint">请先完成姓名验证后开始提问。</div>
            )}
            {verifyOpen && (
              <form className="verify-form compact" onSubmit={handleVerify}>
                <div className="verify-row">
                  <label>姓名</label>
                  <input value={nameInput} onChange={(e) => setNameInput(e.target.value)} placeholder="例如：刘昊然" />
                </div>
                <div className="verify-row">
                  <label>班级（重名时必填）</label>
                  <input value={classInput} onChange={(e) => setClassInput(e.target.value)} placeholder="例如：高二2403班" />
                </div>
                <button type="submit" disabled={verifying}>
                  {verifying ? '验证中…' : '确认身份'}
                </button>
                {verifyError && <div className="status err">{verifyError}</div>}
              </form>
            )}
            {verifiedStudent && (
              <div className="assignment-compact">
                <div className="assignment-meta">今日作业（{todayAssignment?.date || todayDate()}）</div>
                {assignmentLoading && <div className="assignment-status">加载中...</div>}
                {assignmentError && <div className="assignment-status err">{assignmentError}</div>}
                {!assignmentLoading && !todayAssignment && !assignmentError && <div className="assignment-empty">今日暂无作业。</div>}
                {todayAssignment && (
                  <>
                    <div className="assignment-meta">
                      作业编号：{todayAssignment.assignment_id || '-'} · 题数：{todayAssignment.question_count || 0}
                    </div>
                    {todayAssignment.meta?.target_kp?.length ? (
                      <div className="assignment-meta">知识点：{todayAssignment.meta.target_kp.join('，')}</div>
                    ) : null}
                    {todayAssignment.delivery?.files?.length ? (
                      <div className="download-list">
                        {todayAssignment.delivery.files.map((file) => (
                          <a key={file.url} className="download-link" href={`${apiBase}${file.url}`} target="_blank" rel="noreferrer">
                            下载：{file.name}
                          </a>
                        ))}
                      </div>
                    ) : (
                      <div className="assignment-note">在聊天中输入“开始今天作业”进入讨论。</div>
                    )}
                  </>
                )}
              </div>
            )}
            {verifiedStudent && (
              <button
                type="button"
                className="ghost"
                onClick={() => {
                  setVerifiedStudent(null)
                  setNameInput('')
                  setClassInput('')
                  setVerifyError('')
                  setVerifyOpen(true)
                }}
              >
                重新验证
              </button>
            )}
          </section>
        </aside>

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
