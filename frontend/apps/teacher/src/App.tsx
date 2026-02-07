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
import RoutingPage from './features/routing/RoutingPage'
import {
  buildInvocationToken,
  findInvocationTrigger,
  parseInvocationInput,
  type InvocationTriggerType,
} from './features/chat/invocation'
import { decideSkillRouting } from './features/chat/requestRouting'
import { useChatScroll } from './features/chat/useChatScroll'
import ChatComposer from './features/chat/ChatComposer'
import ChatMessages from './features/chat/ChatMessages'
import MentionPanel from './features/chat/MentionPanel'
import SessionSidebar from './features/chat/SessionSidebar'
import 'katex/dist/katex.min.css'

const DEFAULT_API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const TEACHER_SESSION_VIEW_STATE_KEY = 'teacherSessionViewState'
const TEACHER_LOCAL_DRAFT_SESSIONS_KEY = 'teacherLocalDraftSessionIds'

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
  lane_id?: string
  lane_queue_position?: number
  lane_queue_size?: number
  lane_active?: boolean
}

type ChatStartResult = {
  ok: boolean
  job_id: string
  status: string
  lane_id?: string
  lane_queue_position?: number
  lane_queue_size?: number
  lane_active?: boolean
  debounced?: boolean
}

type PendingChatJob = {
  job_id: string
  request_id: string
  placeholder_id: string
  user_text: string
  session_id: string
  lane_id?: string
  created_at: number
}

type TeacherHistorySession = {
  session_id: string
  updated_at?: string
  preview?: string
  message_count?: number
  compaction_runs?: number
}

type SessionGroup<T> = {
  key: string
  label: string
  items: T[]
}

type TeacherHistorySessionsResponse = {
  ok: boolean
  teacher_id: string
  sessions: TeacherHistorySession[]
  next_cursor?: number | null
  total?: number
}

type SessionViewStatePayload = {
  title_map: Record<string, string>
  hidden_ids: string[]
  active_session_id: string
  updated_at: string
}

type TeacherHistoryMessage = {
  ts?: string
  role?: string
  content?: string
  kind?: string
}

type TeacherHistorySessionResponse = {
  ok: boolean
  teacher_id: string
  session_id: string
  messages: TeacherHistoryMessage[]
  next_cursor: number
}

type TeacherMemoryProposal = {
  proposal_id: string
  teacher_id?: string
  target?: string
  title?: string
  content?: string
  source?: string
  status?: string
  created_at?: string
  applied_at?: string
  rejected_at?: string
  reject_reason?: string
  supersedes?: string[]
  superseded_by?: string
}

type TeacherMemoryProposalListResponse = {
  ok: boolean
  teacher_id: string
  proposals: TeacherMemoryProposal[]
}

type TeacherMemoryInsightsResponse = {
  ok: boolean
  teacher_id: string
  window_days: number
  summary?: {
    applied_total?: number
    rejected_total?: number
    active_total?: number
    expired_total?: number
    superseded_total?: number
    avg_priority_active?: number
    by_source?: Record<string, number>
    by_target?: Record<string, number>
    rejected_reasons?: Record<string, number>
  }
  retrieval?: {
    search_calls?: number
    search_hit_calls?: number
    search_hit_rate?: number
    search_mode_breakdown?: Record<string, number>
    context_injected?: number
  }
  top_queries?: Array<{
    query: string
    calls: number
    hit_calls: number
    hit_rate: number
  }>
}

type UploadJobStatus = {
  job_id: string
  status: 'queued' | 'processing' | 'done' | 'failed' | 'confirmed' | 'confirming' | 'cancelled'
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
  due_at?: string
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

type AssignmentProgressStudent = {
  student_id: string
  student_name?: string
  class_name?: string
  complete?: boolean
  overdue?: boolean
  discussion?: { status?: string; pass?: boolean; message_count?: number; last_ts?: string }
  submission?: { attempts?: number; best?: any }
}

type AssignmentProgress = {
  ok: boolean
  assignment_id: string
  date?: string
  scope?: string
  class_name?: string
  due_at?: string
  expected_count?: number
  counts?: { expected?: number; discussion_pass?: number; submitted?: number; completed?: number; overdue?: number }
  students?: AssignmentProgressStudent[]
  updated_at?: string
}

type ExamUploadJobStatus = {
  job_id: string
  status: 'queued' | 'processing' | 'done' | 'failed' | 'confirmed' | 'confirming' | 'cancelled'
  progress?: number
  step?: string
  error?: string
  error_detail?: string
  exam_id?: string
  counts?: { students?: number; responses?: number; questions?: number }
  counts_scored?: { students?: number; responses?: number }
  totals_summary?: Record<string, any>
  scoring?: {
    status?: string
    responses_total?: number
    responses_scored?: number
    students_total?: number
    students_scored?: number
    default_max_score_qids?: string[]
  }
  answer_key?: { count?: number; source?: string; warnings?: string[] }
  warnings?: string[]
}

type ExamUploadDraft = {
  job_id: string
  exam_id: string
  date?: string
  class_name?: string
  paper_files?: string[]
  score_files?: string[]
  answer_files?: string[]
  counts?: Record<string, any>
  counts_scored?: Record<string, any>
  totals_summary?: Record<string, any>
  scoring?: Record<string, any>
  meta: Record<string, any>
  questions: Array<Record<string, any>>
  score_schema?: Record<string, any>
  answer_key?: Record<string, any>
  answer_key_text?: string
  answer_text_excerpt?: string
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

type AgentOption = {
  id: string
  title: string
  desc: string
}

type MentionOption = {
  id: string
  title: string
  desc: string
  type: InvocationTriggerType
}

type SkillResponse = {
  skills: Array<{
    id: string
    title?: string
    desc?: string
    prompts?: string[]
    examples?: string[]
    allowed_roles?: string[]
  }>
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

const fallbackSkills: Skill[] = [
  {
    id: 'physics-teacher-ops',
    title: '教师运营',
    desc: '考试分析、课前检测、教学备课与课堂讨论。',
    prompts: ['列出所有考试，并给出最新考试概览。'],
    examples: ['列出考试', '生成课前检测清单', '做一次考试分析'],
  },
  {
    id: 'physics-homework-generator',
    title: '作业生成',
    desc: '基于课堂讨论生成课后诊断与作业。',
    prompts: ['生成作业 A2403_2026-02-04，知识点 KP-M01,KP-E04，每个 5 题。'],
    examples: ['生成作业 A2403_2026-02-04', '渲染作业文档'],
  },
  {
    id: 'physics-lesson-capture',
    title: '课堂采集',
    desc: '课堂材料文字识别并抽取例题与讨论结构。',
    prompts: ['采集课堂材料 L2403_2026-02-04，主题“静电场综合”。'],
    examples: ['采集课堂材料 L2403_2026-02-04', '列出课程'],
  },
  {
    id: 'physics-student-coach',
    title: '学生教练',
    desc: '学生侧讨论、作业批改与画像更新。',
    prompts: ['查看学生画像 高二2403班_武熙语。'],
    examples: ['查看学生画像 武熙语', '开始今天作业'],
  },
  {
    id: 'physics-student-focus',
    title: '学生重点分析',
    desc: '针对某个学生进行重点诊断与画像更新。',
    prompts: ['请分析学生 高二2403班_武熙语 的最近作业表现。'],
    examples: ['分析学生 高二2403班_武熙语'],
  },
  {
    id: 'physics-core-examples',
    title: '核心例题库',
    desc: '登记核心例题、标准解法与变式题。',
    prompts: ['登记核心例题 CE001，知识点 KP-M01。'],
    examples: ['登记核心例题 CE001', '生成变式题 3 道'],
  },
  {
    id: 'physics-llm-routing',
    title: '模型路由管理',
    desc: '按任务类型配置模型路由，支持仿真与回滚。',
    prompts: ['先读取当前路由配置，再给我一个三类任务分流方案。'],
    examples: ['查看当前模型路由', '仿真 physics-homework-generator 的 chat.agent', '回滚到路由版本 3'],
  },
]

const fallbackAgents: AgentOption[] = [
  {
    id: 'default',
    title: '默认 Agent',
    desc: '按系统路由自动选择执行链路。',
  },
  {
    id: 'opencode',
    title: 'OpenCode Agent',
    desc: '优先按 opencode 路由执行（需后端已配置）。',
  },
]

const TEACHER_GREETING =
  '老师端已就绪。你可以直接提需求，例如：\n- 列出考试\n- 导入学生名册\n- 生成作业\n\n召唤规则：`@agent` 选择执行代理，`$skill` 选择技能。'

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
    updated_at: state.updated_at || '',
  }
  return JSON.stringify(normalized)
}

const readTeacherLocalViewState = (): SessionViewStatePayload => {
  try {
    const raw = localStorage.getItem(TEACHER_SESSION_VIEW_STATE_KEY)
    if (raw) {
      const parsed = normalizeSessionViewStatePayload(JSON.parse(raw))
      if (!parsed.active_session_id) {
        parsed.active_session_id = String(localStorage.getItem('teacherActiveSessionId') || '').trim()
      }
      if (parsed.updated_at) return parsed
    }
  } catch {
    // ignore
  }
  let titleMap: Record<string, string> = {}
  let hiddenIds: string[] = []
  const activeSessionId = String(localStorage.getItem('teacherActiveSessionId') || '').trim()
  try {
    const parsed = JSON.parse(localStorage.getItem('teacherSessionTitles') || '{}')
    if (parsed && typeof parsed === 'object') titleMap = parsed
  } catch {
    titleMap = {}
  }
  try {
    const parsed = JSON.parse(localStorage.getItem('teacherDeletedSessions') || '[]')
    if (Array.isArray(parsed)) hiddenIds = parsed.map((item) => String(item || '').trim()).filter(Boolean)
  } catch {
    hiddenIds = []
  }
  return normalizeSessionViewStatePayload({
    title_map: titleMap,
    hidden_ids: hiddenIds,
    active_session_id: activeSessionId || 'main',
    updated_at: new Date().toISOString(),
  })
}

const readTeacherLocalDraftSessionIds = (): string[] => {
  try {
    const raw = localStorage.getItem(TEACHER_LOCAL_DRAFT_SESSIONS_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    if (!Array.isArray(parsed)) return []
    const cleaned = parsed.map((item) => String(item || '').trim()).filter(Boolean)
    return Array.from(new Set(cleaned))
  } catch {
    return []
  }
}

const makeId = () => `${Date.now()}-${Math.random().toString(16).slice(2)}`

const nowTime = () => new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })

const timeFromIso = (iso?: string) => {
  if (!iso) return nowTime()
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return nowTime()
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

const pendingUserMessageId = (jobId: string) => `pending_user_${jobId}`

const withPendingChatOverlay = (messages: Message[], pending: PendingChatJob | null, targetSessionId: string): Message[] => {
  if (!pending?.job_id || pending.session_id !== targetSessionId) return messages
  if (messages.some((msg) => msg.id === pending.placeholder_id)) return messages

  const next = [...messages]
  const hasUserText = pending.user_text
    ? next.some((msg) => msg.role === 'user' && msg.content === pending.user_text)
    : true
  if (!hasUserText && pending.user_text) {
    next.push({
      id: pendingUserMessageId(pending.job_id),
      role: 'user',
      content: pending.user_text,
      time: timeFromIso(new Date(pending.created_at).toISOString()),
    })
  }
  next.push({
    id: pending.placeholder_id,
    role: 'assistant',
    content: '正在生成…',
    time: nowTime(),
  })
  return next
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

const buildSkill = (skill: { id: string; title?: string; desc?: string; prompts?: string[]; examples?: string[] }): Skill => {
  const prompts = Array.isArray(skill.prompts) ? skill.prompts.filter(Boolean) : []
  const examples = Array.isArray(skill.examples) ? skill.examples.filter(Boolean) : []
  return {
    id: skill.id,
    title: (skill.title || '').trim() || '未命名技能',
    desc: (skill.desc || '').trim(),
    prompts: prompts.length ? prompts : ['请描述你的需求。'],
    examples,
  }
}

type WorkbenchTab = 'skills' | 'memory' | 'workflow'
type WheelScrollZone = 'chat' | 'session' | 'workbench'

type WorkflowStepState = 'todo' | 'active' | 'done' | 'error'
type WorkflowIndicatorTone = 'neutral' | 'active' | 'success' | 'error'
type WorkflowStepItem = { key: string; label: string; state: WorkflowStepState }
type WorkflowIndicator = { label: string; tone: WorkflowIndicatorTone; steps: WorkflowStepItem[] }

export default function App() {
  const initialViewStateRef = useRef<SessionViewStatePayload>(readTeacherLocalViewState())
  const [apiBase, setApiBase] = useState(() => localStorage.getItem('apiBaseTeacher') || DEFAULT_API_URL)
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
  const [mainView, setMainView] = useState<'chat' | 'routing'>(() => {
    const raw = localStorage.getItem('teacherMainView')
    return raw === 'routing' ? 'routing' : 'chat'
  })
  const [sessionSidebarOpen, setSessionSidebarOpen] = useState(() => localStorage.getItem('teacherSessionSidebarOpen') !== 'false')
  const [skillsOpen, setSkillsOpen] = useState(() => localStorage.getItem('teacherSkillsOpen') !== 'false')
  const [workbenchTab, setWorkbenchTab] = useState<WorkbenchTab>(() => {
    const raw = localStorage.getItem('teacherWorkbenchTab')
    return raw === 'memory' || raw === 'workflow' ? raw : 'skills'
  })
  const [activeAgentId, setActiveAgentId] = useState(() => localStorage.getItem('teacherActiveAgentId') || 'default')
  const [activeSkillId, setActiveSkillId] = useState(() => localStorage.getItem('teacherActiveSkillId') || 'physics-teacher-ops')
  const [skillPinned, setSkillPinned] = useState(() => localStorage.getItem('teacherSkillPinned') === 'true')
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
  const [composerWarning, setComposerWarning] = useState('')
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
  const [progressPanelCollapsed, setProgressPanelCollapsed] = useState(true)
  const [progressAssignmentId, setProgressAssignmentId] = useState('')
  const [progressLoading, setProgressLoading] = useState(false)
  const [progressError, setProgressError] = useState('')
  const [progressData, setProgressData] = useState<AssignmentProgress | null>(null)
  const [progressOnlyIncomplete, setProgressOnlyIncomplete] = useState(true)
  const [historySessions, setHistorySessions] = useState<TeacherHistorySession[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyError, setHistoryError] = useState('')
  const [historyCursor, setHistoryCursor] = useState(0)
  const [historyHasMore, setHistoryHasMore] = useState(false)
  const [historyQuery, setHistoryQuery] = useState('')
  const [showArchivedSessions, setShowArchivedSessions] = useState(false)
  const [sessionTitleMap, setSessionTitleMap] = useState<Record<string, string>>(() => initialViewStateRef.current.title_map)
  const [deletedSessionIds, setDeletedSessionIds] = useState<string[]>(() => initialViewStateRef.current.hidden_ids)
  const [localDraftSessionIds, setLocalDraftSessionIds] = useState<string[]>(() => readTeacherLocalDraftSessionIds())
  const [openSessionMenuId, setOpenSessionMenuId] = useState('')
  const [sessionLoading, setSessionLoading] = useState(false)
  const [sessionError, setSessionError] = useState('')
  const [sessionCursor, setSessionCursor] = useState(-1)
  const [sessionHasMore, setSessionHasMore] = useState(false)
  const [activeSessionId, setActiveSessionId] = useState(() => initialViewStateRef.current.active_session_id || 'main')
  const [viewStateUpdatedAt, setViewStateUpdatedAt] = useState(() => initialViewStateRef.current.updated_at || new Date().toISOString())
  const [viewStateSyncReady, setViewStateSyncReady] = useState(false)
  const [proposalLoading, setProposalLoading] = useState(false)
  const [proposalError, setProposalError] = useState('')
  const [proposals, setProposals] = useState<TeacherMemoryProposal[]>([])
  const [memoryStatusFilter, setMemoryStatusFilter] = useState<'applied' | 'rejected' | 'all'>('applied')
  const [memoryInsights, setMemoryInsights] = useState<TeacherMemoryInsightsResponse | null>(null)
  const [chatQueueHint, setChatQueueHint] = useState('')
  const PENDING_CHAT_KEY = 'teacherPendingChatJob'
  const [pendingChatJob, setPendingChatJob] = useState<PendingChatJob | null>(() => {
    try {
      const raw = localStorage.getItem(PENDING_CHAT_KEY)
      return raw ? (JSON.parse(raw) as any) : null
    } catch {
      return null
    }
  })

  const [examId, setExamId] = useState('')
  const [examDate, setExamDate] = useState('')
  const [examClassName, setExamClassName] = useState('')
  const [examPaperFiles, setExamPaperFiles] = useState<File[]>([])
  const [examScoreFiles, setExamScoreFiles] = useState<File[]>([])
  const [examAnswerFiles, setExamAnswerFiles] = useState<File[]>([])
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
  const applyingViewStateRef = useRef(false)
  const currentViewStateRef = useRef<SessionViewStatePayload>(initialViewStateRef.current)
  const lastSyncedViewStateSignatureRef = useRef(buildSessionViewStateSignature(initialViewStateRef.current))
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
    localStorage.setItem('apiBaseTeacher', apiBase)
    markdownCacheRef.current.clear()
  }, [apiBase])

  useEffect(() => {
    localStorage.setItem('teacherSkillFavorites', JSON.stringify(favorites))
  }, [favorites])

  useEffect(() => {
    localStorage.setItem('teacherSkillsOpen', String(skillsOpen))
  }, [skillsOpen])

  useEffect(() => {
    localStorage.setItem('teacherWorkbenchTab', workbenchTab)
  }, [workbenchTab])

  useEffect(() => {
    localStorage.setItem('teacherSessionSidebarOpen', String(sessionSidebarOpen))
  }, [sessionSidebarOpen])

  useEffect(() => {
    localStorage.setItem('teacherMainView', mainView)
  }, [mainView])

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
    if (activeAgentId) localStorage.setItem('teacherActiveAgentId', activeAgentId)
    else localStorage.removeItem('teacherActiveAgentId')
  }, [activeAgentId])

  useEffect(() => {
    if (activeSkillId) localStorage.setItem('teacherActiveSkillId', activeSkillId)
    else localStorage.removeItem('teacherActiveSkillId')
  }, [activeSkillId])

  useEffect(() => {
    localStorage.setItem('teacherSkillPinned', String(skillPinned))
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
      localStorage.setItem(TEACHER_LOCAL_DRAFT_SESSIONS_KEY, JSON.stringify(localDraftSessionIds))
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
    if (mainView !== 'chat') {
      setOpenSessionMenuId('')
      setSessionSidebarOpen(false)
      setSkillsOpen(false)
    }
  }, [mainView])

  useEffect(() => {
    if (activeSessionId) localStorage.setItem('teacherActiveSessionId', activeSessionId)
    else localStorage.removeItem('teacherActiveSessionId')
  }, [activeSessionId])

  useEffect(() => {
    currentViewStateRef.current = currentViewState
    localStorage.setItem(
      TEACHER_SESSION_VIEW_STATE_KEY,
      JSON.stringify({
        ...currentViewState,
        active_session_id: activeSessionId,
      }),
    )
    localStorage.setItem('teacherSessionTitles', JSON.stringify(currentViewState.title_map))
    localStorage.setItem('teacherDeletedSessions', JSON.stringify(currentViewState.hidden_ids))
  }, [activeSessionId, currentViewState])

  const pushTeacherViewState = useCallback(
    async (state: SessionViewStatePayload) => {
      const payload = normalizeSessionViewStatePayload({
        ...state,
        active_session_id: '',
      })
      const res = await fetch(`${apiBase}/teacher/session/view-state`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ state: payload }),
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `状态码 ${res.status}`)
      }
      const data = await res.json()
      return normalizeSessionViewStatePayload(data?.state || payload)
    },
    [apiBase],
  )

  useEffect(() => {
    let cancelled = false
    const bootstrap = async () => {
      setViewStateSyncReady(false)
      const localState = currentViewStateRef.current
      try {
        const res = await fetch(`${apiBase}/teacher/session/view-state`)
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
        const saved = await pushTeacherViewState(localState)
        if (cancelled) return
        const sig = buildSessionViewStateSignature(saved)
        lastSyncedViewStateSignatureRef.current = sig
        if (saved.updated_at && saved.updated_at !== localState.updated_at) {
          applyingViewStateRef.current = true
          setViewStateUpdatedAt(saved.updated_at)
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
  }, [apiBase, pushTeacherViewState])

  useEffect(() => {
    if (!viewStateSyncReady) return
    if (applyingViewStateRef.current) {
      applyingViewStateRef.current = false
      return
    }
    setViewStateUpdatedAt(new Date().toISOString())
  }, [deletedSessionIds, sessionTitleMap, viewStateSyncReady])

  useEffect(() => {
    if (!viewStateSyncReady) return
    const signature = buildSessionViewStateSignature(currentViewState)
    if (signature === lastSyncedViewStateSignatureRef.current) return
    const timer = window.setTimeout(async () => {
      try {
        const saved = await pushTeacherViewState(currentViewState)
        const savedSig = buildSessionViewStateSignature(saved)
        lastSyncedViewStateSignatureRef.current = savedSig
        if (saved.updated_at && saved.updated_at !== currentViewState.updated_at) {
          applyingViewStateRef.current = true
          setViewStateUpdatedAt(saved.updated_at)
        }
      } catch {
        // keep local state and retry on next mutation
      }
    }, 260)
    return () => window.clearTimeout(timer)
  }, [currentViewState, pushTeacherViewState, viewStateSyncReady])

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
    if (pendingChatJob) localStorage.setItem(PENDING_CHAT_KEY, JSON.stringify(pendingChatJob))
    else localStorage.removeItem(PENDING_CHAT_KEY)
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
    if (mainView !== 'chat') return
    void refreshTeacherSessions()
  }, [mainView, refreshTeacherSessions])

  useEffect(() => {
    if (mainView !== 'chat') return
    if (!activeSessionId) return
    void loadTeacherSessionMessages(activeSessionId, -1, false)
  }, [activeSessionId, mainView, loadTeacherSessionMessages])

  useEffect(() => {
    if (mainView !== 'chat') return
    const timer = window.setInterval(() => {
      void refreshTeacherSessions()
    }, 30000)
    return () => window.clearInterval(timer)
  }, [mainView, refreshTeacherSessions])

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

  const formatUploadJobStatus = (job: UploadJobStatus) => {
    const lines: string[] = []
    const statusMap: Record<string, string> = {
      queued: '排队中',
      processing: '解析中',
      done: '解析完成（待确认）',
      failed: '解析失败',
      confirmed: '已创建作业',
      confirming: '确认中',
      cancelled: '已取消',
    }
    lines.push(`解析状态：${statusMap[job.status] || job.status}`)
    if (job.progress !== undefined) lines.push(`进度：${job.progress}%`)
    if (job.assignment_id) lines.push(`作业编号：${job.assignment_id}`)
    if (job.question_count !== undefined) lines.push(`题目数量：${job.question_count}`)
    if (job.delivery_mode) lines.push(`交付方式：${job.delivery_mode === 'pdf' ? '文档' : '图片'}`)
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
      cancelled: '已取消',
    }
    lines.push(`解析状态：${statusMap[job.status] || job.status}`)
    if (job.progress !== undefined) lines.push(`进度：${job.progress}%`)
    if (job.exam_id) lines.push(`考试编号：${job.exam_id}`)
    if (job.counts?.students !== undefined) lines.push(`学生数：${job.counts.students}`)
    if (job.counts?.questions !== undefined) lines.push(`题目数：${job.counts.questions}`)
    if (job.scoring?.status) {
      const scoreMap: Record<string, string> = { scored: '已评分', partial: '部分已评分', unscored: '未评分' }
      const label = scoreMap[job.scoring.status] || job.scoring.status
      const sTotal = job.scoring.students_total ?? job.counts?.students
      const sScored = job.scoring.students_scored ?? job.counts_scored?.students
      if (sTotal !== undefined && sScored !== undefined) lines.push(`评分：${label}（已评分学生 ${sScored}/${sTotal}）`)
      else lines.push(`评分：${label}`)
      const defaults = Array.isArray(job.scoring.default_max_score_qids) ? job.scoring.default_max_score_qids.length : 0
      if (defaults) lines.push(`提示：有 ${defaults} 题缺少满分，系统已默认按 1 分/题 评分（建议在草稿里核对满分）。`)
    }
    if (job.error) lines.push(`错误：${job.error}`)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const extra = job as any
    if (extra.error_detail) lines.push(`详情：${extra.error_detail}`)
    if (Array.isArray(extra.hints) && extra.hints.length) lines.push(`建议：${extra.hints.join('；')}`)
    if (job.warnings && job.warnings.length) lines.push(`解析提示：${job.warnings.join('；')}`)
    return lines.join('\n')
  }

  const formatExamJobSummary = (job: ExamUploadJobStatus | null, fallbackExamId?: string) => {
    if (!job) return `未开始解析${fallbackExamId ? ` · 考试编号：${fallbackExamId}` : ''}`
    const statusMap: Record<string, string> = {
      queued: '排队中',
      processing: '解析中',
      done: '解析完成（待确认）',
      failed: '解析失败',
      confirmed: '已创建',
      confirming: '确认中',
      cancelled: '已取消',
    }
    const parts: string[] = []
    parts.push(`状态：${statusMap[job.status] || job.status}`)
    if (job.progress !== undefined) parts.push(`${job.progress}%`)
    parts.push(`考试编号：${job.exam_id || fallbackExamId || job.job_id}`)
    if (job.counts?.students !== undefined) parts.push(`学生：${job.counts.students}`)
    if (job.counts?.questions !== undefined) parts.push(`题目：${job.counts.questions}`)
    if (job.scoring?.status) {
      const scoreMap: Record<string, string> = { scored: '已评分', partial: '部分已评分', unscored: '未评分' }
      parts.push(`评分：${scoreMap[job.scoring.status] || job.scoring.status}`)
    }
    if (job.status === 'failed' && job.error) parts.push(`错误：${job.error}`)
    return parts.join(' · ')
  }

  const formatExamDraftSummary = (draft: ExamUploadDraft | null, jobInfo: ExamUploadJobStatus | null) => {
    if (!draft) return ''
    const parts: string[] = []
    parts.push(`考试编号：${draft.exam_id}`)
    if (draft.meta?.date) parts.push(String(draft.meta.date))
    if (draft.meta?.class_name) parts.push(String(draft.meta.class_name))
    if (draft.counts?.students !== undefined) parts.push(`学生：${draft.counts.students}`)
    if (draft.counts?.questions !== undefined) parts.push(`题目：${draft.counts.questions}`)
    if (jobInfo?.status === 'confirmed') parts.push('已创建')
    else if (jobInfo?.status === 'done') parts.push('待创建')
    return parts.join(' · ')
  }

  const formatUploadJobSummary = (job: UploadJobStatus | null, fallbackAssignmentId?: string) => {
    if (!job) return `未开始解析${fallbackAssignmentId ? ` · 作业编号：${fallbackAssignmentId}` : ''}`
    const statusMap: Record<string, string> = {
      queued: '排队中',
      processing: '解析中',
      done: '解析完成（待确认）',
      failed: '解析失败',
      confirmed: '已创建',
      confirming: '确认中',
      cancelled: '已取消',
    }
    const parts: string[] = []
    parts.push(`状态：${statusMap[job.status] || job.status}`)
    if (job.progress !== undefined) parts.push(`${job.progress}%`)
    parts.push(`作业编号：${job.assignment_id || fallbackAssignmentId || job.job_id}`)
    if (job.question_count !== undefined) parts.push(`题目：${job.question_count}`)
    if (job.requirements_missing && job.requirements_missing.length) parts.push(`缺失：${job.requirements_missing.length}项`)
    if (job.status === 'failed' && job.error) parts.push(`错误：${job.error}`)
    return parts.join(' · ')
  }

  const formatDraftSummary = (draft: UploadDraft | null, jobInfo: UploadJobStatus | null) => {
    if (!draft) return ''
    const scopeLabel = draft.scope === 'public' ? '公共作业' : draft.scope === 'class' ? '班级作业' : '私人作业'
    const parts: string[] = []
    parts.push(`作业编号：${draft.assignment_id}`)
    if (draft.date) parts.push(draft.date)
    parts.push(scopeLabel)
    parts.push(`题目：${draft.questions?.length || 0}`)
    if (draft.requirements_missing && draft.requirements_missing.length) parts.push(`缺失：${draft.requirements_missing.length}项`)
    else parts.push('要求已补全')
    if (jobInfo?.status === 'confirmed') parts.push('已创建')
    else if (jobInfo?.status === 'done') parts.push('待创建')
    return parts.join(' · ')
  }

  const formatProgressSummary = (p: AssignmentProgress | null, fallbackAssignmentId?: string) => {
    const aid = (p?.assignment_id || fallbackAssignmentId || '').trim()
    if (!aid) return '未加载作业完成情况'
    const expected = p?.counts?.expected ?? p?.expected_count ?? 0
    const completed = p?.counts?.completed ?? 0
    const overdue = p?.counts?.overdue ?? 0
    const parts: string[] = []
    parts.push(`作业编号：${aid}`)
    if (p?.date) parts.push(String(p.date))
    parts.push(`完成：${completed}/${expected}`)
    if (overdue) parts.push(`逾期：${overdue}`)
    return parts.join(' · ')
  }

  const assignmentWorkflowIndicator = useMemo<WorkflowIndicator>(() => {
    const steps: WorkflowStepItem[] = [
      { key: 'upload', label: '上传文件', state: 'todo' },
      { key: 'parse', label: '解析', state: 'todo' },
      { key: 'review', label: '审核草稿', state: 'todo' },
      { key: 'confirm', label: '创建作业', state: 'todo' },
    ]
    const setState = (key: WorkflowStepItem['key'], state: WorkflowStepState) => {
      const step = steps.find((item) => item.key === key)
      if (step) step.state = state
    }
    const markDone = (...keys: WorkflowStepItem['key'][]) => {
      keys.forEach((key) => setState(key, 'done'))
    }

    const status = uploadJobInfo?.status
    const hasError = Boolean(uploadError || draftError || draftActionError || status === 'failed' || status === 'cancelled')

    let label = '未开始'
    let tone: WorkflowIndicatorTone = 'neutral'
    let stage: 'idle' | 'uploading' | 'parsing' | 'review' | 'confirming' | 'completed' | 'failed-parse' | 'failed-review' | 'failed-confirm' = 'idle'

    if (status === 'confirmed') {
      stage = 'completed'
      label = '已创建作业'
      tone = 'success'
    } else if (uploadConfirming || status === 'confirming') {
      stage = 'confirming'
      label = '创建中'
      tone = 'active'
    } else if (status === 'done' || uploadDraft) {
      stage = 'review'
      label = '待审核'
      tone = 'active'
    } else if (uploading) {
      stage = 'uploading'
      label = '上传中'
      tone = 'active'
    } else if (status === 'queued' || status === 'processing' || uploadJobId) {
      stage = 'parsing'
      label = '解析中'
      tone = 'active'
    }

    if (hasError) {
      tone = 'error'
      if (status === 'failed' || status === 'cancelled' || uploadError) {
        stage = 'failed-parse'
        label = status === 'cancelled' ? '流程取消' : '解析失败'
      } else if (uploadConfirming || status === 'confirming') {
        stage = 'failed-confirm'
        label = '创建失败'
      } else {
        stage = 'failed-review'
        label = '审核异常'
      }
    }

    switch (stage) {
      case 'uploading':
        setState('upload', 'active')
        break
      case 'parsing':
        markDone('upload')
        setState('parse', 'active')
        break
      case 'review':
        markDone('upload', 'parse')
        setState('review', 'active')
        break
      case 'confirming':
        markDone('upload', 'parse', 'review')
        setState('confirm', 'active')
        break
      case 'completed':
        markDone('upload', 'parse', 'review', 'confirm')
        break
      case 'failed-parse':
        if (uploading) {
          setState('upload', 'error')
        } else {
          markDone('upload')
          setState('parse', 'error')
        }
        break
      case 'failed-review':
        markDone('upload', 'parse')
        setState('review', 'error')
        break
      case 'failed-confirm':
        markDone('upload', 'parse', 'review')
        setState('confirm', 'error')
        break
      default:
        break
    }

    return { label, tone, steps }
  }, [draftActionError, draftError, uploadConfirming, uploadDraft, uploadError, uploadJobId, uploadJobInfo?.status, uploading])

  const examWorkflowIndicator = useMemo<WorkflowIndicator>(() => {
    const steps: WorkflowStepItem[] = [
      { key: 'upload', label: '上传文件', state: 'todo' },
      { key: 'parse', label: '解析', state: 'todo' },
      { key: 'review', label: '审核草稿', state: 'todo' },
      { key: 'confirm', label: '创建考试', state: 'todo' },
    ]
    const setState = (key: WorkflowStepItem['key'], state: WorkflowStepState) => {
      const step = steps.find((item) => item.key === key)
      if (step) step.state = state
    }
    const markDone = (...keys: WorkflowStepItem['key'][]) => {
      keys.forEach((key) => setState(key, 'done'))
    }

    const status = examJobInfo?.status
    const hasError = Boolean(examUploadError || examDraftError || examDraftActionError || status === 'failed' || status === 'cancelled')

    let label = '未开始'
    let tone: WorkflowIndicatorTone = 'neutral'
    let stage: 'idle' | 'uploading' | 'parsing' | 'review' | 'confirming' | 'completed' | 'failed-parse' | 'failed-review' | 'failed-confirm' = 'idle'

    if (status === 'confirmed') {
      stage = 'completed'
      label = '已创建考试'
      tone = 'success'
    } else if (examConfirming || status === 'confirming') {
      stage = 'confirming'
      label = '创建中'
      tone = 'active'
    } else if (status === 'done' || examDraft) {
      stage = 'review'
      label = '待审核'
      tone = 'active'
    } else if (examUploading) {
      stage = 'uploading'
      label = '上传中'
      tone = 'active'
    } else if (status === 'queued' || status === 'processing' || examJobId) {
      stage = 'parsing'
      label = '解析中'
      tone = 'active'
    }

    if (hasError) {
      tone = 'error'
      if (status === 'failed' || status === 'cancelled' || examUploadError) {
        stage = 'failed-parse'
        label = status === 'cancelled' ? '流程取消' : '解析失败'
      } else if (examConfirming || status === 'confirming') {
        stage = 'failed-confirm'
        label = '创建失败'
      } else {
        stage = 'failed-review'
        label = '审核异常'
      }
    }

    switch (stage) {
      case 'uploading':
        setState('upload', 'active')
        break
      case 'parsing':
        markDone('upload')
        setState('parse', 'active')
        break
      case 'review':
        markDone('upload', 'parse')
        setState('review', 'active')
        break
      case 'confirming':
        markDone('upload', 'parse', 'review')
        setState('confirm', 'active')
        break
      case 'completed':
        markDone('upload', 'parse', 'review', 'confirm')
        break
      case 'failed-parse':
        if (examUploading) {
          setState('upload', 'error')
        } else {
          markDone('upload')
          setState('parse', 'error')
        }
        break
      case 'failed-review':
        markDone('upload', 'parse')
        setState('review', 'error')
        break
      case 'failed-confirm':
        markDone('upload', 'parse', 'review')
        setState('confirm', 'error')
        break
      default:
        break
    }

    return { label, tone, steps }
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
          throw new Error(text || `状态码 ${res.status}`)
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
          throw new Error(text || `状态码 ${res.status}`)
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
    let cancelled = false
    let timeoutId: number | null = null
    let inFlight = false
    let delayMs = 800

    const clearTimer = () => {
      if (timeoutId) window.clearTimeout(timeoutId)
      timeoutId = null
    }

    const jitter = (ms: number) => Math.round(ms * (0.85 + Math.random() * 0.3))

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
          setChatQueueHint('')
          setSending(false)
          void refreshTeacherSessions()
          return
        }
        if (data.status === 'failed' || data.status === 'cancelled') {
          const msg = data.error_detail || data.error || '请求失败'
          updateMessage(pendingChatJob.placeholder_id, { content: `抱歉，请求失败：${msg}`, time: nowTime() })
          setPendingChatJob(null)
          setChatQueueHint('')
          setSending(false)
          return
        }
        const lanePos = Number(data.lane_queue_position || 0)
        const laneSize = Number(data.lane_queue_size || 0)
        if (data.status === 'queued') {
          setChatQueueHint(lanePos > 0 ? `排队中，前方 ${lanePos} 条（队列 ${laneSize}）` : '排队中...')
        } else if (data.status === 'processing') {
          setChatQueueHint('处理中...')
        } else {
          setChatQueueHint('')
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
        clearTimer()
        void poll()
      }
    }
    document.addEventListener('visibilitychange', onVisibilityChange)
    void poll()

    return () => {
      cancelled = true
      setChatQueueHint('')
      document.removeEventListener('visibilitychange', onVisibilityChange)
      clearTimer()
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
    if (mainView !== 'chat') {
      setWheelScrollZone('chat')
      return
    }
    if (wheelScrollZoneRef.current === 'session' && !sessionSidebarOpen) {
      setWheelScrollZone('chat')
    }
    if (wheelScrollZoneRef.current === 'workbench' && !skillsOpen) {
      setWheelScrollZone('chat')
    }
  }, [mainView, sessionSidebarOpen, setWheelScrollZone, skillsOpen])

  useEffect(() => {
    if (typeof document === 'undefined') return
    const enabled = mainView === 'chat' && !isMobileViewport()
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
  }, [isMobileViewport, mainView, sessionSidebarOpen, setWheelScrollZone, skillsOpen])

  useEffect(() => {
    if (typeof window === 'undefined') return
    const enabled = mainView === 'chat' && !isMobileViewport()
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
      const destination = resolveWheelScrollTarget(zone)
      if (tryScroll(destination)) {
        event.preventDefault()
        return
      }
      const fallbackZones: WheelScrollZone[] = ['chat', 'session', 'workbench']
      for (const nextZone of fallbackZones) {
        if (nextZone === zone) continue
        const fallback = resolveWheelScrollTarget(nextZone)
        if (fallback === destination) continue
        if (tryScroll(fallback)) {
          event.preventDefault()
          return
        }
      }
    }
    window.addEventListener('wheel', onWheel, { passive: false, capture: true })
    return () => {
      window.removeEventListener('wheel', onWheel, true)
    }
  }, [isMobileViewport, mainView, resolveWheelScrollTarget, sessionSidebarOpen, skillsOpen])

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

  const toggleSessionArchive = useCallback(
    (sessionId: string) => {
      const sid = String(sessionId || '').trim()
      if (!sid) return
      const isArchived = deletedSessionIds.includes(sid)
      const action = isArchived ? '恢复' : '归档'
      if (!window.confirm(`确认${action}会话 ${getSessionTitle(sid)}？`)) {
        setOpenSessionMenuId('')
        return
      }
      setOpenSessionMenuId('')
      setDeletedSessionIds((prev) => {
        if (isArchived) return prev.filter((id) => id !== sid)
        if (prev.includes(sid)) return prev
        return [...prev, sid]
      })
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
    },
    [activeSessionId, deletedSessionIds, getSessionTitle, startNewTeacherSession, visibleHistorySessions],
  )

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
    requestAnimationFrame(() => {
      if (!inputRef.current) return
      inputRef.current.focus()
      inputRef.current.setSelectionRange(nextPos, nextPos)
      setCursorPos(nextPos)
    })
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
    setInput(nextValue)
    requestAnimationFrame(() => {
      if (!inputRef.current) return
      const nextPos = `${before}${token} `.length
      inputRef.current.focus()
      inputRef.current.setSelectionRange(nextPos, nextPos)
      setCursorPos(nextPos)
    })
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

    setWheelScrollZone('chat')
    enableAutoScroll()
    setMessages((prev) => [
      ...prev,
      { id: makeId(), role: 'user', content: cleanedText, time: nowTime() },
      { id: placeholderId, role: 'assistant', content: '正在生成…', time: nowTime() },
    ])
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
              status: prev.status === 'confirmed' ? 'confirmed' : 'confirming',
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
        setUploadJobInfo((prev) => (prev ? { ...prev, status: 'confirmed' } : prev))
        setDraftPanelCollapsed(true)
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

  return (
    <div ref={appRef} className="app teacher" style={{ ['--teacher-topbar-height' as any]: `${topbarHeight}px` }}>
      <header ref={topbarRef} className="topbar">
        <div className="top-left">
          <div className="brand">物理教学助手 · 老师端</div>
          {mainView === 'chat' ? (
            <button className="ghost" type="button" onClick={toggleSessionSidebar}>
              {sessionSidebarOpen ? '收起会话' : '展开会话'}
            </button>
          ) : null}
        </div>
        <div className="top-actions">
          <div className="view-switch">
            <button type="button" className={mainView === 'chat' ? 'active' : ''} onClick={() => setMainView('chat')}>
              首页工作台
            </button>
            <button type="button" className={mainView === 'routing' ? 'active' : ''} onClick={() => setMainView('routing')}>
              模型路由
            </button>
          </div>
          <div className="role-badge teacher">身份：老师</div>
          {mainView === 'chat' ? (
            <button
              className="ghost"
              type="button"
              onClick={toggleSkillsWorkbench}
            >
              {skillsOpen ? '收起工作台' : '打开工作台'}
            </button>
          ) : null}
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
          <div className="settings-hint">修改后立即生效。</div>
        </section>
      )}

      <div
        className={`teacher-layout ${mainView === 'chat' ? 'chat-view' : ''} ${sessionSidebarOpen ? 'session-open' : 'session-collapsed'} ${skillsOpen ? 'workbench-open' : ''}`}
      >
        {mainView === 'chat' ? (
          <button
            type="button"
            className={`layout-overlay ${sessionSidebarOpen || skillsOpen ? 'show' : ''}`}
            aria-label="关闭侧边栏"
            onClick={() => {
              setSessionSidebarOpen(false)
              setSkillsOpen(false)
            }}
          />
        ) : null}
        {mainView === 'chat' ? (
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
        ) : null}

        <main className={`chat-shell ${mainView === 'routing' ? 'routing-shell' : ''}`}>
          {mainView === 'routing' ? (
            <RoutingPage apiBase={apiBase} />
          ) : (
            <>

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
            </>
          )}
        </main>

        {mainView === 'chat' && (
          <aside className={`skills-panel ${skillsOpen ? 'open' : ''}`}>
            <div className="skills-header">
              <h3>工作台</h3>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  className="ghost"
                  onClick={() => {
                    if (workbenchTab === 'skills') {
                      void fetchSkills()
                    } else if (workbenchTab === 'memory') {
                      void refreshMemoryProposals()
                      void refreshMemoryInsights()
                    } else {
                      refreshWorkflowWorkbench()
                    }
                  }}
                  disabled={
                    workbenchTab === 'skills'
                      ? skillsLoading
                      : workbenchTab === 'memory'
                        ? proposalLoading
                        : progressLoading || uploading || examUploading
                  }
                >
                  刷新
                </button>
                <button className="ghost" onClick={() => setSkillsOpen(false)}>
                  收起
                </button>
              </div>
            </div>
            <div className="view-switch workbench-switch">
              <button type="button" className={workbenchTab === 'skills' ? 'active' : ''} onClick={() => setWorkbenchTab('skills')}>
                技能
              </button>
              <button type="button" className={workbenchTab === 'memory' ? 'active' : ''} onClick={() => setWorkbenchTab('memory')}>
                自动记忆
              </button>
              <button type="button" className={workbenchTab === 'workflow' ? 'active' : ''} onClick={() => setWorkbenchTab('workflow')}>
                工作流
              </button>
            </div>
            {workbenchTab === 'skills' ? (
              <>
                <section className="agent-panel">
                  <div className="agent-panel-header">
                    <strong>执行 Agent</strong>
                    <span className="muted">`@agent` 召唤</span>
                  </div>
                  <div className="agent-list">
                    {agentList.map((agent) => (
                      <div key={agent.id} className={`agent-card ${agent.id === activeAgentId ? 'active' : ''}`}>
                        <div className="agent-title">
                          <strong>@{agent.id}</strong>
                          <span>{agent.title}</span>
                        </div>
                        <p>{agent.desc}</p>
                        <div className="agent-actions">
                          <button
                            type="button"
                            onClick={() => {
                              setActiveAgentId(agent.id)
                              setComposerWarning('')
                            }}
                          >
                            设为当前
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              setActiveAgentId(agent.id)
                              insertInvocationTokenAtCursor('agent', agent.id)
                            }}
                          >
                            插入 @
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
                <div className="skills-tools">
                  <input
                    value={skillQuery}
                    onChange={(e) => setSkillQuery(e.target.value)}
                    placeholder="搜索技能"
                  />
                  <button
                    type="button"
                    className="ghost"
                    disabled={!skillPinned}
                    onClick={() => {
                      setSkillPinned(false)
                      setComposerWarning('已切换到自动技能路由（未显式指定时由后端自动选择）。')
                    }}
                  >
                    使用自动路由
                  </button>
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
                    <div key={skill.id} className={`skill-card ${skillPinned && skill.id === activeSkillId ? 'active' : ''}`}>
                      <div className="skill-title">
                        <div>
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
                      <div className="skill-actions">
                        <button
                          type="button"
                          onClick={() => {
                            chooseSkill(skill.id, true)
                            setComposerWarning('')
                          }}
                        >
                          设为当前
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            chooseSkill(skill.id, true)
                            insertInvocationTokenAtCursor('skill', skill.id)
                          }}
                        >
                          插入 $
                        </button>
                      </div>
                      <div className="skill-prompts">
                        {skill.prompts.map((prompt) => (
                          <button
                            key={prompt}
                            type="button"
                            onClick={() => {
                              chooseSkill(skill.id, true)
                              insertPrompt(prompt)
                            }}
                          >
                            使用模板
                          </button>
                        ))}
                      </div>
                      <div className="skill-examples">
                        {skill.examples.map((ex) => (
                          <button
                            key={ex}
                            type="button"
                            onClick={() => {
                              chooseSkill(skill.id, true)
                              insertPrompt(ex)
                            }}
                          >
                            {ex}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            ) : workbenchTab === 'workflow' ? (
              <section className="memory-panel workbench-memory workbench-workflow">
                <div className="history-header">
                  <strong>作业流程控制</strong>
                </div>
                <div className="workflow-summary-card">
                  <div className="segmented">
                    <button type="button" className={uploadMode === 'assignment' ? 'active' : ''} onClick={() => setUploadMode('assignment')}>
                      作业
                    </button>
                    <button type="button" className={uploadMode === 'exam' ? 'active' : ''} onClick={() => setUploadMode('exam')}>
                      考试
                    </button>
                  </div>
                  <div className="workflow-headline">
                    <div className="muted">当前流程状态</div>
                    <span className={`workflow-chip ${activeWorkflowIndicator.tone}`}>{activeWorkflowIndicator.label}</span>
                  </div>
                  <div className="workflow-steps">
                    {activeWorkflowIndicator.steps.map((step) => (
                      <div key={step.key} className={`workflow-step ${step.state}`}>
                        <span className="workflow-step-dot" />
                        <span className="workflow-step-label">{step.label}</span>
                      </div>
                    ))}
                  </div>
                  <div className="workflow-status">
                    {uploadMode === 'assignment'
                      ? formatUploadJobSummary(uploadJobInfo, uploadAssignmentId.trim())
                      : formatExamJobSummary(examJobInfo, examId.trim())}
                  </div>
                  <div className="workflow-actions">
                    <button type="button" className="ghost" onClick={() => scrollToWorkflowSection('workflow-upload-section')}>
                      定位上传区
                    </button>
                    {uploadMode === 'assignment' ? (
                      <button type="button" className="ghost" onClick={() => scrollToWorkflowSection('workflow-assignment-draft-section')}>
                        定位作业草稿
                      </button>
                    ) : (
                      <button type="button" className="ghost" onClick={() => scrollToWorkflowSection('workflow-exam-draft-section')}>
                        定位考试草稿
                      </button>
                    )}
                    <button type="button" className="ghost" onClick={refreshWorkflowWorkbench}>
                      刷新状态
                    </button>
                  </div>
                </div>
                {uploadMode === 'assignment' ? (
                  <div className="workflow-summary-card">
                    <div className="muted">作业完成情况</div>
                    <div className="workflow-status">{formatProgressSummary(progressData, progressAssignmentId)}</div>
                    <div className="workflow-actions">
                      <button type="button" className="ghost" onClick={() => scrollToWorkflowSection('workflow-progress-section')}>
                        定位完成情况
                      </button>
                      <button type="button" className="ghost" disabled={progressLoading} onClick={() => void fetchAssignmentProgress()}>
                        {progressLoading ? '加载中…' : '刷新完成率'}
                      </button>
                    </div>
                  </div>
                ) : null}
          <section id="workflow-upload-section" className={`upload-card ${uploadCardCollapsed ? 'collapsed' : ''}`}>
	            <div className="panel-header">
	              <div className="panel-title">
	                <h3>{uploadMode === 'assignment' ? '上传作业文件（文档 / 图片）' : '上传考试文件（试卷 + 成绩表）'}</h3>
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
	                          <label>作业编号</label>
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
	                          <label>学生编号（私人作业必填）</label>
	                          <input
	                            value={uploadStudentIds}
	                            onChange={(e) => setUploadStudentIds(e.target.value)}
	                            placeholder="例如：高二2403班_刘昊然"
	                          />
	                        </div>
	                        <div className="upload-field">
	                          <label>作业文件（文档/图片）</label>
	                          <input
	                            type="file"
	                            multiple
	                            accept="application/pdf,image/*,.md,.markdown,.tex"
	                            onChange={(e) => setUploadFiles(Array.from(e.target.files || []))}
	                          />
	                        </div>
	                        <div className="upload-field">
	                          <label>答案文件（可选）</label>
	                          <input
	                            type="file"
	                            multiple
	                            accept="application/pdf,image/*,.md,.markdown,.tex"
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
	                    <p>上传考试试卷、标准答案（可选）与成绩表后，系统将生成考试数据与分析草稿。成绩表推荐电子表格（最稳）。</p>
	                    <form className="upload-form" onSubmit={handleUploadExam}>
	                      <div className="upload-grid">
	                        <div className="upload-field">
	                          <label>考试编号（可选）</label>
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
	                            accept="application/pdf,image/*,.md,.markdown,.tex"
	                            onChange={(e) => setExamPaperFiles(Array.from(e.target.files || []))}
	                          />
	                        </div>
	                        <div className="upload-field">
	                          <label>答案文件（可选）</label>
	                          <input
	                            type="file"
	                            multiple
	                            accept="application/pdf,image/*,.md,.markdown,.tex"
	                            onChange={(e) => setExamAnswerFiles(Array.from(e.target.files || []))}
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

	          {uploadMode === 'assignment' && (
	            <section id="workflow-progress-section" className={`draft-panel ${progressPanelCollapsed ? 'collapsed' : ''}`}>
	              <div className="panel-header">
	                <h3>作业完成情况</h3>
	                {progressPanelCollapsed ? (
	                  <div
	                    className="panel-summary"
	                    title={formatProgressSummary(progressData, progressAssignmentId)}
	                  >
	                    {formatProgressSummary(progressData, progressAssignmentId)}
	                  </div>
	                ) : null}
	                <button type="button" className="ghost" onClick={() => setProgressPanelCollapsed((v) => !v)}>
	                  {progressPanelCollapsed ? '展开' : '收起'}
	                </button>
	              </div>
	              {progressPanelCollapsed ? null : (
	                <>
	                  <div className="progress-toolbar">
	                    <div className="upload-field">
	                      <label>作业编号</label>
	                      <input
	                        value={progressAssignmentId}
	                        onChange={(e) => setProgressAssignmentId(e.target.value)}
	                        placeholder="例如：A2403_2026-02-04"
	                      />
	                    </div>
	                    <div className="progress-toolbar-actions">
	                      <label className="toggle">
	                        <input
	                          type="checkbox"
	                          checked={progressOnlyIncomplete}
	                          onChange={(e) => setProgressOnlyIncomplete(e.target.checked)}
	                        />
	                        只看未完成
	                      </label>
	                      <button
	                        type="button"
	                        className="secondary-btn"
	                        disabled={progressLoading}
	                        onClick={() => void fetchAssignmentProgress()}
	                      >
	                        {progressLoading ? '加载中…' : '刷新'}
	                      </button>
	                    </div>
	                  </div>

	                  {progressError && <div className="status err">{progressError}</div>}
	                  {progressData && (
	                    <div className="draft-meta">
	                      <div>作业编号：{progressData.assignment_id}</div>
	                      <div>日期：{String(progressData.date || '') || '（未设置）'}</div>
	                      <div>
	                        应交：{progressData.counts?.expected ?? progressData.expected_count ?? 0} · 完成：
	                        {progressData.counts?.completed ?? 0} · 讨论通过：
	                        {progressData.counts?.discussion_pass ?? 0} · 已评分：
	                        {progressData.counts?.submitted ?? 0}
	                        {progressData.counts?.overdue ? ` · 逾期：${progressData.counts.overdue}` : ''}
	                      </div>
	                      <div>截止：{progressData.due_at ? progressData.due_at : '永不截止'}</div>
	                    </div>
	                  )}

	                  {progressData?.students && progressData.students.length > 0 && (
	                    <div className="progress-list">
	                      {(progressOnlyIncomplete
	                        ? progressData.students.filter((s) => !s.complete)
	                        : progressData.students
	                      ).map((s) => {
	                        const attempts = s.submission?.attempts ?? 0
	                        const best = s.submission?.best as any
	                        const graded = best
	                          ? `得分${best.score_earned ?? 0}`
	                          : attempts
	                            ? `已提交${attempts}次（未评分）`
	                            : '未提交'
	                        const discussion = s.discussion?.pass ? '讨论通过' : '讨论未完成'
	                        const overdue = s.overdue ? ' · 逾期' : ''
	                        const name = [s.class_name, s.student_name].filter(Boolean).join(' ')
	                        return (
	                          <div key={s.student_id} className={`progress-row ${s.complete ? 'ok' : 'todo'}`}>
	                            <div className="progress-main">
	                              <strong>{s.student_id}</strong>
	                              {name ? <span className="muted"> {name}</span> : null}
	                            </div>
	                            <div className="progress-sub">
	                              {discussion} · {graded}
	                              {overdue}
	                            </div>
	                          </div>
	                        )
	                      })}
	                    </div>
	                  )}
	                </>
	              )}
	            </section>
	          )}

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
	            <section id="workflow-exam-draft-section" className={`draft-panel ${examDraftPanelCollapsed ? 'collapsed' : ''}`}>
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
	                    <div>考试编号：{examDraft.exam_id}</div>
	                    <div>日期：{String(examDraft.meta?.date || examDraft.date || '') || '（未设置）'}</div>
	                    {examDraft.meta?.class_name ? <div>班级：{String(examDraft.meta.class_name)}</div> : null}
	                    {examDraft.answer_files?.length ? <div>答案文件：{examDraft.answer_files.length} 份</div> : null}
	                    {examDraft.answer_key?.count !== undefined && examDraft.answer_key?.count !== 0 ? (
	                      <div>解析到答案：{String(examDraft.answer_key.count)} 条</div>
	                    ) : null}
	                    {examDraft.counts?.students !== undefined ? <div>学生数：{examDraft.counts.students}</div> : null}
	                    {examDraft.scoring?.status ? (
	                      <div>
	                        评分状态：
	                        {{
	                          scored: '已评分',
	                          partial: '部分已评分',
	                          unscored: '未评分',
	                        }[String(examDraft.scoring.status)] || String(examDraft.scoring.status)}
	                        {examDraft.scoring?.students_scored !== undefined && examDraft.scoring?.students_total !== undefined
	                          ? `（已评分学生 ${examDraft.scoring.students_scored}/${examDraft.scoring.students_total}）`
	                          : ''}
	                      </div>
	                    ) : null}
	                    {Array.isArray(examDraft.scoring?.default_max_score_qids) && examDraft.scoring.default_max_score_qids.length ? (
	                      <div className="muted">
	                        提示：有 {examDraft.scoring.default_max_score_qids.length} 题缺少满分，系统已默认按 1 分/题 评分（建议核对题目满分）。
	                      </div>
	                    ) : null}
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
	                    <div className="draft-card">
	                      <h4>标准答案（可编辑）</h4>
	                      <div className="draft-form">
	                        <label>答案文本（每行一个，示例：1 A）</label>
	                        <textarea
	                          value={String(examDraft.answer_key_text || '')}
	                          onChange={(e) => updateExamAnswerKeyText(e.target.value)}
	                          onKeyDown={stopKeyPropagation}
	                          rows={8}
	                          placeholder={`示例：\n1 A\n2 C\n12(1) B`}
	                        />
	                      </div>
	                      {examDraft.answer_text_excerpt ? (
	                        <details style={{ marginTop: 8 }}>
	                          <summary className="muted">查看识别到的答案文本（可用作填充参考）</summary>
	                          <pre className="status ok" style={{ whiteSpace: 'pre-wrap' }}>
	                            {String(examDraft.answer_text_excerpt)}
	                          </pre>
	                          <div className="draft-actions" style={{ marginTop: 8 }}>
	                            <button
	                              type="button"
	                              className="secondary-btn"
	                              onClick={() => {
	                                if (!examDraft.answer_text_excerpt) return
	                                updateExamAnswerKeyText(String(examDraft.answer_text_excerpt))
	                              }}
	                              disabled={!examDraft.answer_text_excerpt}
	                            >
	                              用识别文本填充
	                            </button>
	                          </div>
	                        </details>
	                      ) : (
	                        <div className="muted">未检测到答案文件识别文本。你也可以直接粘贴答案文本。</div>
	                      )}
	                      <div className="muted" style={{ marginTop: 8 }}>
	                        提示：保存草稿后，创建考试时会使用该答案对“作答字母但无分数”的客观题自动评分。
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
            <section id="workflow-assignment-draft-section" className={`draft-panel ${draftPanelCollapsed ? 'collapsed' : ''}`}>
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
                    <div>作业编号：{uploadDraft.assignment_id}</div>
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
                    <div>交付方式：{uploadDraft.delivery_mode === 'pdf' ? '文档' : '图片'}</div>
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


              </section>
            ) : (
              <section className="memory-panel workbench-memory">
                <div className="history-header">
                  <strong>自动记忆记录</strong>
                  <div className="history-actions">
                    <div className="view-switch">
                      <button
                        type="button"
                        className={memoryStatusFilter === 'applied' ? 'active' : ''}
                        onClick={() => setMemoryStatusFilter('applied')}
                      >
                        已写入
                      </button>
                      <button
                        type="button"
                        className={memoryStatusFilter === 'rejected' ? 'active' : ''}
                        onClick={() => setMemoryStatusFilter('rejected')}
                      >
                        已拦截
                      </button>
                      <button
                        type="button"
                        className={memoryStatusFilter === 'all' ? 'active' : ''}
                        onClick={() => setMemoryStatusFilter('all')}
                      >
                        全部
                      </button>
                    </div>
                  </div>
                </div>
                {memoryInsights?.summary && (
                  <div className="memory-metrics-grid">
                    <div className="memory-metric-card">
                      <div className="memory-metric-value">{memoryInsights.summary.active_total ?? 0}</div>
                      <div className="memory-metric-label">活跃记忆</div>
                    </div>
                    <div className="memory-metric-card">
                      <div className="memory-metric-value">{memoryInsights.summary.expired_total ?? 0}</div>
                      <div className="memory-metric-label">已过期</div>
                    </div>
                    <div className="memory-metric-card">
                      <div className="memory-metric-value">{memoryInsights.summary.superseded_total ?? 0}</div>
                      <div className="memory-metric-label">已替代</div>
                    </div>
                    <div className="memory-metric-card">
                      <div className="memory-metric-value">{memoryInsights.summary.avg_priority_active ?? 0}</div>
                      <div className="memory-metric-label">平均优先级</div>
                    </div>
                    <div className="memory-metric-card">
                      <div className="memory-metric-value">
                        {`${Math.round((memoryInsights.retrieval?.search_hit_rate ?? 0) * 100)}%`}
                      </div>
                      <div className="memory-metric-label">检索命中率(14d)</div>
                    </div>
                    <div className="memory-metric-card">
                      <div className="memory-metric-value">{memoryInsights.retrieval?.search_calls ?? 0}</div>
                      <div className="memory-metric-label">检索次数(14d)</div>
                    </div>
                  </div>
                )}
                {Array.isArray(memoryInsights?.top_queries) && (memoryInsights?.top_queries || []).length > 0 && (
                  <div className="memory-query-list">
                    <div className="muted">高频命中查询（14天）</div>
                    {(memoryInsights?.top_queries || []).slice(0, 5).map((q) => (
                      <div key={q.query} className="proposal-meta">
                        <span>{q.query}</span>
                        <span>
                          {q.hit_calls}/{q.calls}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
                {proposalError ? <div className="status err">{proposalError}</div> : null}
                {!proposalLoading && proposals.length === 0 ? <div className="history-hint">暂无记录。</div> : null}
                {proposals.length > 0 && (
                  <div className="proposal-list">
                    {proposals.map((p) => (
                      <div key={p.proposal_id} className="proposal-item">
                        <div className="proposal-title">
                          {p.title || 'Memory Update'} <span className="muted">[{p.target || 'MEMORY'}]</span>
                        </div>
                        <div className="proposal-meta">
                          <span>{p.created_at || '-'}</span>
                          <span>{p.source || 'manual'}</span>
                          <span className={`memory-status-chip ${String(p.status || '').toLowerCase() || 'unknown'}`}>
                            {String(p.status || '').toLowerCase() === 'applied'
                              ? '已写入'
                              : String(p.status || '').toLowerCase() === 'rejected'
                                ? '已拦截'
                                : '待处理'}
                          </span>
                        </div>
                        <div className="proposal-content">{p.content || ''}</div>
                        <div className="proposal-meta">
                          <span>{p.proposal_id}</span>
                          <span>{p.applied_at || p.rejected_at || '-'}</span>
                        </div>
                        {p.reject_reason ? <div className="muted">原因：{p.reject_reason}</div> : null}
                      </div>
                    ))}
                  </div>
                )}
              </section>
            )}
          </aside>
        )}
      </div>
    </div>
  )
}
