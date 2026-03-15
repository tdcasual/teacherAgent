export type StudentMobileTab = 'chat' | 'sessions' | 'learning'

type StudentMobilePanels = {
  sessionListOpen: boolean
  verifyOpen: boolean
  homeOpen: boolean
}

export const isStudentMobileTab = (value: string): value is StudentMobileTab =>
  value === 'chat' || value === 'sessions' || value === 'learning'

export const studentMobileTabFromPanels = ({ sessionListOpen, verifyOpen, homeOpen }: StudentMobilePanels): StudentMobileTab => {
  if (homeOpen || verifyOpen) return 'learning'
  if (sessionListOpen) return 'sessions'
  return 'chat'
}

export const studentMobilePanelsFromTab = (tab: StudentMobileTab): StudentMobilePanels => {
  if (tab === 'chat') return { sessionListOpen: false, verifyOpen: false, homeOpen: false }
  if (tab === 'sessions') return { sessionListOpen: true, verifyOpen: false, homeOpen: false }
  return { sessionListOpen: false, verifyOpen: false, homeOpen: true }
}
