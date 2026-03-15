import type {
  AssignmentDetail,
  Message,
  PendingChatJob,
  RecentCompletedReply,
  StudentTodayHomeMaterial,
  StudentTodayHomeStep,
  StudentTodayHomeViewModel,
  VerifiedStudent,
} from '../../appTypes'

type BuildStudentTodayHomeViewModelInput = {
  verifiedStudent: VerifiedStudent | null
  assignmentLoading: boolean
  assignmentError: string
  todayAssignment: AssignmentDetail | null
  activeSessionId: string
  messages: Message[]
  pendingChatJob: PendingChatJob | null
  recentCompletedReplies: RecentCompletedReply[]
  onOpenExecutionLabel?: string
}

const toMaterials = (assignment: AssignmentDetail | null): StudentTodayHomeMaterial[] =>
  Array.isArray(assignment?.delivery?.files)
    ? assignment!.delivery!.files!.map((item) => ({
      label: String(item?.name || '学习材料'),
      url: typeof item?.url === 'string' ? item.url : undefined,
    }))
    : []

const buildProgressSteps = (status: StudentTodayHomeViewModel['status']): StudentTodayHomeStep[] => {
  if (status === 'pending_generation') {
    return [
      { label: '准备任务', tone: 'active' },
      { label: '开始练习', tone: 'neutral' },
      { label: '提交结果', tone: 'neutral' },
    ]
  }
  if (status === 'generating') {
    return [
      { label: '准备任务', tone: 'active' },
      { label: '开始练习', tone: 'neutral' },
      { label: '提交结果', tone: 'neutral' },
    ]
  }
  if (status === 'ready') {
    return [
      { label: '任务已就绪', tone: 'success' },
      { label: '开始练习', tone: 'active' },
      { label: '提交结果', tone: 'neutral' },
    ]
  }
  if (status === 'submitted') {
    return [
      { label: '任务已就绪', tone: 'success' },
      { label: '完成练习', tone: 'success' },
      { label: '已提交', tone: 'success' },
    ]
  }
  return [
    { label: '任务已就绪', tone: 'success' },
    { label: '继续练习', tone: 'active' },
    { label: '等待提交', tone: 'neutral' },
  ]
}

const estimateMinutes = (assignment: AssignmentDetail | null): number | null => {
  const questionCount = Number(assignment?.question_count || 0)
  if (!Number.isFinite(questionCount) || questionCount <= 0) return null
  return Math.max(15, questionCount * 3)
}

const dueLabelOf = (assignment: AssignmentDetail | null): string => {
  const date = String(assignment?.date || '').trim()
  return date ? `${date} 截止` : '今天完成'
}

const includesUserWork = (messages: Message[]): boolean => messages.some((item) => item.role === 'user' && item.content.trim())

const matchesTodaySession = (
  activeSessionId: string,
  assignment: AssignmentDetail | null,
  reply: RecentCompletedReply,
): boolean => {
  const activeId = activeSessionId.trim()
  const assignmentId = String(assignment?.assignment_id || '').trim()
  return Boolean(reply.session_id && (reply.session_id === activeId || reply.session_id === assignmentId))
}

export function buildStudentTodayHomeViewModel(input: BuildStudentTodayHomeViewModelInput): StudentTodayHomeViewModel {
  const {
    verifiedStudent,
    assignmentLoading,
    todayAssignment,
    activeSessionId,
    messages,
    pendingChatJob,
    recentCompletedReplies,
    onOpenExecutionLabel = '继续完成',
  } = input

  const materials = toMaterials(todayAssignment)
  const estimatedMinutesValue = estimateMinutes(todayAssignment)
  const dueLabel = dueLabelOf(todayAssignment)
  const submitted = recentCompletedReplies.some((item) => matchesTodaySession(activeSessionId, todayAssignment, item))
  const inProgress = Boolean(pendingChatJob?.job_id) || includesUserWork(messages)

  if (!verifiedStudent) {
    return {
      status: 'pending_generation',
      title: '今日任务尚未生成',
      summary: '先完成身份验证，系统会为你准备今天的练习内容。',
      primaryActionLabel: '先完成身份验证',
      primaryActionDisabled: true,
      statusLabel: '等待验证',
      estimatedMinutes: null,
      dueLabel: '完成验证后开始',
      materials: [],
      progressSteps: buildProgressSteps('pending_generation'),
    }
  }

  if (assignmentLoading) {
    return {
      status: 'generating',
      title: '正在准备今天的任务',
      summary: '系统正在整理题目、要求和提交入口，请稍后查看。',
      primaryActionLabel: '稍后查看',
      primaryActionDisabled: true,
      statusLabel: '生成中',
      estimatedMinutes: null,
      dueLabel: '准备完成后可开始',
      materials,
      progressSteps: buildProgressSteps('generating'),
    }
  }

  if (submitted) {
    return {
      status: 'submitted',
      title: '今天的任务已提交',
      summary: '你已完成本次任务提交，现在可以查看结果或等待老师反馈。',
      primaryActionLabel: '查看本次提交',
      primaryActionDisabled: false,
      statusLabel: '已提交',
      estimatedMinutes: estimatedMinutesValue,
      dueLabel,
      materials,
      progressSteps: buildProgressSteps('submitted'),
    }
  }

  if (!todayAssignment) {
    return {
      status: 'pending_generation',
      title: '今日任务尚未生成',
      summary: '系统会根据今天安排准备练习内容，你可以立即生成今日任务。',
      primaryActionLabel: '生成今日任务',
      primaryActionDisabled: false,
      statusLabel: '待生成',
      estimatedMinutes: null,
      dueLabel: '生成后开始',
      materials: [],
      progressSteps: buildProgressSteps('pending_generation'),
    }
  }

  if (inProgress) {
    return {
      status: 'in_progress',
      title: '继续今日任务',
      summary: '你已经开始今天的练习，可以继续完成当前任务。',
      primaryActionLabel: onOpenExecutionLabel,
      primaryActionDisabled: false,
      statusLabel: '进行中',
      estimatedMinutes: estimatedMinutesValue,
      dueLabel,
      materials,
      progressSteps: buildProgressSteps('in_progress'),
    }
  }

  return {
    status: 'ready',
    title: String(todayAssignment.assignment_id || '今日任务'),
    summary: '今天的练习已经准备好，先开始主任务，再处理补充内容。',
    primaryActionLabel: '开始今日任务',
    primaryActionDisabled: false,
    statusLabel: '未开始',
    estimatedMinutes: estimatedMinutesValue,
    dueLabel,
    materials,
    progressSteps: buildProgressSteps('ready'),
  }
}

export type { BuildStudentTodayHomeViewModelInput }
