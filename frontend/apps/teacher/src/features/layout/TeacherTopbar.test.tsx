import { cleanup, render, screen } from '@testing-library/react'
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
})
