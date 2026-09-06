import { describe, expect, it } from 'vitest'

import type { PendingChatJob, TodayAssignmentItem, VerifiedStudent } from '../../appTypes'
import { buildStudentTodayHomeViewModel } from './studentTodayHomeState'

type HomeInput = Parameters<typeof buildStudentTodayHomeViewModel>[0]

const verifiedStudent: VerifiedStudent = {
  student_id: 'S001',
  student_name: '测试学生',
  class_name: '高二1班',
}

const todayAssignments: TodayAssignmentItem[] = [
  {
    assignment_id: 'A001',
    teacher_id: 't_zhang',
    subject_id: 'physics',
    title: '牛顿第二定律练习',
    due_at: '2026-03-14T23:59:59',
    progress: {
      submitted: false,
      overdue: false,
      official_score: null,
      process_archive_status: 'none',
    },
  },
]

const pendingChatJob: PendingChatJob = {
  job_id: 'job-1',
  request_id: 'req-1',
  placeholder_id: 'placeholder-1',
  user_text: '开始今天作业',
  session_id: 'sess-1',
  created_at: Date.now(),
}

const buildInput = (overrides: Partial<HomeInput> = {}): HomeInput => ({
  verifiedStudent,
  assignmentLoading: false,
  assignmentError: '',
  todayAssignments,
  activeSessionId: '',
  messages: [],
  pendingChatJob: null,
  onOpenExecutionLabel: '继续任务',
  ...overrides,
})

describe('buildStudentTodayHomeViewModel', () => {
  it('blocks the main task flow until the student is verified', () => {
    const viewModel = buildStudentTodayHomeViewModel(
      buildInput({
        verifiedStudent: null,
        todayAssignments: [],
      }),
    )

    expect(viewModel.status).toBe('pending_generation')
    expect(viewModel.title).toBe('老师尚未布置')
    expect(viewModel.primaryActionLabel).toBe('先完成身份验证')
    expect(viewModel.primaryActionDisabled).toBe(true)
  })

  it('returns generating while today assignment is still loading', () => {
    const viewModel = buildStudentTodayHomeViewModel(
      buildInput({
        assignmentLoading: true,
      }),
    )

    expect(viewModel.status).toBe('generating')
    expect(viewModel.title).toBe('正在加载今天的任务')
    expect(viewModel.primaryActionLabel).toBe('稍后查看')
    expect(viewModel.primaryActionDisabled).toBe(true)
  })

  it('returns empty copy when no assignment is ready yet', () => {
    const viewModel = buildStudentTodayHomeViewModel(
      buildInput({
        todayAssignments: [],
      }),
    )

    expect(viewModel.status).toBe('empty')
    expect(viewModel.title).toBe('老师尚未布置')
    expect(viewModel.primaryActionLabel).toBe('老师尚未布置')
    expect(viewModel.primaryActionDisabled).toBe(true)
  })

  it('returns ready when the assignment exists but the student has not started', () => {
    const viewModel = buildStudentTodayHomeViewModel(buildInput())

    expect(viewModel.status).toBe('ready')
    expect(viewModel.primaryActionLabel).toBe('进入任务')
    expect(viewModel.items).toHaveLength(1)
    expect(viewModel.items[0].submitted).toBe(false)
    expect(viewModel.progressSteps.map((step) => step.label)).toEqual(['已准备', '待开始', '待提交'])
  })

  it('returns in_progress when there is a pending chat job', () => {
    const viewModel = buildStudentTodayHomeViewModel(
      buildInput({
        activeSessionId: 'sess-1',
        pendingChatJob,
      }),
    )

    expect(viewModel.status).toBe('in_progress')
    expect(viewModel.title).toBe('继续今日任务')
    expect(viewModel.primaryActionLabel).toBe('继续任务')
    expect(viewModel.progressSteps.map((step) => step.label)).toEqual(['已准备', '进行中', '待提交'])
  })

  it('returns in_progress when the active session already contains user work', () => {
    const viewModel = buildStudentTodayHomeViewModel(
      buildInput({
        activeSessionId: 'sess-1',
        messages: [
          { id: 'assistant-1', role: 'assistant', content: '请开始答题', time: '09:00' },
          { id: 'user-1', role: 'user', content: '这是我的第一题答案', time: '09:01' },
        ],
      }),
    )

    expect(viewModel.status).toBe('in_progress')
    expect(viewModel.primaryActionLabel).toBe('继续任务')
  })

  it('uses progress.submitted instead of recent chat completion', () => {
    const viewModel = buildStudentTodayHomeViewModel(
      buildInput({
        todayAssignments: [
          {
            ...todayAssignments[0],
            progress: { ...todayAssignments[0].progress, submitted: true },
          },
        ],
      }),
    )

    expect(viewModel.status).toBe('submitted')
    expect(viewModel.items[0].submitted).toBe(true)
    expect(viewModel.primaryActionLabel).toBe('查看作业记录')
    expect(viewModel.progressSteps.map((step) => step.label)).toEqual(['已准备', '已完成', '已提交'])
  })
})
