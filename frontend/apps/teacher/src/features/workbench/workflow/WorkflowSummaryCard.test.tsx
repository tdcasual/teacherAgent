import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import WorkflowSummaryCard from './WorkflowSummaryCard'
import type { WorkflowSummaryCardProps } from '../../../types/workflow'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const baseProps = (): WorkflowSummaryCardProps => ({
  activeWorkflowIndicator: {
    label: '待审核',
    tone: 'active',
    steps: [
      { key: 'upload', label: '上传文件', state: 'done' },
      { key: 'parse', label: '解析', state: 'done' },
      { key: 'review', label: '审核草稿', state: 'active' },
      { key: 'confirm', label: '创建作业', state: 'todo' },
    ],
  },
  uploadMode: 'assignment',
  setUploadMode: () => undefined,
  uploadJobInfo: null,
  uploadAssignmentId: 'HW-20260314',
  examJobInfo: null,
  examId: '',
  progressData: null,
  progressAssignmentId: '',
  progressLoading: false,
  scrollToWorkflowSection: vi.fn(),
  refreshWorkflowWorkbench: vi.fn(),
  fetchAssignmentProgress: async () => undefined,
  formatUploadJobSummary: () => '状态：解析完成（待确认） · 作业编号：HW-20260314',
  formatExamJobSummary: () => '状态：未开始',
  formatProgressSummary: () => '暂无完成情况',
})

describe('WorkflowSummaryCard', () => {
  it('surfaces one primary action around the current assignment step', () => {
    const props = baseProps()

    render(<WorkflowSummaryCard {...props} />)

    expect(screen.queryByText('状态总览')).toBeNull()
    expect(screen.queryByText('下一步：继续审核草稿并确认创建作业')).toBeNull()
    expect(screen.queryByText('动作目标')).toBeNull()
    expect(screen.getByRole('button', { name: '查看草稿' })).toBeTruthy()
    expect(screen.queryByText('状态：解析完成（待确认） · 作业编号：HW-20260314')).toBeNull()
    expect(screen.getByRole('button', { name: '查看上传区' })).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: '查看草稿' }))

    expect(props.scrollToWorkflowSection).toHaveBeenCalledWith('workflow-assignment-draft-section')
  })

  it('lets the primary CTA take its own row in narrow sidebar layouts', () => {
    const props = baseProps()

    render(<WorkflowSummaryCard {...props} />)

    const primaryAction = screen.getByRole('button', { name: '查看草稿' })
    const summaryLayout = primaryAction.parentElement

    expect(summaryLayout).toBeTruthy()
    expect((summaryLayout as HTMLElement).className).toContain('grid')
    expect((summaryLayout as HTMLElement).className).not.toContain('xl:grid-cols-[minmax(0,1fr)_auto]')
    expect(primaryAction.className).toContain('w-full')
    expect(primaryAction.className).not.toContain('xl:w-auto')
  })
})
