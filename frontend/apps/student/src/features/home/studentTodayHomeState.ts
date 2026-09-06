import type {
  Message,
  PendingChatJob,
  StudentTodayHomeItem,
  StudentTodayHomeMaterial,
  StudentTodayHomeStep,
  StudentTodayHomeViewModel,
  TodayAssignmentItem,
  VerifiedStudent,
} from '../../appTypes'

type BuildStudentTodayHomeViewModelInput = {
  verifiedStudent: VerifiedStudent | null
  assignmentLoading: boolean
  assignmentError: string
  todayAssignments: TodayAssignmentItem[]
  activeSessionId: string
  messages: Message[]
  pendingChatJob: PendingChatJob | null
  onOpenExecutionLabel?: string
}

const buildProgressSteps = (status: StudentTodayHomeViewModel['status']): StudentTodayHomeStep[] => {
  if (status === 'pending_generation') {
    return [
      { label: '准备中', tone: 'active' },
      { label: '待开始', tone: 'neutral' },
      { label: '待提交', tone: 'neutral' },
    ]
  }
  if (status === 'generating') {
    return [
      { label: '准备中', tone: 'active' },
      { label: '待开始', tone: 'neutral' },
      { label: '待提交', tone: 'neutral' },
    ]
  }
  if (status === 'empty') {
    return [
      { label: '未布置', tone: 'neutral' },
      { label: '待开始', tone: 'neutral' },
      { label: '待提交', tone: 'neutral' },
    ]
  }
  if (status === 'ready') {
    return [
      { label: '已准备', tone: 'success' },
      { label: '待开始', tone: 'active' },
      { label: '待提交', tone: 'neutral' },
    ]
  }
  if (status === 'submitted') {
    return [
      { label: '已准备', tone: 'success' },
      { label: '已完成', tone: 'success' },
      { label: '已提交', tone: 'success' },
    ]
  }
  return [
    { label: '已准备', tone: 'success' },
    { label: '进行中', tone: 'active' },
    { label: '待提交', tone: 'neutral' },
  ]
}

const dueLabelOf = (item: TodayAssignmentItem): string => {
  const due = String(item.due_at || '').trim()
  if (item.progress.overdue) return due ? `${due} 已逾期` : '已逾期'
  return due ? `${due} 截止` : '无截止时间'
}

const toHomeItems = (assignments: TodayAssignmentItem[]): StudentTodayHomeItem[] =>
  assignments.map((item) => ({
    assignment_id: item.assignment_id,
    teacher_id: item.teacher_id,
    subject_id: item.subject_id,
    title: item.title || item.assignment_id,
    dueLabel: dueLabelOf(item),
    overdue: Boolean(item.progress.overdue),
    submitted: Boolean(item.progress.submitted),
  }))

const includesUserWork = (messages: Message[]): boolean => messages.some((item) => item.role === 'user' && item.content.trim())

export function buildStudentTodayHomeViewModel(input: BuildStudentTodayHomeViewModelInput): StudentTodayHomeViewModel {
  const {
    verifiedStudent,
    assignmentLoading,
    todayAssignments,
    messages,
    pendingChatJob,
    onOpenExecutionLabel = '继续任务',
  } = input

  const items = toHomeItems(todayAssignments)
  const inProgress = Boolean(pendingChatJob?.job_id) || includesUserWork(messages)
  const allSubmitted = items.length > 0 && items.every((item) => item.submitted)

  if (!verifiedStudent) {
    return {
      status: 'pending_generation',
      title: '老师尚未布置',
      summary: '先完成身份验证，再查看今天各科老师布置的作业。',
      primaryActionLabel: '先完成身份验证',
      primaryActionDisabled: true,
      statusLabel: '等待验证',
      estimatedMinutes: null,
      dueLabel: '完成验证后开始',
      materials: [],
      progressSteps: buildProgressSteps('pending_generation'),
      items: [],
    }
  }

  if (assignmentLoading) {
    return {
      status: 'generating',
      title: '正在加载今天的任务',
      summary: '正在读取各科作业列表，请稍后查看。',
      primaryActionLabel: '稍后查看',
      primaryActionDisabled: true,
      statusLabel: '加载中',
      estimatedMinutes: null,
      dueLabel: '加载完成后可开始',
      materials: [],
      progressSteps: buildProgressSteps('generating'),
      items,
    }
  }

  if (items.length === 0) {
    return {
      status: 'empty',
      title: '老师尚未布置',
      summary: '今天还没有需要处理的作业。可以先自由提问，或查看作业记录。',
      primaryActionLabel: '老师尚未布置',
      primaryActionDisabled: true,
      statusLabel: '未布置',
      estimatedMinutes: null,
      dueLabel: '',
      materials: [],
      progressSteps: buildProgressSteps('empty'),
      items: [],
    }
  }

  if (allSubmitted) {
    return {
      status: 'submitted',
      title: '今天的任务已提交',
      summary: '已提交的作业会进入作业记录，不再占用今日列表。',
      primaryActionLabel: '查看作业记录',
      primaryActionDisabled: false,
      statusLabel: '已提交',
      estimatedMinutes: null,
      dueLabel: items[0]?.dueLabel || '',
      materials: [] as StudentTodayHomeMaterial[],
      progressSteps: buildProgressSteps('submitted'),
      items,
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
      estimatedMinutes: null,
      dueLabel: items[0]?.dueLabel || '',
      materials: [],
      progressSteps: buildProgressSteps('in_progress'),
      items,
    }
  }

  return {
    status: 'ready',
    title: '今日作业',
    summary: '按学科查看老师布置的作业，进入任务后可以开始陪练。',
    primaryActionLabel: '进入任务',
    primaryActionDisabled: false,
    statusLabel: '未开始',
    estimatedMinutes: null,
    dueLabel: items[0]?.dueLabel || '',
    materials: [],
    progressSteps: buildProgressSteps('ready'),
    items,
  }
}

export type { BuildStudentTodayHomeViewModelInput }
