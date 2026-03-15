import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { createRef } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import TeacherTopbar from './TeacherTopbar'
import * as teacherAuth from '../auth/teacherAuth'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const buildProps = () => ({
  topbarRef: createRef<HTMLElement>(),
  sessionSidebarOpen: false,
  skillsOpen: false,
  onToggleSessionSidebar: vi.fn(),
  onOpenModelSettingsPanel: vi.fn(),
  onToggleSkillsWorkbench: vi.fn(),
  onToggleSettingsPanel: vi.fn(),
})

describe('TeacherTopbar desktop AI entry logo', () => {
  it('renders AI entry logo on desktop mode', () => {
    const props = buildProps()
    render(<TeacherTopbar {...props} />)

    const logo = screen.getByAltText('AI入口图标')
    expect(logo.getAttribute('src')).toBe('/ai-entry-logo.png')
  })

  it('hides AI entry logo on compact mobile mode', () => {
    const props = buildProps()
    render(<TeacherTopbar {...props} compactMobile />)

    expect(screen.queryByAltText('AI入口图标')).toBeNull()
  })

  it('keeps compact mode to primary actions and hides direct auth button', () => {
    const props = buildProps()
    render(<TeacherTopbar {...props} compactMobile />)
    const header = screen.getByRole('banner')

    expect(screen.getByRole('button', { name: '会话' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '更多' })).toBeTruthy()
    expect(header.className).toContain('mobile-topbar-compact')
    expect(screen.queryByRole('button', { name: '教师认证' })).toBeNull()
  })

  it('keeps desktop topbar to context actions and a single admin entry', () => {
    const props = buildProps()
    render(<TeacherTopbar {...props} />)

    expect(screen.getByRole('button', { name: '展开会话' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '打开工作台' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '管理' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '设置' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: '模型设置' })).toBeNull()
    expect(screen.queryByRole('button', { name: '教师认证' })).toBeNull()
  })

  it('shows admin entry inside compact more menu', () => {
    const props = buildProps()
    render(<TeacherTopbar {...props} compactMobile />)

    fireEvent.click(screen.getByRole('button', { name: '更多' }))

    expect(screen.getByRole('menu', { name: '移动端更多操作' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '打开管理' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: '教师认证' })).toBeNull()
  })

  it('opens admin panel from desktop management button', () => {
    const props = buildProps()
    render(<TeacherTopbar {...props} />)

    fireEvent.click(screen.getByRole('button', { name: '管理' }))

    expect(screen.getByRole('dialog', { name: '教师管理面板' })).toBeTruthy()
  })

  it('groups management actions into identity, password, and student reset sections', () => {
    vi.spyOn(teacherAuth, 'readTeacherAccessToken').mockReturnValue('teacher-token')
    vi.spyOn(teacherAuth, 'readTeacherAuthSubject').mockReturnValue({
      teacher_id: 'T001',
      teacher_name: '张老师',
      email: 'teacher@example.com',
    })

    const props = buildProps()
    render(<TeacherTopbar {...props} />)

    fireEvent.click(screen.getByRole('button', { name: '管理' }))

    expect(screen.getByText('身份验证', { exact: true })).toBeTruthy()
    expect(screen.getByText('使用姓名与凭证确认当前教师身份。')).toBeTruthy()
    expect(screen.getByText('密码设置', { exact: true })).toBeTruthy()
    expect(screen.getByText('为当前教师账号设置或更新密码。')).toBeTruthy()
    expect(screen.getByText('学生密码管理', { exact: true })).toBeTruthy()
  })
})
