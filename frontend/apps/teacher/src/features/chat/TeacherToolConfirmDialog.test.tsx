import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { TeacherToolConfirmDialog } from './TeacherToolConfirmDialog'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('TeacherToolConfirmDialog', () => {
  it('wires confirm-for-tool onto ConfirmDialog', () => {
    const onConfirm = vi.fn()
    const onCancel = vi.fn()
    render(
      <TeacherToolConfirmDialog
        toolConfirm={{ confirm_id: 'abc', tool: 'student.profile.update', preview: '{"student_id":"S1"}' }}
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    )
    expect(screen.getByRole('dialog')).toBeTruthy()
    expect(screen.getByText('确认执行写操作？')).toBeTruthy()
    expect(screen.getByText(/student.profile.update/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '确认执行' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: '取消' }))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })
})
