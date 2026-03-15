import { describe, expect, it } from 'vitest'

import {
  isStudentMobileTab,
  studentMobilePanelsFromTab,
  studentMobileTabFromPanels,
  type StudentMobileTab,
} from './mobileShellState'

describe('student mobile shell state mapping', () => {
  it('maps tab to panel state', () => {
    expect(studentMobilePanelsFromTab('chat')).toEqual({ sessionListOpen: false, verifyOpen: false, homeOpen: false })
    expect(studentMobilePanelsFromTab('sessions')).toEqual({ sessionListOpen: true, verifyOpen: false, homeOpen: false })
    expect(studentMobilePanelsFromTab('learning')).toEqual({ sessionListOpen: false, verifyOpen: false, homeOpen: true })
  })

  it('maps panel state to tab', () => {
    expect(studentMobileTabFromPanels({ sessionListOpen: false, verifyOpen: false, homeOpen: false })).toBe('chat')
    expect(studentMobileTabFromPanels({ sessionListOpen: true, verifyOpen: false, homeOpen: false })).toBe('sessions')
    expect(studentMobileTabFromPanels({ sessionListOpen: false, verifyOpen: false, homeOpen: true })).toBe('learning')
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
