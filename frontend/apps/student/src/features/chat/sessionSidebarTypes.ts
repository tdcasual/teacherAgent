import type { Dispatch, FormEvent, KeyboardEvent as ReactKeyboardEvent } from 'react'
import type { AssignmentDetail, SessionGroup, StudentHistorySession, VerifiedStudent } from '../../appTypes'
import type { StudentAction } from '../../hooks/useStudentState'

export type SessionSidebarProps = {
  apiBase: string
  sidebarOpen: boolean
  dispatch: Dispatch<StudentAction>
  verifiedStudent: VerifiedStudent | null
  historyLoading: boolean
  historyError: string
  historyHasMore: boolean
  refreshSessions: (mode?: 'more') => Promise<void>
  showArchivedSessions: boolean
  historyQuery: string
  visibleSessionCount: number
  groupedSessions: Array<SessionGroup<StudentHistorySession>>
  deletedSessionIds: string[]
  activeSessionId: string
  onSelectSession: (sessionId: string) => void
  getSessionTitle: (sessionId: string) => string
  openSessionMenuId: string
  toggleSessionMenu: (sessionId: string) => void
  handleSessionMenuTriggerKeyDown: (sessionId: string, isOpen: boolean, event: ReactKeyboardEvent<HTMLButtonElement>) => void
  handleSessionMenuKeyDown: (sessionId: string, event: ReactKeyboardEvent<HTMLDivElement>) => void
  setSessionMenuTriggerRef: (sessionId: string, node: HTMLButtonElement | null) => void
  setSessionMenuRef: (sessionId: string, node: HTMLDivElement | null) => void
  renameSession: (sessionId: string) => void
  toggleSessionArchive: (sessionId: string) => void
  sessionHasMore: boolean
  sessionLoading: boolean
  sessionCursor: number
  loadSessionMessages: (sessionId: string, cursor: number, append: boolean) => Promise<void>
  sessionError: string
  verifyOpen: boolean
  handleVerify: (event: FormEvent) => void
  handleSetPassword: (event: FormEvent) => void
  nameInput: string
  classInput: string
  credentialInput: string
  credentialType: 'token' | 'password'
  newPasswordInput: string
  verifying: boolean
  settingPassword: boolean
  verifyError: string
  verifyInfo: string
  todayAssignment: AssignmentDetail | null
  assignmentLoading: boolean
  assignmentError: string
  resetVerification: () => void
  startNewStudentSession: () => void
  renameDialogSessionId: string | null
  archiveDialogSessionId: string | null
  archiveDialogActionLabel: string
  archiveDialogIsArchived: boolean
  cancelRenameDialog: () => void
  confirmRenameDialog: (nextTitle: string) => void
  cancelArchiveDialog: () => void
  confirmArchiveDialog: () => void
}
