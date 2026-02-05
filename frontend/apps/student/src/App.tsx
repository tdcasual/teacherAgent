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
          throw new Error(text || `HTTP ${res.status}`)
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

  const appendMessage = (roleType: 'user' | 'assistant', content: string) => {
    setMessages((prev) => [...prev, { id: makeId(), role: roleType, content, time: nowTime() }])
  }

  const handleSend = async (event: FormEvent) => {
    event.preventDefault()
    if (!verifiedStudent) {
      setVerifyError('请先填写姓名并完成验证。')
      setVerifyOpen(true)
      return
    }
    const trimmed = input.trim()
    if (!trimmed) return

    appendMessage('user', trimmed)
    setInput('')

    const contextMessages = [...messages, { id: 'temp', role: 'user' as const, content: trimmed, time: '' }]
      .slice(-20)
      .map((msg) => ({ role: msg.role, content: msg.content }))

    setSending(true)
    try {
      const res = await fetch(`${apiBase}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: contextMessages,
          role: 'student',
          student_id: verifiedStudent.student_id,
          assignment_id: todayAssignment?.assignment_id,
          assignment_date: todayDate(),
        }),
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `HTTP ${res.status}`)
      }
      const data = (await res.json()) as ChatResponse
      appendMessage('assistant', data.reply || '已收到。')
    } catch (err: any) {
      appendMessage('assistant', `抱歉，请求失败：${err.message || err}`)
    } finally {
      setSending(false)
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
        throw new Error(text || `HTTP ${res.status}`)
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
        <div className="brand">Physics Learning Helper · 学生端</div>
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
            <label>API 地址</label>
            <input value={apiBase} onChange={(e) => setApiBase(e.target.value)} placeholder="http://localhost:8000" />
          </div>
          <div className="settings-hint">修改后立即生效。</div>
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
          {sending && (
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
                作业ID：{todayAssignment.assignment_id || '-'} · 题数：{todayAssignment.question_count || 0}
              </div>
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

        <form className={`composer ${!verifiedStudent ? 'disabled' : ''}`} onSubmit={handleSend}>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={verifiedStudent ? '输入问题，例如：牛顿第三定律是什么' : '请先填写姓名完成验证'}
            rows={3}
            disabled={!verifiedStudent}
          />
          <div className="composer-actions">
            <button type="submit" className="send-btn" disabled={sending || !verifiedStudent}>
              发送
            </button>
          </div>
        </form>
      </main>
    </div>
  )
}
