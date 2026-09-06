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
    expect(screen.getByRole('button', { name: '设置' }).className).toContain('min-h-[44px]')
    expect(screen.getByRole('button', { name: '设置' }).className).toContain('min-w-[44px]')
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

  it('labels the shell as admin and hides workbench controls after admin login', () => {
    vi.spyOn(teacherAuth, 'readTeacherAccessToken').mockReturnValue('admin-token')
    vi.spyOn(teacherAuth, 'readTeacherAuthRole').mockReturnValue('admin')
    vi.spyOn(teacherAuth, 'readTeacherAuthSubject').mockReturnValue({
      teacher_id: 'principal_admin',
      teacher_name: 'principal_admin',
      role: 'admin',
    })
    render(<TeacherTopbar {...buildProps()} />)

    expect(screen.getByText('身份：管理员')).toBeTruthy()
    expect(screen.queryByText('身份：老师')).toBeNull()
    expect(screen.queryByRole('button', { name: '打开工作台' })).toBeNull()
    expect(screen.queryByRole('button', { name: '展开会话' })).toBeNull()
  })

  it('opens admin panel from desktop management button', () => {
    const props = buildProps()
    render(<TeacherTopbar {...props} />)

    fireEvent.click(screen.getByRole('button', { name: '管理' }))

    expect(screen.getByRole('region', { name: '教师管理面板' })).toBeTruthy()
    expect(screen.getByText('工具抽屉')).toBeTruthy()
  })

  it('keeps identity form values after closing and reopening admin panel', () => {
    const props = buildProps()
    render(<TeacherTopbar {...props} />)

    fireEvent.click(screen.getByRole('button', { name: '管理' }))
    fireEvent.change(screen.getByPlaceholderText('例如：张老师'), { target: { value: '李老师' } })
    fireEvent.click(screen.getByRole('button', { name: '收起' }))

    expect(screen.queryByRole('region', { name: '教师管理面板' })).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: '管理' }))
    expect((screen.getByPlaceholderText('例如：张老师') as HTMLInputElement).value).toBe('李老师')
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
    expect(screen.getByText('用姓名和凭证确认教师身份。')).toBeTruthy()
    expect(screen.getByText('密码设置', { exact: true })).toBeTruthy()
    expect(screen.getByText('设置或更新当前账号密码。')).toBeTruthy()
    expect(screen.getByText('学生密码管理', { exact: true })).toBeTruthy()
    expect(screen.getByText('按学生或班级重置密码。')).toBeTruthy()
    expect(screen.queryByRole('button', { name: '全部学生' })).toBeNull()
  })

  it('associates admin form labels with their fields', () => {
    const props = buildProps()
    render(<TeacherTopbar {...props} />)
    fireEvent.click(screen.getByRole('button', { name: '管理' }))

    const nameInput = screen.getByPlaceholderText('例如：张老师')
    const emailInput = screen.getByPlaceholderText('name@example.com')
    const credentialInput = screen.getByPlaceholderText('输入分发 token')
    const passwordInput = screen.getByPlaceholderText('至少 8 位，含字母和数字')
    expect(screen.getByText('姓名').getAttribute('for')).toBe(nameInput.id)
    expect(screen.getByText('邮箱（同名时必填）').getAttribute('for')).toBe(emailInput.id)
    expect(screen.getByText('token', { selector: 'label' }).getAttribute('for')).toBe(credentialInput.id)
    expect(screen.getByText('新密码').getAttribute('for')).toBe(passwordInput.id)
  })
})
