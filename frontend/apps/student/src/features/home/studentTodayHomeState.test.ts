import { describe, expect, it } from 'vitest'

import type { AssignmentDetail, PendingChatJob, RecentCompletedReply, VerifiedStudent } from '../../appTypes'
import { buildStudentTodayHomeViewModel } from './studentTodayHomeState'

type HomeInput = Parameters<typeof buildStudentTodayHomeViewModel>[0]

const verifiedStudent: VerifiedStudent = {
  student_id: 'S001',
  student_name: '测试学生',
  class_name: '高二1班',
}

const todayAssignment: AssignmentDetail = {
  assignment_id: 'A001',
  date: '2026-03-14',
  question_count: 8,
  meta: { target_kp: ['力学'] },
  delivery: {
    mode: 'files',
    files: [
      { name: '练习题.pdf', url: 'http://localhost:8000/files/assignment.pdf' },
      { name: '讲义.pdf', url: 'http://localhost:8000/files/note.pdf' },
    ],
  },
}

const pendingChatJob: PendingChatJob = {
  job_id: 'job-1',
  request_id: 'req-1',
  placeholder_id: 'placeholder-1',
  user_text: '开始今天作业',
  session_id: 'A001',
  created_at: Date.now(),
}

const completedReply: RecentCompletedReply = {
  session_id: 'A001',
  user_text: '我做完了',
  reply_text: '已收到本次提交',
  completed_at: Date.now(),
}

const buildInput = (overrides: Partial<HomeInput> = {}): HomeInput => ({
  verifiedStudent,
  assignmentLoading: false,
  assignmentError: '',
  todayAssignment,
  activeSessionId: '',
  messages: [],
  pendingChatJob: null,
  recentCompletedReplies: [],
  onOpenExecutionLabel: '继续任务',
  ...overrides,
})

describe('buildStudentTodayHomeViewModel', () => {
  it('blocks the main task flow until the student is verified', () => {
    const viewModel = buildStudentTodayHomeViewModel(
      buildInput({
        verifiedStudent: null,
        todayAssignment: null,
      }),
    )

    expect(viewModel.status).toBe('pending_generation')
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
    expect(viewModel.title).toBe('正在准备今天的任务')
    expect(viewModel.primaryActionLabel).toBe('稍后查看')
    expect(viewModel.primaryActionDisabled).toBe(true)
  })

  it('returns pending_generation when no assignment is ready yet', () => {
    const viewModel = buildStudentTodayHomeViewModel(
      buildInput({
        todayAssignment: null,
      }),
    )

    expect(viewModel.status).toBe('pending_generation')
    expect(viewModel.title).toBe('今日任务尚未生成')
    expect(viewModel.primaryActionLabel).toBe('生成任务')
  })

  it('returns ready when the assignment exists but the student has not started', () => {
    const viewModel = buildStudentTodayHomeViewModel(buildInput())

    expect(viewModel.status).toBe('ready')
    expect(viewModel.primaryActionLabel).toBe('进入任务')
    expect(viewModel.progressSteps.map((step) => step.label)).toEqual(['已准备', '待开始', '待提交'])
    expect(viewModel.materials).toHaveLength(2)
  })

  it('returns in_progress when there is a pending chat job', () => {
    const viewModel = buildStudentTodayHomeViewModel(
      buildInput({
        activeSessionId: 'A001',
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
        activeSessionId: 'A001',
        messages: [
          { id: 'assistant-1', role: 'assistant', content: '请开始答题', time: '09:00' },
          { id: 'user-1', role: 'user', content: '这是我的第一题答案', time: '09:01' },
        ],
      }),
    )

    expect(viewModel.status).toBe('in_progress')
    expect(viewModel.primaryActionLabel).toBe('继续任务')
  })

  it('returns submitted when a recent completed reply exists for today', () => {
    const viewModel = buildStudentTodayHomeViewModel(
      buildInput({
        activeSessionId: 'A001',
        recentCompletedReplies: [completedReply],
      }),
    )

    expect(viewModel.status).toBe('submitted')
    expect(viewModel.title).toBe('今天的任务已提交')
    expect(viewModel.primaryActionLabel).toBe('查看提交')
    expect(viewModel.progressSteps.map((step) => step.label)).toEqual(['已准备', '已完成', '已提交'])
  })
})
