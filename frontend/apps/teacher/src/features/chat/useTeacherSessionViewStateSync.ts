import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { safeLocalStorageSetItem } from '../../utils/storage'
import {
  buildSessionViewStateSignature,
  compareSessionViewStateUpdatedAt,
  normalizeSessionViewStatePayload,
  TEACHER_SESSION_VIEW_STATE_KEY,
  type SessionViewStatePayload,
} from './viewState'

type Params = {
  apiBase: string
  activeSessionId: string
  sessionTitleMap: Record<string, string>
  deletedSessionIds: string[]
  viewStateUpdatedAt: string
  setSessionTitleMap: (value: Record<string, string>) => void
  setDeletedSessionIds: (value: string[]) => void
  setViewStateUpdatedAt: (value: string) => void
  initialState: SessionViewStatePayload
}

export function useTeacherSessionViewStateSync({
  apiBase,
  activeSessionId,
  sessionTitleMap,
  deletedSessionIds,
  viewStateUpdatedAt,
  setSessionTitleMap,
  setDeletedSessionIds,
  setViewStateUpdatedAt,
  initialState,
}: Params) {
  const [syncReady, setSyncReady] = useState(false)
  const applyingViewStateRef = useRef(false)
  const currentViewStateRef = useRef<SessionViewStatePayload>(initialState)
  const lastSyncedViewStateSignatureRef = useRef(buildSessionViewStateSignature(initialState))

  const currentViewState = useMemo(
    () =>
      normalizeSessionViewStatePayload({
        title_map: sessionTitleMap,
        hidden_ids: deletedSessionIds,
        active_session_id: '',
        updated_at: viewStateUpdatedAt,
      }),
    [deletedSessionIds, sessionTitleMap, viewStateUpdatedAt],
  )

  useEffect(() => {
    currentViewStateRef.current = currentViewState
    safeLocalStorageSetItem(
      TEACHER_SESSION_VIEW_STATE_KEY,
      JSON.stringify({
        ...currentViewState,
        active_session_id: activeSessionId,
      }),
    )
    safeLocalStorageSetItem('teacherSessionTitles', JSON.stringify(currentViewState.title_map))
    safeLocalStorageSetItem('teacherDeletedSessions', JSON.stringify(currentViewState.hidden_ids))
  }, [activeSessionId, currentViewState])

  const pushTeacherViewState = useCallback(
    async (state: SessionViewStatePayload) => {
      const payload = normalizeSessionViewStatePayload({
        ...state,
        active_session_id: '',
      })
      const res = await fetch(`${apiBase}/teacher/session/view-state`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ state: payload }),
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `状态码 ${res.status}`)
      }
      const data = await res.json()
      return normalizeSessionViewStatePayload(data?.state || payload)
    },
    [apiBase],
  )

  useEffect(() => {
    let cancelled = false
    const bootstrap = async () => {
      setSyncReady(false)
      const localState = currentViewStateRef.current
      try {
        const res = await fetch(`${apiBase}/teacher/session/view-state`)
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `状态码 ${res.status}`)
        }
        const data = await res.json()
        const remoteState = normalizeSessionViewStatePayload(data?.state || {})
        const cmp = compareSessionViewStateUpdatedAt(remoteState.updated_at, localState.updated_at)
        if (cmp > 0) {
          if (cancelled) return
          applyingViewStateRef.current = true
          setSessionTitleMap(remoteState.title_map)
          setDeletedSessionIds(remoteState.hidden_ids)
          setViewStateUpdatedAt(remoteState.updated_at || new Date().toISOString())
          lastSyncedViewStateSignatureRef.current = buildSessionViewStateSignature(remoteState)
          return
        }
        const saved = await pushTeacherViewState(localState)
        if (cancelled) return
        const sig = buildSessionViewStateSignature(saved)
        lastSyncedViewStateSignatureRef.current = sig
        if (saved.updated_at && saved.updated_at !== localState.updated_at) {
          applyingViewStateRef.current = true
          setViewStateUpdatedAt(saved.updated_at)
        }
      } catch {
        lastSyncedViewStateSignatureRef.current = buildSessionViewStateSignature(localState)
      } finally {
        if (!cancelled) setSyncReady(true)
      }
    }
    void bootstrap()
    return () => {
      cancelled = true
    }
  }, [apiBase, pushTeacherViewState, setDeletedSessionIds, setSessionTitleMap, setViewStateUpdatedAt])

  useEffect(() => {
    if (!syncReady) return
    if (applyingViewStateRef.current) {
      applyingViewStateRef.current = false
      return
    }
    setViewStateUpdatedAt(new Date().toISOString())
  }, [deletedSessionIds, sessionTitleMap, setViewStateUpdatedAt, syncReady])

  useEffect(() => {
    if (!syncReady) return
    const signature = buildSessionViewStateSignature(currentViewState)
    if (signature === lastSyncedViewStateSignatureRef.current) return
    const timer = window.setTimeout(async () => {
      try {
        const saved = await pushTeacherViewState(currentViewState)
        const savedSig = buildSessionViewStateSignature(saved)
        lastSyncedViewStateSignatureRef.current = savedSig
        if (saved.updated_at && saved.updated_at !== currentViewState.updated_at) {
          applyingViewStateRef.current = true
          setViewStateUpdatedAt(saved.updated_at)
        }
      } catch {
        // keep local state and retry on next mutation
      }
    }, 260)
    return () => window.clearTimeout(timer)
  }, [currentViewState, pushTeacherViewState, setViewStateUpdatedAt, syncReady])
}

