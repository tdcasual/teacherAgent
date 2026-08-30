import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { StudentAssignmentHistoryItem } from '../../appTypes'
import StudentAssignmentHistoryPage from './StudentAssignmentHistoryPage'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const items: StudentAssignmentHistoryItem[] = [
  {
    assignment_id: 'HW_DONE',
    teacher_id: 't_zhang',
    subject_id: 'physics',
    title: '已交力学',
    due_at: '2026-08-20T23:59:59',
    visibility_status: 'published',
    submitted: true,
    official_score: 12,
    archived_at: null,
  },
  {
    assignment_id: 'HW_OPEN',
    teacher_id: 't_zhang',
    subject_id: 'physics',
    title: '未交力学',
    due_at: '2026-08-29T23:59:59',
    visibility_status: 'published',
    submitted: false,
    official_score: null,
    archived_at: null,
  },
  {
    assignment_id: 'HW_ARCHIVED',
    teacher_id: 't_zhang',
    subject_id: 'math',
    title: '归档未交',
    due_at: '',
    visibility_status: 'archived',
    submitted: false,
    official_score: null,
    archived_at: '2026-08-25T00:00:00',
  },
]

describe('StudentAssignmentHistoryPage', () => {
  it('lists assignment history and shows official scores for submitted work', () => {
    render(
      <StudentAssignmentHistoryPage
        items={items}
        loading={false}
        error=""
        onBack={() => undefined}
        onSubmit={() => undefined}
        onOpenAssignment={() => undefined}
      />,
    )

    expect(screen.getByTestId('student-assignment-history-page')).toBeTruthy()
    expect(screen.getByText('作业记录')).toBeTruthy()
    expect(screen.getByText('已交力学')).toBeTruthy()
    expect(screen.getByText('官方分 12')).toBeTruthy()
    expect(screen.getByText('未交力学')).toBeTruthy()
    expect(screen.getByText('归档未交')).toBeTruthy()
  })

  it('lets published unsubmitted work open the submit panel, not session history', () => {
    const onSubmit = vi.fn()
    const onOpenAssignment = vi.fn()
    const onBack = vi.fn()
    render(
      <StudentAssignmentHistoryPage
        items={items}
        loading={false}
        error=""
        onBack={onBack}
        onSubmit={onSubmit}
        onOpenAssignment={onOpenAssignment}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: '补交 未交力学' }))
    expect(onSubmit).toHaveBeenCalledWith('HW_OPEN')
    expect(onOpenAssignment).not.toHaveBeenCalled()
    expect(onBack).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: '补交 归档未交' })).toBeNull()
  })
})
