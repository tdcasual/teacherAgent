import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import AssignmentProgressSection from './AssignmentProgressSection'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const baseProps = {
  progressPanelCollapsed: false,
  setProgressPanelCollapsed: vi.fn(),
  formatProgressSummary: () => 'summary',
  progressAssignmentId: 'HW-1',
  setProgressAssignmentId: vi.fn(),
  progressOnlyIncomplete: false,
  setProgressOnlyIncomplete: vi.fn(),
  progressLoading: false,
  fetchAssignmentProgress: vi.fn(async () => undefined),
  progressError: '',
}

describe('AssignmentProgressSection', () => {
  it('renders result and process columns and colors by submitted not discussion', () => {
    render(
      <AssignmentProgressSection
        {...baseProps}
        progressData={{
          ok: true,
          assignment_id: 'HW-1',
          counts: { expected: 2, submitted: 1, completed: 1, overdue: 1, discussion_pass: 1 },
          students: [
            {
              student_id: 'S1',
              student_name: '张三',
              class_name: '高二1班',
              complete: true,
              overdue: false,
              discussion: { pass: false },
              submission: { attempts: 2, best: { score_earned: 8 } },
              official_score: 11,
              result: { attempts: 2, official_score: 11, overdue: false, submitted: true },
              process: { status: 'none', stuck_points: [], has_memory_proposal: false },
            },
            {
              student_id: 'S2',
              student_name: '李四',
              complete: false,
              overdue: true,
              discussion: { pass: true },
              submission: { attempts: 0 },
              official_score: null,
              result: { attempts: 0, official_score: null, overdue: true, submitted: false },
              process: { status: 'pending', stuck_points: [{ summary: '把 v 与 a 混用' }], has_memory_proposal: false },
            },
          ],
        }}
      />,
    )

    expect(screen.getByText('结果')).toBeTruthy()
    expect(screen.getByText('过程')).toBeTruthy()
    expect(screen.getByText(/提交2次/)).toBeTruthy()
    expect(screen.getByText(/官方分11/)).toBeTruthy()
    expect(screen.getByText(/过程：无/)).toBeTruthy()
    expect(screen.getByText(/过程：生成中/)).toBeTruthy()
    expect(screen.queryByText('讨论通过')).toBeNull()
    expect(screen.queryByText('讨论未完成')).toBeNull()

    const submittedRow = screen.getByTestId('progress-row-S1')
    const discussionOnlyRow = screen.getByTestId('progress-row-S2')
    expect(submittedRow.className).toContain('bg-[#f3fbfa]')
    expect(discussionOnlyRow.className).toContain('bg-[#fff8f8]')
  })

  it('saves teacher grade override comment and adopted excerpts', () => {
    const saveStudentGrade = vi.fn(async () => undefined)
    render(
      <AssignmentProgressSection
        {...baseProps}
        saveStudentGrade={saveStudentGrade}
        progressData={{
          ok: true,
          assignment_id: 'HW-1',
          students: [
            {
              student_id: 'S1',
              complete: true,
              submission: { attempts: 1, best: { score_earned: 8 } },
              official_score: 8,
              result: { attempts: 1, official_score: 8, overdue: false, submitted: true },
              process: { status: 'none' },
            },
          ],
        }}
      />,
    )

    fireEvent.change(screen.getByLabelText('覆盖分数'), { target: { value: '12' } })
    fireEvent.change(screen.getByLabelText('评语'), { target: { value: '步骤完整' } })
    fireEvent.change(screen.getByLabelText('采纳陪练摘录'), { target: { value: '先写单位' } })
    fireEvent.click(screen.getByRole('button', { name: '保存成绩' }))

    expect(saveStudentGrade).toHaveBeenCalledWith('S1', {
      override_score: 12,
      comment: '步骤完整',
      adopted_coach_excerpts: [{ text: '先写单位' }],
    })
  })

  it('restores auto score by posting override_score null', () => {
    const saveStudentGrade = vi.fn(async () => undefined)
    render(
      <AssignmentProgressSection
        {...baseProps}
        saveStudentGrade={saveStudentGrade}
        progressData={{
          ok: true,
          assignment_id: 'HW-1',
          students: [
            {
              student_id: 'S1',
              complete: true,
              submission: { attempts: 1, best: { score_earned: 8 } },
              official_score: 12,
              teacher_grade: { override_score_earned: 12, comment: '覆盖' },
              result: { attempts: 1, official_score: 12, overdue: false, submitted: true },
              process: { status: 'none' },
            },
          ],
        }}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '恢复自动分' }))
    expect(saveStudentGrade).toHaveBeenCalledWith('S1', { override_score: null })
  })
})
