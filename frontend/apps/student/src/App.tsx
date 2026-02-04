import { useEffect, useRef, useState, type FormEvent } from 'react'
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

type ChatResponse = {
  reply: string
}

const makeId = () => `${Date.now()}-${Math.random().toString(16).slice(2)}`

const nowTime = () => new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })

const removeEmptyParagraphs = () => {
  return (tree: any) => {
    visit(tree, 'paragraph', (node: any, index: number, parent: any) => {
      if (!parent || typeof index !== 'number') return
      if (!node.children || node.children.length === 0) {
        parent.children.splice(index, 1)
      }
    })
  }
}

const katexSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    span: [...(defaultSchema.attributes?.span || []), 'class', 'style'],
    div: [...(defaultSchema.attributes?.div || []), 'class', 'style'],
    code: [...(defaultSchema.attributes?.code || []), 'class'],
  },
}

const processor = unified()
  .use(remarkParse)
  .use(remarkGfm)
  .use(remarkMath)
  .use(removeEmptyParagraphs)
  .use(remarkRehype)
  .use(rehypeKatex)
  .use(rehypeSanitize, katexSchema)
  .use(rehypeStringify)

const renderMarkdown = (content: string) => {
  const result = processor.processSync(content || '')
  return String(result)
}

export default function App() {
  const [apiBase, setApiBase] = useState(() => localStorage.getItem('apiBaseStudent') || DEFAULT_API_URL)
  const [messages, setMessages] = useState<Message[]>(() => [
    {
      id: makeId(),
      role: 'assistant',
      content: '学生端已就绪。你可以直接提问学科问题，也可以在下方提交作业。',
      time: nowTime(),
    },
  ])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const endRef = useRef<HTMLDivElement | null>(null)

  const [studentId, setStudentId] = useState('')
  const [assignmentId, setAssignmentId] = useState('')
  const [autoDetect, setAutoDetect] = useState(true)
  const [files, setFiles] = useState<File[]>([])
  const [submitStatus, setSubmitStatus] = useState('')
  const [submitError, setSubmitError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    localStorage.setItem('apiBaseStudent', apiBase)
  }, [apiBase])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  const appendMessage = (roleType: 'user' | 'assistant', content: string) => {
    setMessages((prev) => [...prev, { id: makeId(), role: roleType, content, time: nowTime() }])
  }

  const handleSend = async (event: FormEvent) => {
    event.preventDefault()
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
        body: JSON.stringify({ messages: contextMessages, role: 'student' }),
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

  const handleSubmitAssignment = async (event: FormEvent) => {
    event.preventDefault()
    setSubmitError('')
    setSubmitStatus('')
    if (!studentId.trim()) {
      setSubmitError('请填写学生ID')
      return
    }
    if (!files.length) {
      setSubmitError('请至少选择一张作业图片')
      return
    }
    setSubmitting(true)
    try {
      const fd = new FormData()
      fd.append('student_id', studentId.trim())
      if (assignmentId.trim()) fd.append('assignment_id', assignmentId.trim())
      fd.append('auto_assignment', autoDetect ? 'true' : 'false')
      files.forEach((file) => fd.append('files', file))
      const res = await fetch(`${apiBase}/student/submit`, { method: 'POST', body: fd })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `HTTP ${res.status}`)
      }
      const data = await res.json()
      setSubmitStatus(typeof data.output === 'string' ? data.output : JSON.stringify(data, null, 2))
      setFiles([])
    } catch (err: any) {
      setSubmitError(err.message || String(err))
    } finally {
      setSubmitting(false)
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
          {messages.map((msg) => (
            <div key={msg.id} className={`message ${msg.role}`}>
              <div className="bubble">
                <div className="meta">
                  {msg.role === 'user' ? '我' : '助手'} · {msg.time}
                </div>
                <div className="text markdown" dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }} />
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

        <form className="composer" onSubmit={handleSend}>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="输入问题，例如：牛顿第三定律是什么"
            rows={3}
          />
          <div className="composer-actions">
            <button type="submit" className="send-btn" disabled={sending}>
              发送
            </button>
          </div>
        </form>

        <section className="submit-card">
          <h3>作业提交</h3>
          <p>上传作业照片，系统将自动识别并生成初步反馈。</p>
          <form className="submit-form" onSubmit={handleSubmitAssignment}>
            <label>学生ID</label>
            <input value={studentId} onChange={(e) => setStudentId(e.target.value)} placeholder="高二2403班_武熙语" />
            <label>作业ID (可选)</label>
            <input value={assignmentId} onChange={(e) => setAssignmentId(e.target.value)} placeholder="A2403_2026-02-04" />
            <label className="checkbox">
              <input type="checkbox" checked={autoDetect} onChange={(e) => setAutoDetect(e.target.checked)} />
              自动识别作业ID
            </label>
            <label>作业照片</label>
            <input
              type="file"
              multiple
              accept="image/*"
              onChange={(e) => setFiles(Array.from(e.target.files || []))}
            />
            <button type="submit" disabled={submitting}>
              {submitting ? '提交中…' : '提交作业'}
            </button>
          </form>
          {submitError && <div className="status err">{submitError}</div>}
          {submitStatus && <pre className="status ok">{submitStatus}</pre>}
        </section>
      </main>
    </div>
  )
}
