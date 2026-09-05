import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { createRef } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import * as teacherAuth from '../auth/teacherAuth'
import TeacherTopbarAdminMenu from './TeacherTopbarAdminMenu'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
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

  it('logs admin in via POST /auth/admin/login and stores role=admin', async () => {
    const writeSession = vi.spyOn(teacherAuth, 'writeTeacherAuthSession').mockImplementation(() => undefined)
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      expect(url).toContain('/auth/admin/login')
      expect(url).not.toContain('/auth/teacher/')
      return {
        ok: true,
        json: async () => ({
          ok: true,
          access_token: 'admin-access',
          role: 'admin',
          subject_id: 'principal_admin',
        }),
      }
    })
    vi.stubGlobal('fetch', fetchMock)
    const onClose = vi.fn()

    render(
      <TeacherTopbarAdminMenu
        open
        panelRef={createRef<HTMLDivElement>()}
        authed={false}
        authSubjectLabel=""
        onOpenModelSettingsPanel={vi.fn()}
        onClose={onClose}
      />,
    )

    fireEvent.change(screen.getByLabelText('管理员用户名'), { target: { value: 'principal_admin' } })
    fireEvent.change(screen.getByLabelText('管理员密码'), { target: { value: 'AdminPass1' } })
    fireEvent.click(screen.getByRole('button', { name: '管理员登录' }))

    await waitFor(() => {
      expect(writeSession).toHaveBeenCalledWith({
        accessToken: 'admin-access',
        teacherId: 'principal_admin',
        teacherName: 'principal_admin',
        role: 'admin',
      })
    })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(JSON.parse(String(init.body))).toEqual({
      username: 'principal_admin',
      password: 'AdminPass1',
    })
    expect(onClose).toHaveBeenCalled()
  })
})
