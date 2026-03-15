import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { StudentTodayHomeViewModel } from '../../appTypes'
import StudentTodayHome from './StudentTodayHome'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const buildViewModel = (overrides: Partial<StudentTodayHomeViewModel> = {}): StudentTodayHomeViewModel => ({
  status: 'ready',
  title: '牛顿第二定律练习',
  summary: '今天先完成本次物理练习，再查看补充讲义。',
  primaryActionLabel: '进入任务',
  primaryActionDisabled: false,
  statusLabel: '未开始',
  estimatedMinutes: 24,
  dueLabel: '2026-03-14 截止',
  materials: [
    { label: '练习题.pdf', url: '/files/assignment.pdf' },
    { label: '讲义.pdf', url: '/files/note.pdf' },
  ],
  progressSteps: [
    { label: '已准备', tone: 'success' },
    { label: '待开始', tone: 'active' },
    { label: '待提交', tone: 'neutral' },
  ],
  ...overrides,
})

describe('StudentTodayHome', () => {
  it('renders the home sections around a single primary task card', () => {
    render(
      <StudentTodayHome
        dateLabel="3月14日 周六"
        viewModel={buildViewModel()}
        onPrimaryAction={() => undefined}
        onOpenHistory={() => undefined}
        onOpenFreeChat={() => undefined}
      />,
    )

    expect(screen.getByText('3月14日 周六')).toBeTruthy()
    expect(screen.getByText('牛顿第二定律练习')).toBeTruthy()
    expect(screen.getByText('练习题.pdf')).toBeTruthy()
    expect(screen.getByText('已准备')).toBeTruthy()
    expect(screen.getByRole('button', { name: '进入任务' })).toBeTruthy()
    expect(screen.getByTestId('student-today-primary-action')).toBeTruthy()
    expect(screen.queryByText('今日任务')).toBeNull()
    expect(screen.queryByText('历史与补充')).toBeNull()
  })

  it('keeps the primary stage distinct from supplementary content', () => {
    render(
      <StudentTodayHome
        dateLabel="3月14日 周六"
        viewModel={buildViewModel()}
        onPrimaryAction={() => undefined}
        onOpenHistory={() => undefined}
        onOpenFreeChat={() => undefined}
      />,
    )

    const primaryStage = screen.getByTestId('student-today-primary-stage')
    const secondaryStage = screen.getByTestId('student-today-secondary-stage')
    const materialsStage = screen.getByTestId('student-home-materials-stage')
    const progressStage = screen.getByTestId('student-home-progress-stage')
    const historyStage = screen.getByTestId('student-home-history-stage')

    expect(primaryStage.textContent).toContain('牛顿第二定律练习')
    expect(primaryStage.textContent).toContain('进入任务')
    expect(primaryStage.textContent).not.toContain('今日任务')
    expect(primaryStage.textContent).not.toContain('开始练习')
    expect(primaryStage.textContent).not.toContain('今日主线')
    expect(primaryStage.textContent).not.toContain('TODAY FIRST')
    expect(primaryStage.textContent).not.toContain('先从这里开始')
    expect(secondaryStage.textContent).toContain('练习题.pdf')
    expect(secondaryStage.textContent).toContain('已准备')
    expect(secondaryStage.textContent).toContain('历史任务')
    expect(secondaryStage.textContent).not.toContain('辅助区')
    expect(secondaryStage.textContent).not.toContain('历史与补充')
    expect(materialsStage.getAttribute('data-home-tier')).toBe('supporting')
    expect(progressStage.getAttribute('data-home-tier')).toBe('supporting')
    expect(historyStage.getAttribute('data-home-tier')).toBe('supporting')
    expect(historyStage.getAttribute('data-home-style')).toBe('inline-links')
  })

  it('shows generate copy for pending_generation', () => {
    render(
      <StudentTodayHome
        dateLabel="3月14日 周六"
        viewModel={buildViewModel({
          status: 'pending_generation',
          title: '今日任务尚未生成',
          summary: '系统会根据今天安排准备练习内容。',
          primaryActionLabel: '生成任务',
          estimatedMinutes: null,
          dueLabel: '生成后开始',
          materials: [],
          progressSteps: [
            { label: '准备中', tone: 'active' },
            { label: '待开始', tone: 'neutral' },
            { label: '待提交', tone: 'neutral' },
          ],
        })}
        onPrimaryAction={() => undefined}
        onOpenHistory={() => undefined}
        onOpenFreeChat={() => undefined}
      />,
    )

    expect(screen.getByRole('button', { name: '生成任务' })).toBeTruthy()
    expect(screen.getAllByRole('button', { name: '生成任务' })).toHaveLength(1)
  })

  it('shows generating feedback without an active primary action', () => {
    render(
      <StudentTodayHome
        dateLabel="3月14日 周六"
        viewModel={buildViewModel({
          status: 'generating',
          title: '正在准备今天的任务',
          summary: '系统正在整理题目、要求和提交入口，请稍后查看。',
          primaryActionLabel: '稍后查看',
          primaryActionDisabled: true,
        })}
        onPrimaryAction={() => undefined}
        onOpenHistory={() => undefined}
        onOpenFreeChat={() => undefined}
      />,
    )

    expect(screen.getByText('正在准备今天的任务')).toBeTruthy()
    expect(screen.getByRole('button', { name: '稍后查看' }).hasAttribute('disabled')).toBe(true)
  })

  it('shows continue copy for in-progress work', () => {
    render(
      <StudentTodayHome
        dateLabel="3月14日 周六"
        viewModel={buildViewModel({
          status: 'in_progress',
          title: '继续今日任务',
          primaryActionLabel: '继续任务',
        })}
        onPrimaryAction={() => undefined}
        onOpenHistory={() => undefined}
        onOpenFreeChat={() => undefined}
      />,
    )

    expect(screen.getByRole('button', { name: '继续任务' })).toBeTruthy()
  })

  it('shows submitted copy and still keeps one primary action', () => {
    render(
      <StudentTodayHome
        dateLabel="3月14日 周六"
        viewModel={buildViewModel({
          status: 'submitted',
          title: '今天的任务已提交',
          primaryActionLabel: '查看提交',
          statusLabel: '已提交',
        })}
        onPrimaryAction={() => undefined}
        onOpenHistory={() => undefined}
        onOpenFreeChat={() => undefined}
      />,
    )

    expect(screen.getByRole('button', { name: '查看提交' })).toBeTruthy()
    expect(screen.getAllByTestId('student-today-primary-action')).toHaveLength(1)
  })

  it('wires primary and secondary actions', () => {
    const onPrimaryAction = vi.fn()
    const onOpenHistory = vi.fn()
    const onOpenFreeChat = vi.fn()

    render(
      <StudentTodayHome
        dateLabel="3月14日 周六"
        viewModel={buildViewModel()}
        onPrimaryAction={onPrimaryAction}
        onOpenHistory={onOpenHistory}
        onOpenFreeChat={onOpenFreeChat}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '进入任务' }))
    fireEvent.click(screen.getByRole('button', { name: '历史任务' }))
    fireEvent.click(screen.getByRole('button', { name: '自由提问' }))

    expect(onPrimaryAction).toHaveBeenCalledTimes(1)
    expect(onOpenHistory).toHaveBeenCalledTimes(1)
    expect(onOpenFreeChat).toHaveBeenCalledTimes(1)
  })
})
