import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import TeacherWorkbench from './TeacherWorkbench'
import type { TeacherWorkbenchViewModel } from './teacherWorkbenchViewModel'

vi.mock('./tabs/SkillsTab', () => ({
  default: () => <div>skills-tab-content</div>,
}))

vi.mock('./tabs/WorkflowTab', () => ({
  default: () => <div>workflow-tab-content</div>,
}))

vi.mock('./tabs/MemoryTab', () => ({
  default: () => <div>memory-tab-content</div>,
}))

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const buildViewModel = (): TeacherWorkbenchViewModel => {
  const setSkillsOpen = vi.fn()
  const setWorkbenchTab = vi.fn()
  const refreshWorkflowWorkbench = vi.fn()
  const scrollToWorkflowSection = vi.fn()

  return {
    skillsOpen: true,
    setSkillsOpen,
    workbenchTab: 'skills',
    setWorkbenchTab,
    fetchSkills: async () => undefined,
    refreshMemoryProposals: async () => undefined,
    refreshMemoryInsights: async () => undefined,
    refreshStudentMemoryProposals: async () => undefined,
    refreshStudentMemoryInsights: async () => undefined,
    refreshWorkflowWorkbench,
    skillsLoading: false,
    proposalLoading: false,
    studentProposalLoading: false,
    progressLoading: false,
    uploading: false,
    examUploading: false,
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
    uploadJobInfo: null,
    uploadAssignmentId: 'HW-20260314',
    examJobInfo: null,
    examId: '',
    progressData: null,
    progressAssignmentId: '',
    scrollToWorkflowSection,
    fetchAssignmentProgress: async () => undefined,
    formatUploadJobSummary: () => '状态：解析完成（待确认） · 作业编号：HW-20260314',
    formatExamJobSummary: () => '状态：未开始',
    formatProgressSummary: () => '暂无完成情况',
  } as unknown as TeacherWorkbenchViewModel
}

describe('TeacherWorkbench header', () => {
  it('shows current workflow status and routes the primary CTA into the workflow tab', () => {
    const viewModel = buildViewModel()

    render(<TeacherWorkbench viewModel={viewModel} />)

    expect(screen.getByText('教学编辑台')).toBeTruthy()
    expect(screen.getByText('把主动作留在顶部任务条，这里只保留流程摘要与入口。')).toBeTruthy()
    expect(screen.getByText('流程摘要')).toBeTruthy()
    expect(screen.getByText('待审核')).toBeTruthy()
    expect(screen.getByText('下一步：继续审核草稿并确认创建作业')).toBeTruthy()
    expect(screen.getByText('状态：解析完成（待确认） · 作业编号：HW-20260314')).toBeTruthy()
    expect(screen.getByRole('button', { name: '刷新' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '收起' })).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: '查看草稿' }))

    expect(viewModel.setWorkbenchTab).toHaveBeenCalledWith('workflow')
    expect(viewModel.scrollToWorkflowSection).toHaveBeenCalledWith('workflow-assignment-draft-section')
  })

  it('stacks the summary CTA for narrow workbench widths', () => {
    const viewModel = buildViewModel()

    render(<TeacherWorkbench viewModel={viewModel} />)

    const primaryAction = screen.getByRole('button', { name: '查看草稿' })
    const summaryLayout = primaryAction.parentElement

    expect(summaryLayout).toBeTruthy()
    expect((summaryLayout as HTMLElement).className).toContain('grid')
    expect((summaryLayout as HTMLElement).className).not.toContain('xl:grid-cols-[minmax(0,1fr)_auto]')
    expect(primaryAction.className).toContain('w-full')
    expect(primaryAction.className).not.toContain('xl:w-auto')
  })

  it('switches to a compact status header when the workflow tab is already active', () => {
    const viewModel = buildViewModel()
    viewModel.workbenchTab = 'workflow'

    render(<TeacherWorkbench viewModel={viewModel} />)

    expect(screen.getByText('工作流已展开')).toBeTruthy()
    expect(screen.getByText('下一步：继续审核草稿并确认创建作业 · 下方继续处理。')).toBeTruthy()
    expect(screen.queryByRole('button', { name: '查看草稿' })).toBeNull()
  })
})
