import { describe, expect, it } from 'vitest'

import {
  isStudentMobileTab,
  studentMobilePanelsFromTab,
  studentMobileTabFromPanels,
  type StudentMobileTab,
} from './mobileShellState'

describe('student mobile shell state mapping', () => {
  it('maps tab to panel state', () => {
    expect(studentMobilePanelsFromTab('chat')).toEqual({ sidebarOpen: false, verifyOpen: false })
    expect(studentMobilePanelsFromTab('sessions')).toEqual({ sidebarOpen: true, verifyOpen: false })
    expect(studentMobilePanelsFromTab('learning')).toEqual({ sidebarOpen: true, verifyOpen: true })
  })

  it('maps panel state to tab', () => {
    expect(studentMobileTabFromPanels({ sidebarOpen: false, verifyOpen: false })).toBe('chat')
    expect(studentMobileTabFromPanels({ sidebarOpen: true, verifyOpen: false })).toBe('sessions')
    expect(studentMobileTabFromPanels({ sidebarOpen: true, verifyOpen: true })).toBe('learning')
  })

  it('round-trips each supported tab', () => {
    const tabs: StudentMobileTab[] = ['chat', 'sessions', 'learning']
    for (const tab of tabs) {
      expect(studentMobileTabFromPanels(studentMobilePanelsFromTab(tab))).toBe(tab)
    }
  })

  it('guards tab strings', () => {
    expect(isStudentMobileTab('chat')).toBe(true)
    expect(isStudentMobileTab('sessions')).toBe(true)
    expect(isStudentMobileTab('learning')).toBe(true)
    expect(isStudentMobileTab('workbench')).toBe(false)
  })
})
