import { useCallback, useReducer } from 'react'
import {
  createInitialTeacherSessionState,
  teacherSessionReducer,
  type TeacherSessionState,
} from './teacherSessionState'
import type { TeacherHistorySession } from '../../appTypes'
import type { SessionViewStatePayload } from '../chat/viewState'

type StateSetterValue<T> = T | ((prev: T) => T)

const resolveStateSetter = <T>(value: StateSetterValue<T>, prev: T): T => {
  if (typeof value === 'function') {
    return (value as (prev: T) => T)(prev)
  }
  return value
}

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
    (value: StateSetterValue<TeacherHistorySession[]>) => {
      update((prev) => ({ ...prev, historySessions: resolveStateSetter(value, prev.historySessions) }))
    },
    [update],
  )

  const setSessionTitleMap = useCallback(
    (value: StateSetterValue<Record<string, string>>) => {
      update((prev) => ({ ...prev, sessionTitleMap: resolveStateSetter(value, prev.sessionTitleMap) }))
    },
    [update],
  )

  const setDeletedSessionIds = useCallback(
    (value: StateSetterValue<string[]>) => {
      update((prev) => ({ ...prev, deletedSessionIds: resolveStateSetter(value, prev.deletedSessionIds) }))
    },
    [update],
  )

  const setLocalDraftSessionIds = useCallback(
    (value: StateSetterValue<string[]>) => {
      update((prev) => ({ ...prev, localDraftSessionIds: resolveStateSetter(value, prev.localDraftSessionIds) }))
    },
    [update],
  )

  const setOpenSessionMenuId = useCallback(
    (value: StateSetterValue<string>) => {
      update((prev) => ({ ...prev, openSessionMenuId: resolveStateSetter(value, prev.openSessionMenuId) }))
    },
    [update],
  )

  const setActiveSessionId = useCallback(
    (value: StateSetterValue<string>) => {
      update((prev) => ({ ...prev, activeSessionId: resolveStateSetter(value, prev.activeSessionId) }))
    },
    [update],
  )

  const setViewStateUpdatedAt = useCallback((value: string) => setField('viewStateUpdatedAt', value), [setField])

  const setHistoryLoading = useCallback((value: boolean) => setField('historyLoading', value), [setField])
  const setHistoryError = useCallback((value: string) => setField('historyError', value), [setField])
  const setHistoryCursor = useCallback((value: number) => setField('historyCursor', value), [setField])
  const setHistoryHasMore = useCallback((value: boolean) => setField('historyHasMore', value), [setField])
  const setHistoryQuery = useCallback((value: string) => setField('historyQuery', value), [setField])
  const setShowArchivedSessions = useCallback(
    (value: StateSetterValue<boolean>) => {
      update((prev) => ({ ...prev, showArchivedSessions: resolveStateSetter(value, prev.showArchivedSessions) }))
    },
    [update],
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
