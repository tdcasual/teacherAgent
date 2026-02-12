import { useCallback, useReducer } from 'react'
import {
  createInitialTeacherSessionState,
  teacherSessionReducer,
  type TeacherSessionState,
} from './teacherSessionState'
import type { TeacherHistorySession } from '../../appTypes'
import type { SessionViewStatePayload } from '../chat/viewState'

export function useTeacherSessionState(initialViewState: SessionViewStatePayload) {
  const [state, dispatch] = useReducer(teacherSessionReducer, initialViewState, createInitialTeacherSessionState)

  const setField = useCallback(
    (key: keyof TeacherSessionState, value: TeacherSessionState[keyof TeacherSessionState]) => {
      dispatch({ type: 'set', key, value })
    },
    [dispatch],
  )

  const update = useCallback(
    (updater: (prev: TeacherSessionState) => TeacherSessionState) => {
      dispatch({ type: 'update', update: updater })
    },
    [dispatch],
  )

  const setHistorySessions = useCallback(
    (value: TeacherHistorySession[] | ((prev: TeacherHistorySession[]) => TeacherHistorySession[])) => {
      if (typeof value === 'function') {
        update((prev) => ({ ...prev, historySessions: (value as any)(prev.historySessions) }))
        return
      }
      setField('historySessions', value)
    },
    [setField, update],
  )

  const setSessionTitleMap = useCallback(
    (value: Record<string, string> | ((prev: Record<string, string>) => Record<string, string>)) => {
      if (typeof value === 'function') {
        update((prev) => ({ ...prev, sessionTitleMap: (value as any)(prev.sessionTitleMap) }))
        return
      }
      setField('sessionTitleMap', value)
    },
    [setField, update],
  )

  const setDeletedSessionIds = useCallback(
    (value: string[] | ((prev: string[]) => string[])) => {
      if (typeof value === 'function') {
        update((prev) => ({ ...prev, deletedSessionIds: (value as any)(prev.deletedSessionIds) }))
        return
      }
      setField('deletedSessionIds', value)
    },
    [setField, update],
  )

  const setLocalDraftSessionIds = useCallback(
    (value: string[] | ((prev: string[]) => string[])) => {
      if (typeof value === 'function') {
        update((prev) => ({ ...prev, localDraftSessionIds: (value as any)(prev.localDraftSessionIds) }))
        return
      }
      setField('localDraftSessionIds', value)
    },
    [setField, update],
  )

  const setOpenSessionMenuId = useCallback(
    (value: string | ((prev: string) => string)) => {
      if (typeof value === 'function') {
        update((prev) => ({ ...prev, openSessionMenuId: (value as any)(prev.openSessionMenuId) }))
        return
      }
      setField('openSessionMenuId', value)
    },
    [setField, update],
  )

  const setActiveSessionId = useCallback(
    (value: string | ((prev: string) => string)) => {
      if (typeof value === 'function') {
        update((prev) => ({ ...prev, activeSessionId: (value as any)(prev.activeSessionId) }))
        return
      }
      setField('activeSessionId', value)
    },
    [setField, update],
  )

  const setViewStateUpdatedAt = useCallback((value: string) => setField('viewStateUpdatedAt', value), [setField])

  const setHistoryLoading = useCallback((value: boolean) => setField('historyLoading', value), [setField])
  const setHistoryError = useCallback((value: string) => setField('historyError', value), [setField])
  const setHistoryCursor = useCallback((value: number) => setField('historyCursor', value), [setField])
  const setHistoryHasMore = useCallback((value: boolean) => setField('historyHasMore', value), [setField])
  const setHistoryQuery = useCallback((value: string) => setField('historyQuery', value), [setField])
  const setShowArchivedSessions = useCallback(
    (value: boolean | ((prev: boolean) => boolean)) => {
      if (typeof value === 'function') {
        update((prev) => ({ ...prev, showArchivedSessions: (value as any)(prev.showArchivedSessions) }))
        return
      }
      setField('showArchivedSessions', value)
    },
    [setField, update],
  )
  const setRenameDialogSessionId = useCallback((value: string | null) => setField('renameDialogSessionId', value), [setField])
  const setArchiveDialogSessionId = useCallback((value: string | null) => setField('archiveDialogSessionId', value), [setField])
  const setSessionLoading = useCallback((value: boolean) => setField('sessionLoading', value), [setField])
  const setSessionError = useCallback((value: string) => setField('sessionError', value), [setField])
  const setSessionCursor = useCallback((value: number) => setField('sessionCursor', value), [setField])
  const setSessionHasMore = useCallback((value: boolean) => setField('sessionHasMore', value), [setField])

  return {
    ...state,
    setHistorySessions,
    setHistoryLoading,
    setHistoryError,
    setHistoryCursor,
    setHistoryHasMore,
    setHistoryQuery,
    setShowArchivedSessions,
    setSessionTitleMap,
    setDeletedSessionIds,
    setLocalDraftSessionIds,
    setOpenSessionMenuId,
    setRenameDialogSessionId,
    setArchiveDialogSessionId,
    setSessionLoading,
    setSessionError,
    setSessionCursor,
    setSessionHasMore,
    setActiveSessionId,
    setViewStateUpdatedAt,
  }
}
