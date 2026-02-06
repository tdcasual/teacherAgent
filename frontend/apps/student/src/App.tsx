import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
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

type StudentHistorySessionsResponse = {
  ok: boolean
  student_id: string
  sessions: StudentHistorySession[]
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

export default function App() {
  const [apiBase, setApiBase] = useState(() => localStorage.getItem('apiBaseStudent') || DEFAULT_API_URL)
  const [messages, setMessages] = useState<Message[]>(() => [
    {
      id: makeId(),
      role: 'assistant',
      content: '学生端已就绪。请先填写姓名完成验证，然后开始提问或进入作业讨论。',
      time: nowTime(),
    },
  ])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const endRef = useRef<HTMLDivElement | null>(null)

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
  const markdownCacheRef = useRef(new Map<string, { content: string; html: string }>())

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
  const [activeSessionId, setActiveSessionId] = useState('')
  const [sessionLoading, setSessionLoading] = useState(false)
  const [sessionError, setSessionError] = useState('')
  const [sessionCursor, setSessionCursor] = useState(0)
  const [sessionHasMore, setSessionHasMore] = useState(false)

  useEffect(() => {
    localStorage.setItem('apiBaseStudent', apiBase)
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

  const renderedMessages = useMemo(() => {
    const cache = markdownCacheRef.current
    return messages.map((msg): RenderedMessage => {
      const cached = cache.get(msg.id)
      if (cached && cached.content === msg.content) return { ...msg, html: cached.html }
      const html = renderMarkdown(msg.content)
      cache.set(msg.id, { content: msg.content, html })
      return { ...msg, html }
    })
  }, [messages])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

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

  const refreshSessions = async () => {
    const sid = verifiedStudent?.student_id?.trim() || ''
    if (!sid) return
    setHistoryLoading(true)
    setHistoryError('')
    try {
      const url = new URL(`${apiBase}/student/history/sessions`)
      url.searchParams.set('student_id', sid)
      url.searchParams.set('limit', '30')
      const res = await fetch(url.toString())
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `状态码 ${res.status}`)
      }
      const data = (await res.json()) as StudentHistorySessionsResponse
      setSessions(Array.isArray(data.sessions) ? data.sessions : [])
    } catch (err: any) {
      setHistoryError(err.message || String(err))
    } finally {
      setHistoryLoading(false)
    }
  }

  const loadSessionMessages = async (sessionId: string, cursor: number, append: boolean) => {
    const sid = verifiedStudent?.student_id?.trim() || ''
    if (!sid || !sessionId) return
    setSessionLoading(true)
    setSessionError('')
    try {
      const LIMIT = 80
      const url = new URL(`${apiBase}/student/history/session`)
      url.searchParams.set('student_id', sid)
      url.searchParams.set('session_id', sessionId)
      url.searchParams.set('cursor', String(cursor))
      url.searchParams.set('limit', String(LIMIT))
      url.searchParams.set('direction', 'backward')
      const res = await fetch(url.toString())
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `状态码 ${res.status}`)
      }
      const data = (await res.json()) as StudentHistorySessionResponse
      const raw = Array.isArray(data.messages) ? data.messages : []
      const mapped: Message[] = raw
        .map((m, idx) => {
          const roleRaw = String(m.role || '').toLowerCase()
          const role = roleRaw === 'assistant' ? 'assistant' : roleRaw === 'user' ? 'user' : null
          const content = typeof m.content === 'string' ? m.content : ''
          if (!role || !content) return null
          return {
            id: `hist_${sessionId}_${cursor}_${idx}_${m.ts || ''}`,
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
        setMessages((prev) => {
          const greeting = prev[0]
          return mapped.length ? mapped : greeting ? [greeting] : prev
        })
      }
    } catch (err: any) {
      setSessionError(err.message || String(err))
    } finally {
      setSessionLoading(false)
    }
  }

  useEffect(() => {
    if (!verifiedStudent?.student_id) return
    void refreshSessions()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [verifiedStudent?.student_id, apiBase])

  useEffect(() => {
    if (!historyOpen) return
    if (!verifiedStudent?.student_id) return
    void refreshSessions()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [historyOpen])

  useEffect(() => {
    const sid = verifiedStudent?.student_id?.trim() || ''
    if (!sid) return
    try {
      const raw = localStorage.getItem(`studentActiveSession:${sid}`)
      if (raw && !activeSessionId) setActiveSessionId(raw)
    } catch {
      // ignore
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [verifiedStudent?.student_id])

  useEffect(() => {
    const sid = verifiedStudent?.student_id?.trim() || ''
    if (!sid) return
    if (!activeSessionId) return
    try {
      localStorage.setItem(`studentActiveSession:${sid}`, activeSessionId)
    } catch {
      // ignore
    }
  }, [activeSessionId, verifiedStudent?.student_id])

  useEffect(() => {
    if (!verifiedStudent?.student_id) return
    if (pendingChatJob?.job_id) return
    if (activeSessionId) return
    const next = todayAssignment?.assignment_id || `general_${todayDate()}`
    setActiveSessionId(next)
  }, [verifiedStudent?.student_id, todayAssignment?.assignment_id, pendingChatJob?.job_id, activeSessionId])

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

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">物理学习助手 · 学生端</div>
        <div className="top-actions">
          <div className="role-badge student">身份：学生</div>
          <button className="ghost" onClick={() => setHistoryOpen((prev) => !prev)}>
            历史
          </button>
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

      {historyOpen && (
        <section className="history-panel">
          <div className="history-header">
            <strong>历史会话</strong>
            <div className="history-actions">
              <button
                type="button"
                className="ghost"
                disabled={!verifiedStudent || historyLoading}
                onClick={() => void refreshSessions()}
              >
                {historyLoading ? '刷新中…' : '刷新'}
              </button>
              <button
                type="button"
                className="ghost"
                disabled={!verifiedStudent}
                onClick={() => {
                  const next = `general_${todayDate()}_${Math.random().toString(16).slice(2, 6)}`
                  setActiveSessionId(next)
                  setSessionCursor(-1)
                  setSessionHasMore(false)
                  setSessionError('')
                  setMessages([
                    {
                      id: makeId(),
                      role: 'assistant',
                      content: '已开启新会话。你可以继续提问，或输入“开始今天作业”。',
                      time: nowTime(),
                    },
                  ])
                  setHistoryOpen(false)
                }}
              >
                新会话
              </button>
            </div>
          </div>
          {!verifiedStudent && <div className="history-hint">请先完成姓名验证后查看历史记录。</div>}
          {historyError && <div className="status err">{historyError}</div>}
          {verifiedStudent && !historyLoading && sessions.length === 0 && !historyError && (
            <div className="history-hint">暂无历史记录。</div>
          )}
          {verifiedStudent && sessions.length > 0 && (
            <div className="session-list">
              {sessions.map((s) => (
                <button
                  key={s.session_id}
                  type="button"
                  className={`session-item ${s.session_id === activeSessionId ? 'active' : ''}`}
                  onClick={() => {
                    setActiveSessionId(s.session_id)
                    setSessionCursor(-1)
                    setSessionHasMore(false)
                    setSessionError('')
                    setHistoryOpen(false)
                  }}
                >
                  <div className="session-main">
                    <div className="session-id">{s.session_id}</div>
                    <div className="session-meta">
                      {(s.message_count || 0).toString()} 条{ s.updated_at ? ` · ${s.updated_at}` : '' }
                    </div>
                  </div>
                  {s.preview ? <div className="session-preview">{s.preview}</div> : null}
                </button>
              ))}
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
        </section>
      )}

      <main className="chat-shell">
        <div className="messages">
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

        <section className={`verify-card ${verifiedStudent ? 'collapsed' : ''}`}>
          <div className="verify-header">
            <div>
              <strong>姓名验证</strong>
              {verifiedStudent && (
                <div className="verify-summary">
                  已验证：{verifiedStudent.class_name ? `${verifiedStudent.class_name} · ` : ''}
                  {verifiedStudent.student_name}
                </div>
              )}
            </div>
            <div className="verify-actions">
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
              <button type="button" className="ghost" onClick={() => setVerifyOpen((prev) => !prev)}>
                {verifyOpen ? '收起' : '展开'}
              </button>
            </div>
          </div>
          {verifyOpen && (
            <form className="verify-form" onSubmit={handleVerify}>
              <div className="verify-row">
                <label>姓名</label>
                <input
                  value={nameInput}
                  onChange={(e) => setNameInput(e.target.value)}
                  placeholder="例如：刘昊然"
                />
              </div>
              <div className="verify-row">
                <label>班级（重名时必填）</label>
                <input
                  value={classInput}
                  onChange={(e) => setClassInput(e.target.value)}
                  placeholder="例如：高二2403班"
                />
              </div>
              <button type="submit" disabled={verifying}>
                {verifying ? '验证中…' : '确认身份'}
              </button>
              {verifyError && <div className="status err">{verifyError}</div>}
            </form>
          )}
          {!verifyOpen && !verifiedStudent && <div className="verify-note">请先输入姓名完成验证。</div>}
          {!verifyOpen && verifiedStudent && <div className="verify-note">验证通过，现在可以开始提问。</div>}
        </section>

        <section className="assignment-card">
          <div className="assignment-header">
            <div>
              <strong>今日作业</strong>
              <span className="assignment-date">（{todayAssignment?.date || todayDate()}）</span>
            </div>
          </div>
          {!verifiedStudent && <div className="assignment-empty">请先完成姓名验证后查看今日作业。</div>}
          {verifiedStudent && assignmentLoading && <div className="assignment-status">加载中...</div>}
          {verifiedStudent && assignmentError && <div className="assignment-status err">{assignmentError}</div>}
          {verifiedStudent && !assignmentLoading && !todayAssignment && !assignmentError && (
            <div className="assignment-empty">今日暂无作业。</div>
          )}
          {verifiedStudent && todayAssignment && (
            <>
              <div className="assignment-meta">
                作业编号：{todayAssignment.assignment_id || '-'} · 题数：{todayAssignment.question_count || 0}
              </div>
              {activeSessionId ? <div className="assignment-meta">当前会话：{activeSessionId}</div> : null}
              {todayAssignment.meta?.target_kp?.length ? (
                <div className="assignment-meta">知识点：{todayAssignment.meta.target_kp.join('，')}</div>
              ) : null}
              {todayAssignment.delivery?.files?.length ? (
                <div className="assignment-downloads">
                  <div className="assignment-note">本次作业以文件形式下发，请下载后完成。</div>
                  <div className="download-list">
                    {todayAssignment.delivery.files.map((file) => (
                      <a
                        key={file.url}
                        className="download-link"
                        href={`${apiBase}${file.url}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        下载：{file.name}
                      </a>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="assignment-note">作业题目不会在此处展示，请在聊天中输入“开始今天作业”进入讨论。</div>
              )}
            </>
          )}
        </section>

        <form
          className={`composer ${!verifiedStudent || pendingChatJob?.job_id ? 'disabled' : ''}`}
          onSubmit={handleSend}
        >
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={verifiedStudent ? '输入问题，例如：牛顿第三定律是什么' : '请先填写姓名完成验证'}
            rows={3}
            disabled={!verifiedStudent || Boolean(pendingChatJob?.job_id)}
          />
          <div className="composer-actions">
            <button type="submit" className="send-btn" disabled={sending || !verifiedStudent || Boolean(pendingChatJob?.job_id)}>
              发送
            </button>
          </div>
        </form>
      </main>
    </div>
  )
}
