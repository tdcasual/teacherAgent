import { useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
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

type Skill = {
  id: string
  title: string
  desc: string
  prompts: string[]
  examples: string[]
}

type SkillResponse = {
  skills: Array<{ id: string; title?: string; desc?: string }>
}

const skillPresets: Record<string, Pick<Skill, 'prompts' | 'examples'>> = {
  'physics-teacher-ops': {
    prompts: ['@physics-teacher-ops 请列出所有考试，并给出最新考试概览。'],
    examples: ['列出考试', '生成课前检测清单', '做一次考试分析'],
  },
  'physics-homework-generator': {
    prompts: ['@physics-homework-generator 生成作业 A2403_2026-02-04，知识点 KP-M01,KP-E04，每个 5 题。'],
    examples: ['生成作业 A2403_2026-02-04', '渲染作业 PDF'],
  },
  'physics-lesson-capture': {
    prompts: ['@physics-lesson-capture 采集课堂材料 L2403_2026-02-04，主题“静电场综合”。'],
    examples: ['采集课堂材料 L2403_2026-02-04', '列出课程'],
  },
  'physics-student-coach': {
    prompts: ['@physics-student-coach 查看学生画像 高二2403班_武熙语。'],
    examples: ['查看学生画像 武熙语', '导入学生名册'],
  },
  'physics-student-focus': {
    prompts: ['@physics-student-focus 请分析学生 高二2403班_武熙语 的最近作业表现。'],
    examples: ['分析学生 高二2403班_武熙语'],
  },
  'physics-core-examples': {
    prompts: ['@physics-core-examples 登记核心例题 CE001，知识点 KP-M01。'],
    examples: ['登记核心例题 CE001', '生成变式题 3 道'],
  },
}

const fallbackSkills: Skill[] = [
  {
    id: 'physics-teacher-ops',
    title: '教师运营',
    desc: '考试分析、课前检测、教学备课与课堂讨论。',
    ...skillPresets['physics-teacher-ops'],
  },
  {
    id: 'physics-homework-generator',
    title: '作业生成',
    desc: '基于课堂讨论生成课后诊断与作业。',
    ...skillPresets['physics-homework-generator'],
  },
  {
    id: 'physics-lesson-capture',
    title: '课堂采集',
    desc: 'OCR 课堂材料并抽取例题与讨论结构。',
    ...skillPresets['physics-lesson-capture'],
  },
  {
    id: 'physics-student-coach',
    title: '学生教练',
    desc: '学生侧讨论、作业、OCR 评分与画像更新。',
    ...skillPresets['physics-student-coach'],
  },
  {
    id: 'physics-student-focus',
    title: '学生重点分析',
    desc: '针对某个学生进行重点诊断与画像更新。',
    ...skillPresets['physics-student-focus'],
  },
  {
    id: 'physics-core-examples',
    title: '核心例题库',
    desc: '登记核心例题、标准解法与变式题。',
    ...skillPresets['physics-core-examples'],
  },
]

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

const remarkLatexBrackets = () => {
  return (tree: any) => {
    visit(tree, 'text', (node: any, index: number, parent: any) => {
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

const buildSkill = (skill: { id: string; title?: string; desc?: string }): Skill => {
  const preset = skillPresets[skill.id]
  const prompts = preset?.prompts ?? [`@${skill.id} 请描述你的需求。`]
  const examples = preset?.examples ?? []
  return {
    id: skill.id,
    title: skill.title || skill.id,
    desc: skill.desc || '暂无描述',
    prompts,
    examples,
  }
}

export default function App() {
  const [apiBase, setApiBase] = useState(() => localStorage.getItem('apiBaseTeacher') || DEFAULT_API_URL)
  const [messages, setMessages] = useState<Message[]>(() => [
    {
      id: makeId(),
      role: 'assistant',
      content:
        '老师端已就绪。你可以直接提需求，例如：\n- 列出考试\n- 导入学生名册\n- 生成作业\n\n在输入框中输入 `@` 可以看到技能提示。',
      time: nowTime(),
    },
  ])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [skillsOpen, setSkillsOpen] = useState(() => localStorage.getItem('teacherSkillsOpen') !== 'false')
  const [cursorPos, setCursorPos] = useState(0)
  const [skillQuery, setSkillQuery] = useState('')
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false)
  const [favorites, setFavorites] = useState<string[]>(() => {
    try {
      return JSON.parse(localStorage.getItem('teacherSkillFavorites') || '[]')
    } catch {
      return []
    }
  })
  const [skillList, setSkillList] = useState<Skill[]>(fallbackSkills)
  const [skillsLoading, setSkillsLoading] = useState(false)
  const [skillsError, setSkillsError] = useState('')
  const [mentionIndex, setMentionIndex] = useState(0)

  const endRef = useRef<HTMLDivElement | null>(null)
  const inputRef = useRef<HTMLTextAreaElement | null>(null)

  useEffect(() => {
    localStorage.setItem('apiBaseTeacher', apiBase)
  }, [apiBase])

  useEffect(() => {
    localStorage.setItem('teacherSkillFavorites', JSON.stringify(favorites))
  }, [favorites])

  useEffect(() => {
    localStorage.setItem('teacherSkillsOpen', String(skillsOpen))
  }, [skillsOpen])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  useEffect(() => {
    const fetchSkills = async () => {
      setSkillsLoading(true)
      setSkillsError('')
      try {
        const res = await fetch(`${apiBase}/skills`)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = (await res.json()) as SkillResponse
        if (!data.skills || !Array.isArray(data.skills) || data.skills.length === 0) {
          setSkillList(fallbackSkills)
          return
        }
        setSkillList(data.skills.map((skill) => buildSkill(skill)))
      } catch (err: any) {
        setSkillsError(err.message || '无法加载技能列表')
        setSkillList(fallbackSkills)
      } finally {
        setSkillsLoading(false)
      }
    }
    fetchSkills()
  }, [apiBase])

  const appendMessage = (roleType: 'user' | 'assistant', content: string) => {
    setMessages((prev) => [...prev, { id: makeId(), role: roleType, content, time: nowTime() }])
  }

  const mention = useMemo(() => {
    const uptoCursor = input.slice(0, cursorPos)
    const match = /@([\w-]*)$/.exec(uptoCursor)
    if (!match) return null
    const query = match[1].toLowerCase()
    const items = skillList.filter(
      (skill) => skill.id.toLowerCase().includes(query) || skill.title.toLowerCase().includes(query)
    )
    return { start: match.index, query, items }
  }, [input, cursorPos, skillList])

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

  const insertSkillMention = (skill: Skill) => {
    if (!mention) return
    const template = skill.prompts[0] || `@${skill.id} `
    const before = input.slice(0, mention.start)
    const after = input.slice(cursorPos)
    const nextValue = `${before}${template} ${after}`.replace(/\s+$/, ' ')
    setInput(nextValue)
    requestAnimationFrame(() => {
      if (!inputRef.current) return
      const nextPos = `${before}${template} `.length
      inputRef.current.focus()
      inputRef.current.setSelectionRange(nextPos, nextPos)
      setCursorPos(nextPos)
    })
  }

  const toggleFavorite = (skillId: string) => {
    setFavorites((prev) => (prev.includes(skillId) ? prev.filter((id) => id !== skillId) : [...prev, skillId]))
  }

  const submitMessage = async () => {
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
        body: JSON.stringify({ messages: contextMessages, role: 'teacher' }),
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

  const handleSend = async (event: FormEvent) => {
    event.preventDefault()
    if (sending) return
    await submitMessage()
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
        const skill = mention.items[mentionIndex]
        if (skill) insertSkillMention(skill)
        return
      }
    }

    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void submitMessage()
    }
  }

  return (
    <div className="app teacher">
      <header className="topbar">
        <div className="brand">Physics Teaching Helper · 老师端</div>
        <div className="top-actions">
          <div className="role-badge teacher">身份：老师</div>
          <button className="ghost" onClick={() => setSkillsOpen((prev) => !prev)}>
            技能
          </button>
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

      <div className="teacher-layout">
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
              ref={inputRef}
              value={input}
              onChange={(e) => {
                setInput(e.target.value)
                setCursorPos(e.target.selectionStart || e.target.value.length)
              }}
              onClick={(e) => setCursorPos((e.target as HTMLTextAreaElement).selectionStart || input.length)}
              onKeyUp={(e) => setCursorPos((e.target as HTMLTextAreaElement).selectionStart || input.length)}
              onKeyDown={handleKeyDown}
              placeholder="输入指令或问题，使用 @ 查看技能。Enter 发送，Shift+Enter 换行"
              rows={3}
            />
            <div className="composer-actions">
              <span className="composer-hint">@ 技能 | Enter 发送</span>
              <button type="submit" className="send-btn" disabled={sending}>
                发送
              </button>
            </div>
          </form>

          {mention && mention.items.length > 0 && (
            <div className="mention-panel">
              <div className="mention-title">技能建议（↑↓ 选择 / Enter 插入）</div>
              <div className="mention-list">
                {mention.items.map((skill, index) => (
                  <button
                    key={skill.id}
                    type="button"
                    className={index === mentionIndex ? 'active' : ''}
                    onClick={() => insertSkillMention(skill)}
                  >
                    <strong>@{skill.id}</strong>
                    <span>{skill.title}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </main>

        <aside className={`skills-panel ${skillsOpen ? 'open' : ''}`}>
          <div className="skills-header">
            <h3>技能提示</h3>
            <button className="ghost" onClick={() => setSkillsOpen(false)}>
              收起
            </button>
          </div>
          <div className="skills-tools">
            <input
              value={skillQuery}
              onChange={(e) => setSkillQuery(e.target.value)}
              placeholder="搜索技能"
            />
            <label className="toggle">
              <input
                type="checkbox"
                checked={showFavoritesOnly}
                onChange={(e) => setShowFavoritesOnly(e.target.checked)}
              />
              只看收藏
            </label>
          </div>
          {skillsLoading && <div className="skills-status">正在加载技能...</div>}
          {skillsError && <div className="skills-status err">{skillsError}</div>}
          <div className="skills-body">
            {filteredSkills.map((skill) => (
              <div key={skill.id} className="skill-card">
                <div className="skill-title">
                  <div>
                    <span>@{skill.id}</span>
                    <strong>{skill.title}</strong>
                  </div>
                  <button
                    type="button"
                    className={`fav ${favorites.includes(skill.id) ? 'active' : ''}`}
                    onClick={() => toggleFavorite(skill.id)}
                    aria-label="收藏技能"
                  >
                    {favorites.includes(skill.id) ? '★' : '☆'}
                  </button>
                </div>
                <p>{skill.desc}</p>
                <div className="skill-prompts">
                  {skill.prompts.map((prompt) => (
                    <button key={prompt} type="button" onClick={() => insertPrompt(prompt)}>
                      使用模板
                    </button>
                  ))}
                </div>
                <div className="skill-examples">
                  {skill.examples.map((ex) => (
                    <button key={ex} type="button" onClick={() => insertPrompt(ex)}>
                      {ex}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </aside>
      </div>
    </div>
  )
}
