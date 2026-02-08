import type { TeacherHistorySession } from '../../appTypes'
import { readTeacherLocalDraftSessionIds, type SessionViewStatePayload } from '../chat/viewState'

export type TeacherSessionState = {
  historySessions: TeacherHistorySession[]
  historyLoading: boolean
  historyError: string
  historyCursor: number
  historyHasMore: boolean
  historyQuery: string
  showArchivedSessions: boolean

  sessionTitleMap: Record<string, string>
  deletedSessionIds: string[]
  localDraftSessionIds: string[]
  openSessionMenuId: string
  renameDialogSessionId: string | null
  archiveDialogSessionId: string | null

  sessionLoading: boolean
  sessionError: string
  sessionCursor: number
  sessionHasMore: boolean

  activeSessionId: string
  viewStateUpdatedAt: string
}

export type TeacherSessionAction =
  | { type: 'set'; key: keyof TeacherSessionState; value: TeacherSessionState[keyof TeacherSessionState] }
  | { type: 'update'; update: (prev: TeacherSessionState) => TeacherSessionState }

export const createInitialTeacherSessionState = (initialViewState: SessionViewStatePayload): TeacherSessionState => {
  return {
    historySessions: [],
    historyLoading: false,
    historyError: '',
    historyCursor: 0,
    historyHasMore: false,
    historyQuery: '',
    showArchivedSessions: false,

    sessionTitleMap: initialViewState.title_map,
    deletedSessionIds: initialViewState.hidden_ids,
    localDraftSessionIds: readTeacherLocalDraftSessionIds(),
    openSessionMenuId: '',
    renameDialogSessionId: null,
    archiveDialogSessionId: null,

    sessionLoading: false,
    sessionError: '',
    sessionCursor: -1,
    sessionHasMore: false,

    activeSessionId: initialViewState.active_session_id || 'main',
    viewStateUpdatedAt: initialViewState.updated_at || new Date().toISOString(),
  }
}

export const teacherSessionReducer = (state: TeacherSessionState, action: TeacherSessionAction): TeacherSessionState => {
  if (action.type === 'update') return action.update(state)
  if (action.type === 'set') return { ...state, [action.key]: action.value } as TeacherSessionState
  return state
}
