export type StudentMobileTab = 'chat' | 'sessions' | 'learning'

export type StudentMobilePanels = {
  sidebarOpen: boolean
  verifyOpen: boolean
}

export const isStudentMobileTab = (value: string): value is StudentMobileTab =>
  value === 'chat' || value === 'sessions' || value === 'learning'

export const studentMobileTabFromPanels = ({ sidebarOpen, verifyOpen }: StudentMobilePanels): StudentMobileTab => {
  if (!sidebarOpen) return 'chat'
  return verifyOpen ? 'learning' : 'sessions'
}

export const studentMobilePanelsFromTab = (tab: StudentMobileTab): StudentMobilePanels => {
  if (tab === 'chat') return { sidebarOpen: false, verifyOpen: false }
  if (tab === 'sessions') return { sidebarOpen: true, verifyOpen: false }
  return { sidebarOpen: true, verifyOpen: true }
}
