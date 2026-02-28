import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { createRef } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import TeacherTopbar from './TeacherTopbar'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

const buildProps = () => ({
  topbarRef: createRef<HTMLElement>(),
  sessionSidebarOpen: false,
  skillsOpen: false,
  onToggleSessionSidebar: vi.fn(),
  onOpenRoutingSettingsPanel: vi.fn(),
  onOpenPersonaManager: vi.fn(),
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

    expect(screen.getByRole('button', { name: '会话' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '更多' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: '教师认证' })).toBeNull()
  })

  it('shows auth action inside compact more menu', () => {
    const props = buildProps()
    render(<TeacherTopbar {...props} compactMobile />)

    fireEvent.click(screen.getByRole('button', { name: '更多' }))

    expect(screen.getByRole('menu', { name: '移动端更多操作' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '教师认证' })).toBeTruthy()
  })
})
