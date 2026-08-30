import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { createRef } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import * as teacherAuth from '../auth/teacherAuth'
import TeacherTopbarAdminMenu from './TeacherTopbarAdminMenu'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('TeacherTopbarAdminMenu password reset scope', () => {
  it('hides reset-all for non-admin teachers', () => {
    vi.spyOn(teacherAuth, 'readTeacherAccessToken').mockReturnValue('teacher-token')
    vi.spyOn(teacherAuth, 'readTeacherAuthRole').mockReturnValue('teacher')
    vi.spyOn(teacherAuth, 'readTeacherAuthSubject').mockReturnValue({
      teacher_id: 'T001',
      teacher_name: '张老师',
    })

    render(
      <TeacherTopbarAdminMenu
        open
        panelRef={createRef<HTMLDivElement>()}
        authed
        authSubjectLabel="张老师"
        onOpenModelSettingsPanel={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByText('按学生或班级重置密码。')).toBeTruthy()
    expect(screen.queryByRole('button', { name: '全部学生' })).toBeNull()
  })

  it('shows reset-all only for admin', () => {
    vi.spyOn(teacherAuth, 'readTeacherAccessToken').mockReturnValue('admin-token')
    vi.spyOn(teacherAuth, 'readTeacherAuthRole').mockReturnValue('admin')
    vi.spyOn(teacherAuth, 'readTeacherAuthSubject').mockReturnValue({
      teacher_id: 'admin',
      teacher_name: '校长',
      role: 'admin',
    })

    render(
      <TeacherTopbarAdminMenu
        open
        panelRef={createRef<HTMLDivElement>()}
        authed
        authSubjectLabel="校长"
        onOpenModelSettingsPanel={vi.fn()}
        onClose={vi.fn()}
      />,
    )

    expect(screen.getByText('按学生、班级或全部学生重置密码。')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '全部学生' }))
    expect(screen.getByText('我确认重置全部学生密码')).toBeTruthy()
  })
})
