export type StudentMobileTab = 'chat' | 'sessions' | 'learning'

type StudentMobilePanels = {
  sidebarOpen: boolean
  verifyOpen: boolean
  homeOpen: boolean
}

export const isStudentMobileTab = (value: string): value is StudentMobileTab =>
  value === 'chat' || value === 'sessions' || value === 'learning'

export const studentMobileTabFromPanels = ({ sidebarOpen, verifyOpen, homeOpen }: StudentMobilePanels): StudentMobileTab => {
  if (homeOpen || verifyOpen) return 'learning'
  if (!sidebarOpen) return 'chat'
  return 'sessions'
}

export const studentMobilePanelsFromTab = (tab: StudentMobileTab): StudentMobilePanels => {
  if (tab === 'chat') return { sidebarOpen: false, verifyOpen: false, homeOpen: false }
  if (tab === 'sessions') return { sidebarOpen: true, verifyOpen: false, homeOpen: false }
  return { sidebarOpen: false, verifyOpen: false, homeOpen: true }
}
