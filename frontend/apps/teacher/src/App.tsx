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

type RenderedMessage = Message & { html: string }

type ChatResponse = {
  reply: string
}

type UploadJobStatus = {
  job_id: string
  status: 'queued' | 'processing' | 'done' | 'failed' | 'confirmed'
  progress?: number
  step?: string
  message?: string
  error?: string
  assignment_id?: string
  question_count?: number
  requirements_missing?: string[]
  warnings?: string[]
  delivery_mode?: string
  questions_preview?: Array<{ id: number; stem: string }>
  draft_saved?: boolean
}

type UploadDraft = {
  job_id: string
  assignment_id: string
  date: string
  scope: 'public' | 'class' | 'student'
  class_name?: string
  student_ids?: string[]
  delivery_mode?: string
  source_files?: string[]
  answer_files?: string[]
  question_count?: number
  draft_version?: string | number
  requirements: Record<string, any>
  requirements_missing?: string[]
  warnings?: string[]
  questions: Array<Record<string, any>>
  draft_saved?: boolean
}

type ExamUploadJobStatus = {
  job_id: string
  status: 'queued' | 'processing' | 'done' | 'failed' | 'confirmed' | 'confirming'
  progress?: number
  step?: string
  error?: string
  error_detail?: string
  exam_id?: string
  counts?: { students?: number; responses?: number; questions?: number }
  totals_summary?: Record<string, any>
  warnings?: string[]
}

type ExamUploadDraft = {
  job_id: string
  exam_id: string
  date?: string
  class_name?: string
  paper_files?: string[]
  score_files?: string[]
  counts?: Record<string, any>
  totals_summary?: Record<string, any>
  meta: Record<string, any>
  questions: Array<Record<string, any>>
  score_schema?: Record<string, any>
  warnings?: string[]
  draft_version?: string | number
  draft_saved?: boolean
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
  const [uploadMode, setUploadMode] = useState<'assignment' | 'exam'>(() => {
    const raw = localStorage.getItem('teacherUploadMode')
    return raw === 'exam' ? 'exam' : 'assignment'
  })
  const [uploadAssignmentId, setUploadAssignmentId] = useState('')
  const [uploadDate, setUploadDate] = useState('')
  const [uploadScope, setUploadScope] = useState<'public' | 'class' | 'student'>('public')
  const [uploadClassName, setUploadClassName] = useState('')
  const [uploadStudentIds, setUploadStudentIds] = useState('')
  const [uploadFiles, setUploadFiles] = useState<File[]>([])
  const [uploadAnswerFiles, setUploadAnswerFiles] = useState<File[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadStatus, setUploadStatus] = useState('')
  const [uploadError, setUploadError] = useState('')
  const [uploadCardCollapsed, setUploadCardCollapsed] = useState(false)
  const [uploadJobId, setUploadJobId] = useState('')
  const [uploadJobInfo, setUploadJobInfo] = useState<UploadJobStatus | null>(null)
  const [uploadConfirming, setUploadConfirming] = useState(false)
  const [uploadStatusPollNonce, setUploadStatusPollNonce] = useState(0)
  const [uploadDraft, setUploadDraft] = useState<UploadDraft | null>(null)
  const [draftPanelCollapsed, setDraftPanelCollapsed] = useState(false)
  const [draftLoading, setDraftLoading] = useState(false)
  const [draftError, setDraftError] = useState('')
  const [questionShowCount, setQuestionShowCount] = useState(20)
  const [draftSaving, setDraftSaving] = useState(false)
  const [draftActionStatus, setDraftActionStatus] = useState('')
  const [draftActionError, setDraftActionError] = useState('')
  const [misconceptionsText, setMisconceptionsText] = useState('')
  const [misconceptionsDirty, setMisconceptionsDirty] = useState(false)

  const [examId, setExamId] = useState('')
  const [examDate, setExamDate] = useState('')
  const [examClassName, setExamClassName] = useState('')
  const [examPaperFiles, setExamPaperFiles] = useState<File[]>([])
  const [examScoreFiles, setExamScoreFiles] = useState<File[]>([])
  const [examUploading, setExamUploading] = useState(false)
  const [examUploadStatus, setExamUploadStatus] = useState('')
  const [examUploadError, setExamUploadError] = useState('')
  const [examJobId, setExamJobId] = useState('')
  const [examJobInfo, setExamJobInfo] = useState<ExamUploadJobStatus | null>(null)
  const [examStatusPollNonce, setExamStatusPollNonce] = useState(0)
  const [examDraft, setExamDraft] = useState<ExamUploadDraft | null>(null)
  const [examDraftPanelCollapsed, setExamDraftPanelCollapsed] = useState(false)
  const [examDraftLoading, setExamDraftLoading] = useState(false)
  const [examDraftError, setExamDraftError] = useState('')
  const [examDraftSaving, setExamDraftSaving] = useState(false)
  const [examDraftActionStatus, setExamDraftActionStatus] = useState('')
  const [examDraftActionError, setExamDraftActionError] = useState('')
  const [examConfirming, setExamConfirming] = useState(false)

  const endRef = useRef<HTMLDivElement | null>(null)
  const inputRef = useRef<HTMLTextAreaElement | null>(null)
  const markdownCacheRef = useRef(new Map<string, { content: string; html: string }>())

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
    localStorage.setItem('teacherUploadMode', uploadMode)
  }, [uploadMode])

  useEffect(() => {
    // Refresh recovery: resume polling for the last active upload job.
    const raw = localStorage.getItem('teacherActiveUpload')
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
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  const renderedMessages = useMemo(() => {
    const cache = markdownCacheRef.current
    return messages.map((msg): RenderedMessage => {
      const cached = cache.get(msg.id)
      if (cached && cached.content === msg.content) {
        return { ...msg, html: cached.html }
      }
      const html = renderMarkdown(msg.content)
      cache.set(msg.id, { content: msg.content, html })
      return { ...msg, html }
    })
  }, [messages])

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

  const formatUploadJobStatus = (job: UploadJobStatus) => {
    const lines: string[] = []
    const statusMap: Record<string, string> = {
      queued: '排队中',
      processing: '解析中',
      done: '解析完成（待确认）',
      failed: '解析失败',
      confirmed: '已创建作业',
    }
    lines.push(`解析状态：${statusMap[job.status] || job.status}`)
    if (job.progress !== undefined) lines.push(`进度：${job.progress}%`)
    if (job.assignment_id) lines.push(`作业ID：${job.assignment_id}`)
    if (job.question_count !== undefined) lines.push(`题目数量：${job.question_count}`)
    if (job.delivery_mode) lines.push(`交付方式：${job.delivery_mode === 'pdf' ? 'PDF' : '图片'}`)
    if (job.error) lines.push(`错误：${job.error}`)
    // Backend may include extra fields for better UX.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const extra = job as any
    if (extra.error_detail) lines.push(`详情：${extra.error_detail}`)
    if (Array.isArray(extra.hints) && extra.hints.length) lines.push(`建议：${extra.hints.join('；')}`)
    if (job.warnings && job.warnings.length) lines.push(`解析提示：${job.warnings.join('；')}`)
    if (job.requirements_missing && job.requirements_missing.length) {
      const missingLabelMap: Record<string, string> = {
        // 8-point requirements
        subject: '学科',
        topic: '主题',
        grade_level: '年级',
        class_level: '班级水平',
        core_concepts: '核心概念',
        typical_problem: '典型题型/例题',
        misconceptions: '易错点/易混点',
        duration_minutes: '作业时间',
        preferences: '作业偏好',
        extra_constraints: '额外限制',
        // per-question fields
        stem: '题干',
        answer: '答案',
        kp: '知识点',
        difficulty: '难度',
        score: '分值',
        tags: '标签',
        type: '题型',
      }
      const missingCn = job.requirements_missing.map((key) => missingLabelMap[key] || key)
      lines.push(`作业要求缺失项：${missingCn.join('、')}`)
    }
    if (job.questions_preview && job.questions_preview.length) {
      const previews = job.questions_preview.map((q) => `Q${q.id}：${q.stem}`).join('\n')
      lines.push(`题目预览：\n${previews}`)
    }
    return lines.join('\n')
  }

  const formatExamJobStatus = (job: ExamUploadJobStatus) => {
    const lines: string[] = []
    const statusMap: Record<string, string> = {
      queued: '排队中',
      processing: '解析中',
      done: '解析完成（待确认）',
      failed: '解析失败',
      confirmed: '已创建考试',
      confirming: '确认中',
    }
    lines.push(`解析状态：${statusMap[job.status] || job.status}`)
    if (job.progress !== undefined) lines.push(`进度：${job.progress}%`)
    if (job.exam_id) lines.push(`考试ID：${job.exam_id}`)
    if (job.counts?.students !== undefined) lines.push(`学生数：${job.counts.students}`)
    if (job.counts?.questions !== undefined) lines.push(`题目数：${job.counts.questions}`)
    if (job.error) lines.push(`错误：${job.error}`)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const extra = job as any
    if (extra.error_detail) lines.push(`详情：${extra.error_detail}`)
    if (Array.isArray(extra.hints) && extra.hints.length) lines.push(`建议：${extra.hints.join('；')}`)
    if (job.warnings && job.warnings.length) lines.push(`解析提示：${job.warnings.join('；')}`)
    return lines.join('\n')
  }

  const formatExamJobSummary = (job: ExamUploadJobStatus | null, fallbackExamId?: string) => {
    if (!job) return `未开始解析${fallbackExamId ? ` · 考试ID：${fallbackExamId}` : ''}`
    const statusMap: Record<string, string> = {
      queued: '排队中',
      processing: '解析中',
      done: '解析完成（待确认）',
      failed: '解析失败',
      confirmed: '已创建',
      confirming: '确认中',
    }
    const parts: string[] = []
    parts.push(`状态：${statusMap[job.status] || job.status}`)
    if (job.progress !== undefined) parts.push(`${job.progress}%`)
    parts.push(`考试ID：${job.exam_id || fallbackExamId || job.job_id}`)
    if (job.counts?.students !== undefined) parts.push(`学生：${job.counts.students}`)
    if (job.counts?.questions !== undefined) parts.push(`题目：${job.counts.questions}`)
    if (job.status === 'failed' && job.error) parts.push(`错误：${job.error}`)
    return parts.join(' · ')
  }

  const formatExamDraftSummary = (draft: ExamUploadDraft | null, jobInfo: ExamUploadJobStatus | null) => {
    if (!draft) return ''
    const parts: string[] = []
    parts.push(`考试ID：${draft.exam_id}`)
    if (draft.meta?.date) parts.push(String(draft.meta.date))
    if (draft.meta?.class_name) parts.push(String(draft.meta.class_name))
    if (draft.counts?.students !== undefined) parts.push(`学生：${draft.counts.students}`)
    if (draft.counts?.questions !== undefined) parts.push(`题目：${draft.counts.questions}`)
    if (jobInfo?.status === 'confirmed') parts.push('已创建')
    else if (jobInfo?.status === 'done') parts.push('待创建')
    return parts.join(' · ')
  }

  const formatUploadJobSummary = (job: UploadJobStatus | null, fallbackAssignmentId?: string) => {
    if (!job) return `未开始解析${fallbackAssignmentId ? ` · 作业ID：${fallbackAssignmentId}` : ''}`
    const statusMap: Record<string, string> = {
      queued: '排队中',
      processing: '解析中',
      done: '解析完成（待确认）',
      failed: '解析失败',
      confirmed: '已创建',
    }
    const parts: string[] = []
    parts.push(`状态：${statusMap[job.status] || job.status}`)
    if (job.progress !== undefined) parts.push(`${job.progress}%`)
    parts.push(`作业ID：${job.assignment_id || fallbackAssignmentId || job.job_id}`)
    if (job.question_count !== undefined) parts.push(`题目：${job.question_count}`)
    if (job.requirements_missing && job.requirements_missing.length) parts.push(`缺失：${job.requirements_missing.length}项`)
    if (job.status === 'failed' && job.error) parts.push(`错误：${job.error}`)
    return parts.join(' · ')
  }

  const formatDraftSummary = (draft: UploadDraft | null, jobInfo: UploadJobStatus | null) => {
    if (!draft) return ''
    const scopeLabel = draft.scope === 'public' ? '公共作业' : draft.scope === 'class' ? '班级作业' : '私人作业'
    const parts: string[] = []
    parts.push(`作业ID：${draft.assignment_id}`)
    if (draft.date) parts.push(draft.date)
    parts.push(scopeLabel)
    parts.push(`题目：${draft.questions?.length || 0}`)
    if (draft.requirements_missing && draft.requirements_missing.length) parts.push(`缺失：${draft.requirements_missing.length}项`)
    else parts.push('要求已补全')
    if (jobInfo?.status === 'confirmed') parts.push('已创建')
    else if (jobInfo?.status === 'done') parts.push('待创建')
    return parts.join(' · ')
  }

  useEffect(() => {
    if (!uploadJobId) return
    const BASE_DELAY_MS = 4000
    const MAX_DELAY_MS = 30000

    let cancelled = false
    let timeoutId: number | null = null
    let abortController: AbortController | null = null
    let inFlight = false
    let delayMs = BASE_DELAY_MS
    let lastFingerprint = ''

    const clearTimer = () => {
      if (timeoutId) window.clearTimeout(timeoutId)
      timeoutId = null
    }

    const abortInFlight = () => {
      try {
        abortController?.abort()
      } catch {
        // ignore
      }
      abortController = null
    }

    const scheduleNext = (ms: number) => {
      if (cancelled) return
      clearTimer()
      timeoutId = window.setTimeout(() => void poll(), ms)
    }

    const jitter = (ms: number) => {
      // +/- 20%
      const factor = 0.8 + Math.random() * 0.4
      return Math.round(ms * factor)
    }

    const makeFingerprint = (data: UploadJobStatus) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const extra = data as any
      const updatedAt = extra?.updated_at || extra?.updatedAt || ''
      const missing = Array.isArray(data.requirements_missing) ? data.requirements_missing.join(',') : ''
      const warnings = Array.isArray(data.warnings) ? data.warnings.length : 0
      return [
        data.status,
        data.progress ?? '',
        data.step ?? '',
        data.message ?? '',
        data.assignment_id ?? '',
        data.question_count ?? '',
        missing,
        warnings,
        updatedAt,
        data.error ?? '',
      ].join('|')
    }

    const poll = async () => {
      if (cancelled) return
      if (inFlight) return
      // If tab is hidden, don't keep polling aggressively.
      if (document.visibilityState === 'hidden') {
        scheduleNext(jitter(Math.min(MAX_DELAY_MS, delayMs)))
        return
      }

      inFlight = true
      abortInFlight()
      abortController = new AbortController()
      try {
        const res = await fetch(`${apiBase}/assignment/upload/status?job_id=${encodeURIComponent(uploadJobId)}`, {
          signal: abortController.signal,
        })
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `HTTP ${res.status}`)
        }
        const data = (await res.json()) as UploadJobStatus
        if (cancelled) return
        setUploadError('')
        setUploadJobInfo(data)
        setUploadStatus(formatUploadJobStatus(data))

        // Stop polling once parsing is finished (done/failed) or assignment is confirmed.
        if (['done', 'failed', 'confirmed'].includes(data.status)) return

        const fp = makeFingerprint(data)
        const changed = fp !== lastFingerprint
        lastFingerprint = fp

        if (changed) delayMs = BASE_DELAY_MS
        else delayMs = Math.min(MAX_DELAY_MS, Math.round(delayMs * 1.6))

        scheduleNext(jitter(delayMs))
      } catch (err: any) {
        if (cancelled) return
        if (err?.name === 'AbortError') return
        setUploadError(err.message || String(err))
        // Network/temporary errors: keep polling with backoff (up to cap).
        delayMs = Math.min(MAX_DELAY_MS, Math.round(delayMs * 1.6))
        scheduleNext(jitter(delayMs))
      } finally {
        inFlight = false
      }
    }

    const onVisibilityChange = () => {
      if (cancelled) return
      if (document.visibilityState === 'visible') {
        delayMs = BASE_DELAY_MS
        if (inFlight) return
        scheduleNext(0)
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
  }, [uploadJobId, apiBase, uploadStatusPollNonce])

  useEffect(() => {
    if (!uploadJobId) return
    const status = uploadJobInfo?.status
    if (status !== 'failed' && status !== 'confirmed') return
    try {
      const raw = localStorage.getItem('teacherActiveUpload')
      if (!raw) return
      const active = JSON.parse(raw)
      if (active?.type === 'assignment' && active?.job_id === uploadJobId) localStorage.removeItem('teacherActiveUpload')
    } catch {
      // ignore
    }
  }, [uploadJobId, uploadJobInfo?.status])

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
          throw new Error(text || `HTTP ${res.status}`)
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
    const BASE_DELAY_MS = 4000
    const MAX_DELAY_MS = 30000

    let cancelled = false
    let timeoutId: number | null = null
    let abortController: AbortController | null = null
    let inFlight = false
    let delayMs = BASE_DELAY_MS
    let lastFingerprint = ''

    const clearTimer = () => {
      if (timeoutId) window.clearTimeout(timeoutId)
      timeoutId = null
    }

    const abortInFlight = () => {
      try {
        abortController?.abort()
      } catch {
        // ignore
      }
      abortController = null
    }

    const scheduleNext = (ms: number) => {
      if (cancelled) return
      clearTimer()
      timeoutId = window.setTimeout(() => void poll(), ms)
    }

    const jitter = (ms: number) => {
      const factor = 0.8 + Math.random() * 0.4
      return Math.round(ms * factor)
    }

    const makeFingerprint = (data: ExamUploadJobStatus) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const extra = data as any
      const updatedAt = extra?.updated_at || extra?.updatedAt || ''
      const counts = data.counts ? JSON.stringify(data.counts) : ''
      const warnings = Array.isArray(data.warnings) ? data.warnings.length : 0
      return [data.status, data.progress ?? '', data.step ?? '', data.exam_id ?? '', counts, warnings, updatedAt, data.error ?? ''].join('|')
    }

    const poll = async () => {
      if (cancelled) return
      if (inFlight) return
      if (document.visibilityState === 'hidden') {
        scheduleNext(jitter(Math.min(MAX_DELAY_MS, Math.max(delayMs, 12000))))
        return
      }
      inFlight = true
      abortInFlight()
      abortController = new AbortController()
      try {
        const res = await fetch(`${apiBase}/exam/upload/status?job_id=${encodeURIComponent(examJobId)}`, {
          signal: abortController.signal,
          headers: { Accept: 'application/json' },
        })
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `HTTP ${res.status}`)
        }
        const data = (await res.json()) as ExamUploadJobStatus
        if (cancelled) return
        setExamJobInfo(data)
        setExamUploadStatus(formatExamJobStatus(data))
        if (data.status === 'failed') {
          setExamUploadError(formatExamJobStatus(data))
          try {
            const raw = localStorage.getItem('teacherActiveUpload')
            if (raw) {
              const active = JSON.parse(raw)
              if (active?.type === 'exam' && active?.job_id === examJobId) localStorage.removeItem('teacherActiveUpload')
            }
          } catch {
            // ignore
          }
        }
        if (data.status === 'confirmed') {
          try {
            const raw = localStorage.getItem('teacherActiveUpload')
            if (raw) {
              const active = JSON.parse(raw)
              if (active?.type === 'exam' && active?.job_id === examJobId) localStorage.removeItem('teacherActiveUpload')
            }
          } catch {
            // ignore
          }
        }

        const fingerprint = makeFingerprint(data)
        if (fingerprint !== lastFingerprint) {
          lastFingerprint = fingerprint
          delayMs = BASE_DELAY_MS
        } else {
          delayMs = Math.min(MAX_DELAY_MS, Math.round(delayMs * 1.25))
        }

        if (data.status === 'done' || data.status === 'failed' || data.status === 'confirmed') {
          scheduleNext(jitter(Math.min(MAX_DELAY_MS, Math.max(delayMs, 9000))))
        } else {
          scheduleNext(jitter(delayMs))
        }
      } catch (err: any) {
        if (cancelled) return
        if (err?.name === 'AbortError') return
        setExamUploadError(err.message || String(err))
        delayMs = Math.min(MAX_DELAY_MS, Math.round(delayMs * 1.6))
        scheduleNext(jitter(delayMs))
      } finally {
        inFlight = false
      }
    }

    const onVisibilityChange = () => {
      if (cancelled) return
      if (document.visibilityState === 'visible') {
        delayMs = BASE_DELAY_MS
        if (inFlight) return
        scheduleNext(0)
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
  }, [examJobId, apiBase, examStatusPollNonce])

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
          throw new Error(text || `HTTP ${res.status}`)
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

  const parseCommaList = (text: string) =>
    text
      .split(/[，,]/g)
      .map((s) => s.trim())
      .filter(Boolean)

  const parseLineList = (text: string) =>
    text
      .split(/\n/g)
      .map((s) => s.trim())
      .filter(Boolean)

  // Avoid any accidental key handlers interfering with draft editing.
  const stopKeyPropagation = (e: KeyboardEvent<HTMLElement>) => {
    e.stopPropagation()
  }

  const difficultyOptions = [
    { value: 'basic', label: '基础' },
    { value: 'medium', label: '中等' },
    { value: 'advanced', label: '较难' },
    { value: 'challenge', label: '压轴' },
  ] as const

  const normalizeDifficulty = (value: any) => {
    const raw = String(value || '').trim()
    if (!raw) return 'basic'
    const v = raw.toLowerCase()
    const mapping: Record<string, string> = {
      basic: 'basic',
      medium: 'medium',
      advanced: 'advanced',
      challenge: 'challenge',
      easy: 'basic',
      intermediate: 'medium',
      hard: 'advanced',
      expert: 'challenge',
      'very hard': 'challenge',
      'very_hard': 'challenge',
      入门: 'basic',
      简单: 'basic',
      基础: 'basic',
      中等: 'medium',
      一般: 'medium',
      提高: 'medium',
      较难: 'advanced',
      困难: 'advanced',
      拔高: 'advanced',
      压轴: 'challenge',
      挑战: 'challenge',
    }
    if (mapping[v]) return mapping[v]
    for (const [k, norm] of Object.entries(mapping)) {
      if (k && raw.includes(k)) return norm
    }
    return 'basic'
  }

  const difficultyLabel = (value: any) => {
    const norm = normalizeDifficulty(value)
    const found = difficultyOptions.find((opt) => opt.value === norm)
    return found ? found.label : '基础'
  }

  const requirementLabels: Record<string, string> = {
    subject: '学科',
    topic: '主题',
    grade_level: '年级',
    class_level: '班级水平',
    core_concepts: '核心概念',
    typical_problem: '典型题型/例题',
    misconceptions: '易错点/易混点',
    duration_minutes: '作业时间',
    preferences: '作业偏好',
    extra_constraints: '额外限制',
  }

  const formatMissingRequirements = (missing?: string[]) => {
    const items = Array.isArray(missing) ? missing : []
    return items.map((key) => requirementLabels[key] || key).join('、')
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
      setUploadError('请填写作业ID')
      return
    }
    if (!uploadFiles.length) {
      setUploadError('请至少上传一份作业文件（PDF 或图片）')
      return
    }
    if (uploadScope === 'student' && !uploadStudentIds.trim()) {
      setUploadError('私人作业请填写学生ID')
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
        let message = text || `HTTP ${res.status}`
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
            localStorage.setItem('teacherActiveUpload', JSON.stringify({ type: 'assignment', job_id: jid }))
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
      setExamUploadError('请至少上传一份试卷文件（PDF 或图片）')
      return
    }
    if (!examScoreFiles.length) {
      setExamUploadError('请至少上传一份成绩文件（xls/xlsx 或 PDF/图片）')
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

      const res = await fetch(`${apiBase}/exam/upload/start`, { method: 'POST', body: fd })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `HTTP ${res.status}`)
      }
      const data = await res.json()
      if (data && typeof data === 'object') {
        if (data.job_id) {
          const jid = String(data.job_id)
          setExamJobId(jid)
          try {
            localStorage.setItem('teacherActiveUpload', JSON.stringify({ type: 'exam', job_id: jid }))
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
        let message = text || `HTTP ${res.status}`
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

  const handleConfirmUpload = async () => {
    if (!uploadJobId) return
    setUploadError('')
    setDraftActionError('')
    setDraftActionStatus('正在创建作业…')
    setUploadConfirming(true)
    try {
      // If parsing is still running, don't attempt to confirm. Force a status refresh and keep polling.
      if (uploadJobInfo && uploadJobInfo.status !== 'done' && uploadJobInfo.status !== 'confirmed') {
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
              status: prev.status === 'confirmed' ? 'confirmed' : ('confirming' as any),
              step: 'confirming',
              progress: prev.progress ?? 0,
            }
          : prev
      )
      // Ensure latest edits are saved before confirm
      if (uploadDraft) {
        await saveDraft(uploadDraft)
      }
      const res = await fetch(`${apiBase}/assignment/upload/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: uploadJobId, strict_requirements: true }),
      })
      if (!res.ok) {
        const text = await res.text()
        let message = text || `HTTP ${res.status}`
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
        if (data.assignment_id) lines.push(`作业ID：${data.assignment_id}`)
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
        setUploadJobInfo((prev) => (prev ? { ...prev, status: 'confirmed' } : prev))
        setDraftPanelCollapsed(true)
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
        }),
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `HTTP ${res.status}`)
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
              status: prev.status === 'confirmed' ? 'confirmed' : ('confirming' as any),
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
        let message = text || `HTTP ${res.status}`
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
        if (data.exam_id) lines.push(`考试ID：${data.exam_id}`)
        const msg = lines.join('\n')
        setExamDraftActionStatus(msg)
        setExamUploadStatus(msg)
        setExamJobInfo((prev) => (prev ? { ...prev, status: 'confirmed' } : prev))
        setExamDraftPanelCollapsed(true)
        try {
          const raw = localStorage.getItem('teacherActiveUpload')
          if (raw) {
            const active = JSON.parse(raw)
            if (active?.type === 'exam' && active?.job_id === examJobId) localStorage.removeItem('teacherActiveUpload')
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

	          <section className={`upload-card ${uploadCardCollapsed ? 'collapsed' : ''}`}>
	            <div className="panel-header">
	              <div className="panel-title">
	                <h3>{uploadMode === 'assignment' ? '上传作业文件（PDF / 图片）' : '上传考试文件（试卷 + 成绩表）'}</h3>
	                <div className="segmented">
	                  <button
	                    type="button"
	                    className={uploadMode === 'assignment' ? 'active' : ''}
	                    onClick={() => setUploadMode('assignment')}
	                  >
	                    作业
	                  </button>
	                  <button type="button" className={uploadMode === 'exam' ? 'active' : ''} onClick={() => setUploadMode('exam')}>
	                    考试
	                  </button>
	                </div>
	              </div>
	              {uploadCardCollapsed ? (
	                <div
	                  className="panel-summary"
	                  title={
	                    uploadMode === 'assignment'
	                      ? formatUploadJobSummary(uploadJobInfo, uploadAssignmentId.trim())
	                      : formatExamJobSummary(examJobInfo, examId.trim())
	                  }
	                >
	                  {uploadMode === 'assignment'
	                    ? formatUploadJobSummary(uploadJobInfo, uploadAssignmentId.trim())
	                    : formatExamJobSummary(examJobInfo, examId.trim())}
	                </div>
	              ) : null}
	              <button type="button" className="ghost" onClick={() => setUploadCardCollapsed((v) => !v)}>
	                {uploadCardCollapsed ? '展开' : '收起'}
	              </button>
	            </div>
	            {uploadCardCollapsed ? null : (
	              <>
	                {uploadMode === 'assignment' ? (
	                  <>
	                    <p>上传后将在后台解析题目与答案，并生成作业 8 点描述。解析完成后需确认创建作业。</p>
	                    <form className="upload-form" onSubmit={handleUploadAssignment}>
	                      <div className="upload-grid">
	                        <div className="upload-field">
	                          <label>作业ID</label>
	                          <input
	                            value={uploadAssignmentId}
	                            onChange={(e) => setUploadAssignmentId(e.target.value)}
	                            placeholder="例如：HW-2026-02-05"
	                          />
	                        </div>
	                        <div className="upload-field">
	                          <label>日期（可选）</label>
	                          <input value={uploadDate} onChange={(e) => setUploadDate(e.target.value)} placeholder="YYYY-MM-DD" />
	                        </div>
	                        <div className="upload-field">
	                          <label>范围</label>
	                          <select value={uploadScope} onChange={(e) => setUploadScope(e.target.value as any)}>
	                            <option value="public">公共作业</option>
	                            <option value="class">班级作业</option>
	                            <option value="student">私人作业</option>
	                          </select>
	                        </div>
	                        <div className="upload-field">
	                          <label>班级（班级作业必填）</label>
	                          <input
	                            value={uploadClassName}
	                            onChange={(e) => setUploadClassName(e.target.value)}
	                            placeholder="例如：高二2403班"
	                          />
	                        </div>
	                        <div className="upload-field">
	                          <label>学生ID（私人作业必填）</label>
	                          <input
	                            value={uploadStudentIds}
	                            onChange={(e) => setUploadStudentIds(e.target.value)}
	                            placeholder="例如：高二2403班_刘昊然"
	                          />
	                        </div>
	                        <div className="upload-field">
	                          <label>作业文件（PDF/图片）</label>
	                          <input
	                            type="file"
	                            multiple
	                            accept="application/pdf,image/*"
	                            onChange={(e) => setUploadFiles(Array.from(e.target.files || []))}
	                          />
	                        </div>
	                        <div className="upload-field">
	                          <label>答案文件（可选）</label>
	                          <input
	                            type="file"
	                            multiple
	                            accept="application/pdf,image/*"
	                            onChange={(e) => setUploadAnswerFiles(Array.from(e.target.files || []))}
	                          />
	                        </div>
	                      </div>
	                      <button type="submit" disabled={uploading}>
	                        {uploading ? '上传中…' : '上传并开始解析'}
	                      </button>
	                    </form>
	                    {uploadError && <div className="status err">{uploadError}</div>}
	                    {uploadStatus && <pre className="status ok">{uploadStatus}</pre>}
	                  </>
	                ) : (
	                  <>
	                    <p>上传考试试卷与成绩表后，系统将生成考试数据与分析草稿。成绩表推荐 xlsx（最稳）。</p>
	                    <form className="upload-form" onSubmit={handleUploadExam}>
	                      <div className="upload-grid">
	                        <div className="upload-field">
	                          <label>考试ID（可选）</label>
	                          <input value={examId} onChange={(e) => setExamId(e.target.value)} placeholder="例如：EX2403_PHY" />
	                        </div>
	                        <div className="upload-field">
	                          <label>日期（可选）</label>
	                          <input value={examDate} onChange={(e) => setExamDate(e.target.value)} placeholder="YYYY-MM-DD" />
	                        </div>
	                        <div className="upload-field">
	                          <label>班级（可选）</label>
	                          <input
	                            value={examClassName}
	                            onChange={(e) => setExamClassName(e.target.value)}
	                            placeholder="例如：高二2403班"
	                          />
	                        </div>
	                        <div className="upload-field">
	                          <label>试卷文件（必填）</label>
	                          <input
	                            type="file"
	                            multiple
	                            accept="application/pdf,image/*"
	                            onChange={(e) => setExamPaperFiles(Array.from(e.target.files || []))}
	                          />
	                        </div>
	                        <div className="upload-field">
	                          <label>成绩文件（必填）</label>
	                          <input
	                            type="file"
	                            multiple
	                            accept="application/pdf,image/*,.xls,.xlsx"
	                            onChange={(e) => setExamScoreFiles(Array.from(e.target.files || []))}
	                          />
	                        </div>
	                      </div>
	                      <button type="submit" disabled={examUploading}>
	                        {examUploading ? '上传中…' : '上传并开始解析'}
	                      </button>
	                    </form>
	                    {examUploadError && <div className="status err">{examUploadError}</div>}
	                    {examUploadStatus && <pre className="status ok">{examUploadStatus}</pre>}
	                  </>
	                )}
	              </>
	            )}
	          </section>

	          {uploadMode === 'exam' && examDraftLoading && (
	            <section className="draft-panel">
	              <h3>考试解析结果（审核/修改）</h3>
	              <div className="status ok">草稿加载中…</div>
	            </section>
	          )}

	          {uploadMode === 'exam' && examDraftError && (
	            <section className="draft-panel">
	              <h3>考试解析结果（审核/修改）</h3>
	              <div className="status err">{examDraftError}</div>
	            </section>
	          )}

	          {uploadMode === 'exam' && examDraft && (
	            <section className={`draft-panel ${examDraftPanelCollapsed ? 'collapsed' : ''}`}>
	              <div className="panel-header">
	                <h3>考试解析结果（审核/修改）</h3>
	                {examDraftPanelCollapsed ? (
	                  <div className="panel-summary" title={formatExamDraftSummary(examDraft, examJobInfo)}>
	                    {formatExamDraftSummary(examDraft, examJobInfo)}
	                  </div>
	                ) : null}
	                <button type="button" className="ghost" onClick={() => setExamDraftPanelCollapsed((v) => !v)}>
	                  {examDraftPanelCollapsed ? '展开' : '收起'}
	                </button>
	              </div>
	              {examDraftPanelCollapsed ? null : (
	                <>
	                  <div className="draft-meta">
	                    <div>考试ID：{examDraft.exam_id}</div>
	                    <div>日期：{String(examDraft.meta?.date || examDraft.date || '') || '（未设置）'}</div>
	                    {examDraft.meta?.class_name ? <div>班级：{String(examDraft.meta.class_name)}</div> : null}
	                    {examDraft.counts?.students !== undefined ? <div>学生数：{examDraft.counts.students}</div> : null}
	                    {examDraft.counts?.questions !== undefined ? <div>题目数：{examDraft.counts.questions}</div> : null}
	                    {examDraft.totals_summary?.avg_total !== undefined ? <div>平均分：{examDraft.totals_summary.avg_total}</div> : null}
	                    {examDraft.totals_summary?.median_total !== undefined ? <div>中位数：{examDraft.totals_summary.median_total}</div> : null}
	                    {examDraft.totals_summary?.max_total_observed !== undefined ? (
	                      <div>最高分(观测)：{examDraft.totals_summary.max_total_observed}</div>
	                    ) : null}
	                  </div>

	                  {examDraftActionError && <div className="status err">{examDraftActionError}</div>}
	                  {examDraftActionStatus && <pre className="status ok">{examDraftActionStatus}</pre>}

	                  <div className="draft-actions">
	                    <button
	                      type="button"
	                      className="secondary-btn"
	                      onClick={() => {
	                        if (!examDraft) return
	                        void saveExamDraft(examDraft).catch(() => {})
	                      }}
	                      disabled={examDraftSaving}
	                    >
	                      {examDraftSaving ? '保存中…' : '保存草稿'}
	                    </button>
	                    <button
	                      type="button"
	                      onClick={handleConfirmExamUpload}
	                      disabled={examConfirming || examDraftSaving || !examJobInfo || examJobInfo.status !== 'done'}
	                      title={examJobInfo && examJobInfo.status !== 'done' ? '解析未完成，暂不可创建' : ''}
	                    >
	                      {examConfirming
	                        ? examJobInfo && (examJobInfo.status as any) === 'confirming'
	                          ? `创建中…${examJobInfo.progress ?? 0}%`
	                          : '创建中…'
	                        : examJobInfo && examJobInfo.status === 'confirmed'
	                          ? '已创建'
	                          : '创建考试'}
	                    </button>
	                  </div>

	                  <div className="draft-grid">
	                    <div className="draft-card">
	                      <h4>考试信息（可编辑）</h4>
	                      <div className="draft-form">
	                        <label>日期（YYYY-MM-DD）</label>
	                        <input
	                          value={String(examDraft.meta?.date || '')}
	                          onChange={(e) => updateExamDraftMeta('date', e.target.value)}
	                        />
	                        <label>班级</label>
	                        <input
	                          value={String(examDraft.meta?.class_name || '')}
	                          onChange={(e) => updateExamDraftMeta('class_name', e.target.value)}
	                        />
	                      </div>
	                    </div>
	                    <div className="draft-card">
	                      <h4>题目满分（可编辑）</h4>
	                      <div className="exam-question-list">
	                        {(examDraft.questions || []).map((q, idx) => (
	                          <div className="exam-question-row" key={`${q.question_id || 'q'}-${idx}`}>
	                            <div className="exam-question-id">{q.question_id || `Q${idx + 1}`}</div>
	                            <div className="exam-question-no">{q.question_no ? `题号 ${q.question_no}` : ''}</div>
	                            <input
	                              type="number"
	                              min={0}
	                              step={0.5}
	                              value={q.max_score ?? ''}
	                              onChange={(e) => {
	                                const raw = e.target.value
	                                const nextVal = raw === '' ? null : Number(raw)
	                                updateExamQuestionField(idx, { max_score: nextVal })
	                              }}
	                            />
	                          </div>
	                        ))}
	                      </div>
	                    </div>
	                  </div>
	                </>
	              )}
	            </section>
	          )}

          {uploadMode === 'assignment' && draftLoading && (
            <section className="draft-panel">
              <h3>解析结果（审核/修改）</h3>
              <div className="status ok">草稿加载中…</div>
            </section>
          )}

          {uploadMode === 'assignment' && draftError && (
            <section className="draft-panel">
              <h3>解析结果（审核/修改）</h3>
              <div className="status err">{draftError}</div>
            </section>
          )}

          {uploadMode === 'assignment' && uploadDraft && (
            <section className={`draft-panel ${draftPanelCollapsed ? 'collapsed' : ''}`}>
              <div className="panel-header">
                <h3>解析结果（审核/修改）</h3>
                {draftPanelCollapsed ? (
                  <div className="panel-summary" title={formatDraftSummary(uploadDraft, uploadJobInfo)}>
                    {formatDraftSummary(uploadDraft, uploadJobInfo)}
                  </div>
                ) : null}
                <button type="button" className="ghost" onClick={() => setDraftPanelCollapsed((v) => !v)}>
                  {draftPanelCollapsed ? '展开' : '收起'}
                </button>
              </div>
              {draftPanelCollapsed ? (
                <></>
              ) : (
                <>
                  <div className="draft-meta">
                    <div>作业ID：{uploadDraft.assignment_id}</div>
                    <div>日期：{uploadDraft.date}</div>
                    <div>
                      范围：
                      {uploadDraft.scope === 'public'
                        ? '公共作业'
                        : uploadDraft.scope === 'class'
                          ? '班级作业'
                          : '私人作业'}
                    </div>
                    {uploadDraft.class_name ? <div>班级：{uploadDraft.class_name}</div> : null}
                    {uploadDraft.student_ids && uploadDraft.student_ids.length ? (
                      <div>学生：{uploadDraft.student_ids.join('、')}</div>
                    ) : null}
                    <div>题目数量：{uploadDraft.questions?.length || 0}</div>
                    <div>交付方式：{uploadDraft.delivery_mode === 'pdf' ? 'PDF' : '图片'}</div>
                    {uploadDraft.requirements_missing && uploadDraft.requirements_missing.length ? (
                      <div className="missing">
                        缺失项：{formatMissingRequirements(uploadDraft.requirements_missing)}（补全后才能创建）
                      </div>
                    ) : (
                      <div className="ok">作业要求已补全，可创建。</div>
                    )}
                  </div>

                  {draftActionError && <div className="status err">{draftActionError}</div>}
                  {draftActionStatus && <pre className="status ok">{draftActionStatus}</pre>}

                  <div className="draft-actions">
                    <button
                      type="button"
                      className="secondary-btn"
                      onClick={() => {
                        if (!uploadDraft) return
                        void saveDraft(uploadDraft).catch(() => {})
                      }}
                      disabled={draftSaving}
                    >
                      {draftSaving ? '保存中…' : '保存草稿'}
                    </button>
                    <button
                      type="button"
                      className="confirm-btn"
                      onClick={handleConfirmUpload}
                      disabled={
                        uploadConfirming ||
                        (uploadJobInfo ? uploadJobInfo.status !== 'done' : false) ||
                        ((uploadDraft.requirements_missing?.length || 0) > 0)
                      }
                      title={
                        uploadJobInfo && uploadJobInfo.status !== 'done'
                          ? uploadJobInfo.status === 'confirmed'
                            ? '作业已创建，无需重复创建'
                            : '解析未完成，暂不可创建'
                          : uploadDraft.requirements_missing && uploadDraft.requirements_missing.length
                            ? `请先补全：${formatMissingRequirements(uploadDraft.requirements_missing)}`
                            : ''
                      }
                    >
                      {uploadConfirming
                        ? uploadJobInfo && (uploadJobInfo.status as any) === 'confirming'
                          ? `创建中…${uploadJobInfo.progress ?? 0}%`
                          : '创建中…'
                        : uploadJobInfo && uploadJobInfo.status === 'confirmed'
                          ? '已创建'
                          : '创建作业'}
                    </button>
                  </div>

                  <div className="draft-grid">
                <div className="draft-card">
                  <h4>作业 8 点要求（可编辑）</h4>
                  <div className="draft-form">
                    <label>1) 学科</label>
                    <input value={uploadDraft.requirements?.subject || ''} onChange={(e) => updateDraftRequirement('subject', e.target.value)} />
                    <label>1) 本节课主题</label>
                    <input value={uploadDraft.requirements?.topic || ''} onChange={(e) => updateDraftRequirement('topic', e.target.value)} />
                    <label>2) 年级</label>
                    <input value={uploadDraft.requirements?.grade_level || ''} onChange={(e) => updateDraftRequirement('grade_level', e.target.value)} />
                    <label>2) 班级水平（偏弱/中等/较强/混合）</label>
                    <select
                      value={uploadDraft.requirements?.class_level || ''}
                      onChange={(e) => updateDraftRequirement('class_level', e.target.value)}
                      onKeyDown={stopKeyPropagation}
                    >
                      <option value="">未设置</option>
                      <option value="偏弱">偏弱</option>
                      <option value="中等">中等</option>
                      <option value="较强">较强</option>
                      <option value="混合">混合</option>
                    </select>
                    <label>3) 核心概念（逗号分隔 3–8 个）</label>
                    <input
                      value={(uploadDraft.requirements?.core_concepts || []).join('，')}
                      onChange={(e) => updateDraftRequirement('core_concepts', parseCommaList(e.target.value))}
                    />
                    <label>4) 典型题型/例题特征</label>
                    <textarea
                      value={uploadDraft.requirements?.typical_problem || ''}
                      onChange={(e) => updateDraftRequirement('typical_problem', e.target.value)}
                      onKeyDown={stopKeyPropagation}
                      rows={3}
                    />
                    <label>5) 易错点（每行一条，至少 4 条）</label>
                    <textarea
                      value={misconceptionsText}
                      onChange={(e) => {
                        setMisconceptionsText(e.target.value)
                        setMisconceptionsDirty(true)
                        // Also keep structured requirements up to date for any immediate UI reads.
                        updateDraftRequirement('misconceptions', parseLineList(e.target.value))
                      }}
                      onKeyDown={stopKeyPropagation}
                      placeholder={'示例：\n1) 调零本质理解错误\n2) 换挡不重新调零\n3) 读数方向/单位混淆\n4) 内阻影响忽略'}
                      rows={4}
                    />
                    <label>6) 作业时间（20/40/60）</label>
                    <select
                      value={String(uploadDraft.requirements?.duration_minutes || '')}
                      onChange={(e) => updateDraftRequirement('duration_minutes', Number(e.target.value))}
                    >
                      <option value="">未设置</option>
                      <option value="20">20</option>
                      <option value="40">40</option>
                      <option value="60">60</option>
                    </select>
                    <label>7) 作业偏好（逗号分隔）</label>
                    <input
                      value={(uploadDraft.requirements?.preferences || []).join('，')}
                      onChange={(e) => updateDraftRequirement('preferences', parseCommaList(e.target.value))}
                      placeholder="例如：B提升，E小测验"
                    />
                    <label>8) 额外限制</label>
                    <textarea
                      value={uploadDraft.requirements?.extra_constraints || ''}
                      onChange={(e) => updateDraftRequirement('extra_constraints', e.target.value)}
                      onKeyDown={stopKeyPropagation}
                      rows={2}
                    />
                  </div>
                </div>

                <div className="draft-card">
                  <h4>题目与答案（可编辑）</h4>
                  <div className="draft-hint">题目较多时可先修改关键题，点击“保存草稿”后再创建。</div>
                  {(uploadDraft.questions || []).slice(0, questionShowCount).map((q, idx) => (
                    <details key={idx} className="question-item" open={idx < 1}>
                      <summary>
                        Q{idx + 1} · {(q.kp || q.kp_id || '未分类') as any} · {difficultyLabel(q.difficulty)}
                      </summary>
                      <div className="question-fields">
                        <label>题干</label>
                        <textarea
                          value={q.stem || ''}
                          onChange={(e) => updateDraftQuestion(idx, { stem: e.target.value })}
                          onKeyDown={stopKeyPropagation}
                          rows={4}
                        />
                        <label>答案</label>
                        <textarea
                          value={q.answer || ''}
                          onChange={(e) => updateDraftQuestion(idx, { answer: e.target.value })}
                          onKeyDown={stopKeyPropagation}
                          rows={3}
                        />
                        <div className="row2">
                          <div>
                            <label>分值</label>
                            <input
                              value={q.score ?? ''}
                              onChange={(e) => updateDraftQuestion(idx, { score: Number(e.target.value) || 0 })}
                              placeholder="0"
                            />
                          </div>
                          <div>
                            <label>难度</label>
                            <select
                              value={normalizeDifficulty(q.difficulty)}
                              onChange={(e) => updateDraftQuestion(idx, { difficulty: e.target.value })}
                            >
                              {difficultyOptions.map((opt) => (
                                <option key={opt.value} value={opt.value}>
                                  {opt.label}
                                </option>
                              ))}
                            </select>
                          </div>
                        </div>
                        <div className="row2">
                          <div>
                            <label>知识点（kp）</label>
                            <input value={q.kp || ''} onChange={(e) => updateDraftQuestion(idx, { kp: e.target.value })} />
                          </div>
                          <div>
                            <label>标签（逗号分隔）</label>
                            <input
                              value={Array.isArray(q.tags) ? q.tags.join('，') : q.tags || ''}
                              onChange={(e) => updateDraftQuestion(idx, { tags: parseCommaList(e.target.value) })}
                            />
                          </div>
                        </div>
                        <label>题型（可选）</label>
                        <input value={q.type || ''} onChange={(e) => updateDraftQuestion(idx, { type: e.target.value })} />
                      </div>
                    </details>
                  ))}
                  {uploadDraft.questions && uploadDraft.questions.length > questionShowCount && (
                    <div className="draft-actions">
                      <button type="button" className="secondary-btn" onClick={() => setQuestionShowCount((n) => n + 20)}>
                        加载更多（+20）
                      </button>
                    </div>
                  )}
                </div>
                  </div>
                </>
              )}
            </section>
          )}

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
