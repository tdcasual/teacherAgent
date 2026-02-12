import { useEffect, useMemo, useRef, useState, type Dispatch } from 'react'
import { safeLocalStorageRemoveItem, safeLocalStorageSetItem } from '../../../../shared/storage'
import {
  STUDENT_LOCAL_DRAFT_SESSIONS_KEY_PREFIX,
  STUDENT_SESSION_VIEW_STATE_KEY_PREFIX,
  buildSessionViewStateSignature,
  compareSessionViewStateUpdatedAt,
  normalizeSessionViewStatePayload,
  readStudentLocalDraftSessionIds,
  readStudentLocalViewState,
  type SessionViewStatePayload,
} from '../chat/viewState'
import type { StudentAction, StudentState } from '../../hooks/useStudentState'

type UseStudentSessionViewStateSyncParams = {
  state: StudentState
  dispatch: Dispatch<StudentAction>
  setActiveSession: (sessionId: string) => void
}

export function useStudentSessionViewStateSync({ state, dispatch, setActiveSession }: UseStudentSessionViewStateSyncParams) {
  const { apiBase, activeSessionId, sessionTitleMap, deletedSessionIds, localDraftSessionIds } = state
  const verifiedStudentId = state.verifiedStudent?.student_id

  const [viewStateUpdatedAt, setViewStateUpdatedAt] = useState(() => new Date().toISOString())
  const [viewStateSyncReady, setViewStateSyncReady] = useState(false)
  const applyingViewStateRef = useRef(false)
  const currentViewStateRef = useRef<SessionViewStatePayload>(
    normalizeSessionViewStatePayload({ title_map: {}, hidden_ids: [], active_session_id: '', updated_at: new Date().toISOString() }),
  )
  const lastSyncedViewStateSignatureRef = useRef('')
  const currentViewState = useMemo(
    () => normalizeSessionViewStatePayload({ title_map: sessionTitleMap, hidden_ids: deletedSessionIds, active_session_id: '', updated_at: viewStateUpdatedAt }),
    [deletedSessionIds, sessionTitleMap, viewStateUpdatedAt],
  )

  useEffect(() => {
    const sid = String(verifiedStudentId || '').trim()
    if (!sid) {
      dispatch({ type: 'BATCH', actions: [
        { type: 'SET', field: 'sessions', value: [] },
        { type: 'SET', field: 'historyCursor', value: 0 },
        { type: 'SET', field: 'historyHasMore', value: false },
        { type: 'SET', field: 'sessionTitleMap', value: {} },
        { type: 'SET', field: 'deletedSessionIds', value: [] },
        { type: 'SET', field: 'localDraftSessionIds', value: [] },
      ]})
      setViewStateUpdatedAt(new Date().toISOString())
      setViewStateSyncReady(false)
      lastSyncedViewStateSignatureRef.current = ''
      return
    }
    dispatch({ type: 'BATCH', actions: [
      { type: 'SET', field: 'sessions', value: [] },
      { type: 'SET', field: 'historyCursor', value: 0 },
      { type: 'SET', field: 'historyHasMore', value: false },
    ]})
    const localState = readStudentLocalViewState(sid)
    const localDraftIds = readStudentLocalDraftSessionIds(sid)
    applyingViewStateRef.current = true
    dispatch({ type: 'BATCH', actions: [
      { type: 'SET', field: 'sessionTitleMap', value: localState.title_map },
      { type: 'SET', field: 'deletedSessionIds', value: localState.hidden_ids },
      { type: 'SET', field: 'localDraftSessionIds', value: localDraftIds },
    ]})
    setActiveSession(localState.active_session_id || '')
    setViewStateUpdatedAt(localState.updated_at || '')
    lastSyncedViewStateSignatureRef.current = buildSessionViewStateSignature(localState)
    setViewStateSyncReady(false)

    let cancelled = false
    const bootstrap = async () => {
      try {
        const res = await fetch(`${apiBase}/student/session/view-state?student_id=${encodeURIComponent(sid)}`)
        if (!res.ok) { const text = await res.text(); throw new Error(text || `状态码 ${res.status}`) }
        const data = await res.json()
        const remoteState = normalizeSessionViewStatePayload(data?.state || {})
        const cmp = compareSessionViewStateUpdatedAt(remoteState.updated_at, localState.updated_at)
        if (cmp > 0) {
          if (cancelled) return
          applyingViewStateRef.current = true
          dispatch({ type: 'BATCH', actions: [
            { type: 'SET', field: 'sessionTitleMap', value: remoteState.title_map },
            { type: 'SET', field: 'deletedSessionIds', value: remoteState.hidden_ids },
          ]})
          if (remoteState.active_session_id) setActiveSession(remoteState.active_session_id)
          setViewStateUpdatedAt(remoteState.updated_at || new Date().toISOString())
          lastSyncedViewStateSignatureRef.current = buildSessionViewStateSignature(remoteState)
          return
        }
        const payload = normalizeSessionViewStatePayload({ ...localState, active_session_id: '' })
        const saveRes = await fetch(`${apiBase}/student/session/view-state`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ student_id: sid, state: payload }),
        })
        if (!saveRes.ok) { const text = await saveRes.text(); throw new Error(text || `状态码 ${saveRes.status}`) }
        const savedData = await saveRes.json()
        const savedState = normalizeSessionViewStatePayload(savedData?.state || payload)
        if (cancelled) return
        lastSyncedViewStateSignatureRef.current = buildSessionViewStateSignature(savedState)
        if (savedState.updated_at && savedState.updated_at !== payload.updated_at) {
          applyingViewStateRef.current = true
          setViewStateUpdatedAt(savedState.updated_at)
        }
      } catch {
        lastSyncedViewStateSignatureRef.current = buildSessionViewStateSignature(localState)
      } finally {
        if (!cancelled) setViewStateSyncReady(true)
      }
    }
    void bootstrap()
    return () => { cancelled = true }
  }, [apiBase, verifiedStudentId, setActiveSession, dispatch])

  // Persist to localStorage
  useEffect(() => {
    const sid = String(verifiedStudentId || '').trim()
    if (!sid || !viewStateSyncReady) return
    currentViewStateRef.current = currentViewState
    safeLocalStorageSetItem(`${STUDENT_SESSION_VIEW_STATE_KEY_PREFIX}${sid}`, JSON.stringify(currentViewState))
    safeLocalStorageSetItem(`studentSessionTitles:${sid}`, JSON.stringify(currentViewState.title_map))
    safeLocalStorageSetItem(`studentDeletedSessions:${sid}`, JSON.stringify(currentViewState.hidden_ids))
    if (activeSessionId) safeLocalStorageSetItem(`studentActiveSession:${sid}`, activeSessionId)
    else safeLocalStorageRemoveItem(`studentActiveSession:${sid}`)
  }, [activeSessionId, currentViewState, verifiedStudentId, viewStateSyncReady])

  // Persist local draft session ids
  useEffect(() => {
    const sid = String(verifiedStudentId || '').trim()
    if (!sid) return
    try { safeLocalStorageSetItem(`${STUDENT_LOCAL_DRAFT_SESSIONS_KEY_PREFIX}${sid}`, JSON.stringify(localDraftSessionIds)) } catch { /* ignore */ }
  }, [localDraftSessionIds, verifiedStudentId])

  // Update timestamp on state change
  useEffect(() => {
    const sid = String(verifiedStudentId || '').trim()
    if (!sid || !viewStateSyncReady) return
    if (applyingViewStateRef.current) { applyingViewStateRef.current = false; return }
    setViewStateUpdatedAt(new Date().toISOString())
  }, [deletedSessionIds, sessionTitleMap, verifiedStudentId, viewStateSyncReady])

  // Sync to server on change
  useEffect(() => {
    const sid = String(verifiedStudentId || '').trim()
    if (!sid || !viewStateSyncReady) return
    const signature = buildSessionViewStateSignature(currentViewState)
    if (signature === lastSyncedViewStateSignatureRef.current) return
    const timer = window.setTimeout(async () => {
      try {
        const payload = normalizeSessionViewStatePayload({ ...currentViewState, active_session_id: '' })
        const res = await fetch(`${apiBase}/student/session/view-state`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ student_id: sid, state: payload }),
        })
        if (!res.ok) { const text = await res.text(); throw new Error(text || `状态码 ${res.status}`) }
        const data = await res.json()
        const savedState = normalizeSessionViewStatePayload(data?.state || payload)
        lastSyncedViewStateSignatureRef.current = buildSessionViewStateSignature(savedState)
        if (savedState.updated_at && savedState.updated_at !== payload.updated_at) {
          applyingViewStateRef.current = true
          setViewStateUpdatedAt(savedState.updated_at)
        }
      } catch { /* keep local state and retry on next mutation */ }
    }, 260)
    return () => window.clearTimeout(timer)
  }, [apiBase, currentViewState, verifiedStudentId, viewStateSyncReady])

  return { viewStateSyncReady }
}
