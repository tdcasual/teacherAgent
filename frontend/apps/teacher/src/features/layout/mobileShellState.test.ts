import { describe, expect, it } from 'vitest'

import {
  isTeacherMobileTab,
  teacherMobilePanelsFromTab,
  teacherMobileTabFromPanels,
  type TeacherMobileTab,
} from './mobileShellState'

describe('teacher mobile shell state mapping', () => {
  it('maps tab to panel state', () => {
    expect(teacherMobilePanelsFromTab('chat')).toEqual({ sessionSidebarOpen: false, skillsOpen: false })
    expect(teacherMobilePanelsFromTab('sessions')).toEqual({ sessionSidebarOpen: true, skillsOpen: false })
    expect(teacherMobilePanelsFromTab('workbench')).toEqual({ sessionSidebarOpen: false, skillsOpen: true })
  })

  it('maps panel state to tab', () => {
    expect(teacherMobileTabFromPanels({ sessionSidebarOpen: false, skillsOpen: false })).toBe('chat')
    expect(teacherMobileTabFromPanels({ sessionSidebarOpen: true, skillsOpen: false })).toBe('sessions')
    expect(teacherMobileTabFromPanels({ sessionSidebarOpen: false, skillsOpen: true })).toBe('workbench')
    expect(teacherMobileTabFromPanels({ sessionSidebarOpen: true, skillsOpen: true })).toBe('workbench')
  })

  it('round-trips each supported tab', () => {
    const tabs: TeacherMobileTab[] = ['chat', 'sessions', 'workbench']
    for (const tab of tabs) {
      expect(teacherMobileTabFromPanels(teacherMobilePanelsFromTab(tab))).toBe(tab)
    }
  })

  it('guards tab strings', () => {
    expect(isTeacherMobileTab('chat')).toBe(true)
    expect(isTeacherMobileTab('sessions')).toBe(true)
    expect(isTeacherMobileTab('workbench')).toBe(true)
    expect(isTeacherMobileTab('learning')).toBe(false)
  })
})
