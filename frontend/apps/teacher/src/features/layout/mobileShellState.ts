export type TeacherMobileTab = 'chat' | 'sessions' | 'workbench'

type TeacherMobilePanels = {
  sessionSidebarOpen: boolean
  skillsOpen: boolean
}

export const isTeacherMobileTab = (value: string): value is TeacherMobileTab =>
  value === 'chat' || value === 'sessions' || value === 'workbench'

export const teacherMobilePanelsFromTab = (tab: TeacherMobileTab): TeacherMobilePanels => {
  if (tab === 'chat') return { sessionSidebarOpen: false, skillsOpen: false }
  if (tab === 'sessions') return { sessionSidebarOpen: true, skillsOpen: false }
  return { sessionSidebarOpen: false, skillsOpen: true }
}

export const teacherMobileTabFromPanels = ({
  sessionSidebarOpen,
  skillsOpen,
}: TeacherMobilePanels): TeacherMobileTab => {
  if (skillsOpen) return 'workbench'
  if (sessionSidebarOpen) return 'sessions'
  return 'chat'
}
