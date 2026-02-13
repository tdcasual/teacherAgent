import { useCallback, useEffect, useMemo, type Dispatch, type MutableRefObject } from 'react'
import { makeId } from '../../../shared/id'
import { nowTime, timeFromIso } from '../../../shared/time'
import { stripTransientPendingBubbles } from '../features/chat/pendingOverlay'
import { selectArchiveDialogMeta, selectGroupedSessions, selectVisibleSessions } from '../features/chat/studentUiSelectors'
import { clearStudentAccessToken } from '../features/auth/studentAuth'
import type { Message, PendingChatJob, StudentHistorySessionResponse, StudentHistorySessionsResponse } from '../appTypes'
import {
  STUDENT_NEW_SESSION_MESSAGE,
  toErrorMessage,
  todayDate,
  type RecentCompletedReply,
  recentCompletionKeyOf,
  RECENT_COMPLETION_TTL_MS,
  type StudentAction,
  type StudentState,
} from './useStudentState'

type Refs = {
  historyRequestRef: MutableRefObject<number>
  sessionRequestRef: MutableRefObject<number>
  pendingChatJobRef: MutableRefObject<PendingChatJob | null>
  recentCompletedRepliesRef: MutableRefObject<RecentCompletedReply[]>
}

type UseSessionManagerParams = {
  state: StudentState
  dispatch: Dispatch<StudentAction>
  refs: Refs
  setActiveSession: (sessionId: string) => void
  saveScrollHeight: () => void
  restoreScrollPosition: () => void
}

export function useSessionManager({ state, dispatch, refs, setActiveSession, saveScrollHeight, restoreScrollPosition }: UseSessionManagerParams) {
  const {
    apiBase, verifiedStudent, sessions, deletedSessionIds, historyQuery,
    sessionTitleMap, showArchivedSessions, activeSessionId, historyCursor,
    historyHasMore, localDraftSessionIds, renameDialogSessionId, archiveDialogSessionId,
  } = state
  const { historyRequestRef, sessionRequestRef, pendingChatJobRef, recentCompletedRepliesRef } = refs

  const refreshSessions = useCallback(async (mode: 'reset' | 'more' = 'reset') => {
    const sid = verifiedStudent?.student_id?.trim() || ''
    if (!sid) return
    if (mode === 'more' && !historyHasMore) return
    const cursor = mode === 'more' ? historyCursor : 0
    const requestNo = ++historyRequestRef.current
    dispatch({ type: 'SET', field: 'historyLoading', value: true })
    if (mode === 'reset') dispatch({ type: 'SET', field: 'historyError', value: '' })
    try {
      const url = new URL(`${apiBase}/student/history/sessions`)
      url.searchParams.set('student_id', sid)
      url.searchParams.set('limit', '30')
      url.searchParams.set('cursor', String(cursor))
      const res = await fetch(url.toString())
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `状态码 ${res.status}`)
      }
      const data = (await res.json()) as StudentHistorySessionsResponse
      if (requestNo !== historyRequestRef.current) return
      const serverSessions = Array.isArray(data.sessions) ? data.sessions : []
      const serverIds = new Set(serverSessions.map((item) => String(item.session_id || '').trim()).filter(Boolean))
      dispatch({ type: 'UPDATE_LOCAL_DRAFT_SESSION_IDS', updater: (prev) => prev.filter((id) => !serverIds.has(id)) })
      const nextCursor = typeof data.next_cursor === 'number' ? data.next_cursor : null
      dispatch({ type: 'SET', field: 'historyCursor', value: nextCursor ?? 0 })
      dispatch({ type: 'SET', field: 'historyHasMore', value: nextCursor !== null })
      if (mode === 'more') {
        dispatch({ type: 'UPDATE_SESSIONS', updater: (prev) => {
          const merged = [...prev]
          const existingIds = new Set(prev.map((item) => item.session_id))
          for (const item of serverSessions) {
            if (existingIds.has(item.session_id)) continue
            merged.push(item)
          }
          return merged
        }})
      } else {
        dispatch({ type: 'UPDATE_SESSIONS', updater: (prev) => {
          const draftItems = localDraftSessionIds
            .filter((id) => !serverIds.has(id))
            .map((id) => prev.find((item) => item.session_id === id) || { session_id: id, updated_at: new Date().toISOString(), message_count: 0 })
          const seeded = [...draftItems, ...serverSessions]
          const seen = new Set(seeded.map((item) => item.session_id))
          for (const item of prev) {
            if (seen.has(item.session_id)) continue
            seeded.push(item)
          }
          return seeded
        }})
      }
    } catch (err: unknown) {
      if (requestNo !== historyRequestRef.current) return
      dispatch({ type: 'SET', field: 'historyError', value: toErrorMessage(err) })
    } finally {
      if (requestNo !== historyRequestRef.current) return
      dispatch({ type: 'SET', field: 'historyLoading', value: false })
    }
  }, [verifiedStudent?.student_id, historyHasMore, historyCursor, historyRequestRef, localDraftSessionIds, apiBase, dispatch])

  const loadSessionMessages = useCallback(async (sessionId: string, cursor: number, append: boolean) => {
    const sid = verifiedStudent?.student_id?.trim() || ''
    if (!sid || !sessionId) return
    const targetSessionId = String(sessionId || '').trim()
    if (!targetSessionId) return
    const requestNo = ++sessionRequestRef.current
    dispatch({ type: 'BATCH', actions: [
      { type: 'SET', field: 'sessionLoading', value: true },
      { type: 'SET', field: 'sessionError', value: '' },
    ]})
    try {
      const LIMIT = 80
      const url = new URL(`${apiBase}/student/history/session`)
      url.searchParams.set('student_id', sid)
      url.searchParams.set('session_id', targetSessionId)
      url.searchParams.set('cursor', String(cursor))
      url.searchParams.set('limit', String(LIMIT))
      url.searchParams.set('direction', 'backward')
      const res = await fetch(url.toString())
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `状态码 ${res.status}`)
      }
      const data = (await res.json()) as StudentHistorySessionResponse
      if (requestNo !== sessionRequestRef.current) return
      const raw = Array.isArray(data.messages) ? data.messages : []
      const mapped: Message[] = raw
        .map((m, idx) => {
          const roleRaw = String(m.role || '').toLowerCase()
          const role = roleRaw === 'assistant' ? 'assistant' : roleRaw === 'user' ? 'user' : null
          const content = typeof m.content === 'string' ? m.content : ''
          if (!role || !content) return null
          return { id: `hist_${targetSessionId}_${cursor}_${idx}_${m.ts || ''}`, role, content, time: timeFromIso(m.ts) } as Message
        })
        .filter(Boolean) as Message[]

      const pending = pendingChatJobRef.current
      const mergedPending: Message[] =
        pending?.job_id && pending.session_id === targetSessionId
          ? (() => {
              const base = stripTransientPendingBubbles(mapped)
              const hasUserText = pending.user_text ? base.some((item) => item.role === 'user' && item.content === pending.user_text) : true
              const hasPlaceholder = base.some((item) => item.id === pending.placeholder_id)
              const next = [...base]
              if (!hasUserText && pending.user_text) next.push({ id: makeId(), role: 'user', content: pending.user_text, time: nowTime() })
              if (!hasPlaceholder) next.push({ id: pending.placeholder_id, role: 'assistant', content: '正在回复中…', time: nowTime() })
              return next
            })()
          : mapped

      const recentReplies = recentCompletedRepliesRef.current
      const merged: Message[] =
        recentReplies.length && !(pending?.job_id && pending.session_id === targetSessionId)
          ? (() => {
              const now = Date.now()
              const assistantHistoryCandidates = raw
                .map((item) => {
                  const roleRaw = String(item.role || '').toLowerCase()
                  const content = typeof item.content === 'string' ? item.content : ''
                  if (roleRaw !== 'assistant' || !content) return null
                  const parsedTs = typeof item.ts === 'string' ? Date.parse(item.ts) : Number.NaN
                  return { content, ts_ms: Number.isFinite(parsedTs) ? parsedTs : Number.NaN, used: false }
                })
                .filter(Boolean) as Array<{ content: string; ts_ms: number; used: boolean }>

              const userHistoryCounts = raw.reduce<Record<string, number>>((acc, item) => {
                const roleRaw = String(item.role || '').toLowerCase()
                const content = typeof item.content === 'string' ? item.content : ''
                if (roleRaw !== 'user' || !content) return acc
                acc[content] = (acc[content] || 0) + 1
                return acc
              }, {})

              const removableKeys = new Set<string>()
              const unresolvedRecent: RecentCompletedReply[] = []

              for (const recent of [...recentReplies].sort((a, b) => a.completed_at - b.completed_at)) {
                const recentKey = recentCompletionKeyOf(recent)
                if (now - recent.completed_at > RECENT_COMPLETION_TTL_MS) { removableKeys.add(recentKey); continue }
                if (recent.session_id !== targetSessionId) continue
                let matchedIndex = assistantHistoryCandidates.findIndex((c) => !c.used && c.content === recent.reply_text && Number.isFinite(c.ts_ms) && c.ts_ms >= recent.completed_at - RECENT_COMPLETION_TTL_MS)
                if (matchedIndex < 0 && recent.user_text && (userHistoryCounts[recent.user_text] || 0) > 0) {
                  matchedIndex = assistantHistoryCandidates.findIndex((c) => !c.used && c.content === recent.reply_text && !Number.isFinite(c.ts_ms))
                }
                if (matchedIndex >= 0) { assistantHistoryCandidates[matchedIndex].used = true; removableKeys.add(recentKey); continue }
                unresolvedRecent.push(recent)
              }

              const patched = [...mergedPending]
              for (const recent of unresolvedRecent) {
                if (recent.user_text) patched.push({ id: makeId(), role: 'user', content: recent.user_text, time: nowTime() })
                patched.push({ id: makeId(), role: 'assistant', content: recent.reply_text, time: nowTime() })
              }
              if (removableKeys.size > 0) {
                dispatch({ type: 'UPDATE_RECENT_COMPLETED_REPLIES', updater: (prev) => prev.filter((item) => !removableKeys.has(recentCompletionKeyOf(item))) })
              }
              return patched
            })()
          : mergedPending

      const next = typeof data.next_cursor === 'number' ? data.next_cursor : 0
      dispatch({ type: 'SET', field: 'sessionCursor', value: next })
      dispatch({ type: 'SET', field: 'sessionHasMore', value: merged.length >= 1 && next > 0 })
      if (append) {
        saveScrollHeight()
        dispatch({ type: 'UPDATE_MESSAGES', updater: (prev) => [...merged, ...prev] })
        requestAnimationFrame(() => restoreScrollPosition())
      } else {
        dispatch({ type: 'SET', field: 'messages', value: merged.length ? merged : [{ id: makeId(), role: 'assistant', content: STUDENT_NEW_SESSION_MESSAGE, time: nowTime() }] })
      }
    } catch (err: unknown) {
      if (requestNo !== sessionRequestRef.current) return
      dispatch({ type: 'SET', field: 'sessionError', value: toErrorMessage(err) })
    } finally {
      if (requestNo !== sessionRequestRef.current) return
      dispatch({ type: 'SET', field: 'sessionLoading', value: false })
    }
  }, [verifiedStudent?.student_id, apiBase, sessionRequestRef, pendingChatJobRef, recentCompletedRepliesRef, dispatch, saveScrollHeight, restoreScrollPosition])

  // Auto-refresh sessions on login
  useEffect(() => {
    if (!verifiedStudent?.student_id) return
    void refreshSessions()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [verifiedStudent?.student_id, apiBase])

  // Periodic refresh
  useEffect(() => {
    if (!verifiedStudent?.student_id) return
    const timer = window.setInterval(() => { void refreshSessions() }, 30000)
    return () => window.clearInterval(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [verifiedStudent?.student_id, apiBase])

  // ── Session actions (merged from useStudentSessionActions) ──

  const getSessionTitle = useCallback((sessionId: string) => {
    const sid = String(sessionId || '').trim()
    if (!sid) return '未命名会话'
    return sessionTitleMap[sid] || sid
  }, [sessionTitleMap])

  const visibleSessions = useMemo(() => selectVisibleSessions({
    sessions,
    deletedSessionIds,
    historyQuery,
    sessionTitleMap,
    showArchivedSessions,
  }), [sessions, deletedSessionIds, historyQuery, sessionTitleMap, showArchivedSessions])

  const groupedSessions = useMemo(() => selectGroupedSessions(visibleSessions), [visibleSessions])

  const closeSidebarOnMobile = useCallback(() => {
    if (typeof window === 'undefined') return
    if (window.matchMedia('(max-width: 900px)').matches) dispatch({ type: 'SET', field: 'sidebarOpen', value: false })
  }, [dispatch])

  const selectStudentSession = useCallback((sessionId: string) => {
    const sid = String(sessionId || '').trim()
    if (!sid) return
    dispatch({ type: 'SET', field: 'forceSessionLoadToken', value: state.forceSessionLoadToken + 1 })
    setActiveSession(sid)
    dispatch({ type: 'BATCH', actions: [
      { type: 'SET', field: 'sessionCursor', value: -1 },
      { type: 'SET', field: 'sessionHasMore', value: false },
      { type: 'SET', field: 'sessionError', value: '' },
      { type: 'SET', field: 'openSessionMenuId', value: '' },
    ]})
    closeSidebarOnMobile()
  }, [closeSidebarOnMobile, state.forceSessionLoadToken, setActiveSession, dispatch])

  const resetVerification = useCallback(() => {
    clearStudentAccessToken()
    dispatch({ type: 'BATCH', actions: [
      { type: 'SET', field: 'verifiedStudent', value: null },
      { type: 'SET', field: 'nameInput', value: '' },
      { type: 'SET', field: 'classInput', value: '' },
      { type: 'SET', field: 'credentialInput', value: '' },
      { type: 'SET', field: 'credentialType', value: 'token' },
      { type: 'SET', field: 'newPasswordInput', value: '' },
      { type: 'SET', field: 'verifyError', value: '' },
      { type: 'SET', field: 'verifyInfo', value: '' },
      { type: 'SET', field: 'verifyOpen', value: true },
    ]})
  }, [dispatch])

  const startNewStudentSession = useCallback(() => {
    const next = `general_${todayDate()}_${Math.random().toString(16).slice(2, 6)}`
    sessionRequestRef.current += 1
    dispatch({ type: 'UPDATE_LOCAL_DRAFT_SESSION_IDS', updater: (prev) => prev.includes(next) ? prev : [next, ...prev] })
    dispatch({ type: 'BATCH', actions: [
      { type: 'SET', field: 'showArchivedSessions', value: false },
      { type: 'SET', field: 'sessionCursor', value: -1 },
      { type: 'SET', field: 'sessionHasMore', value: false },
      { type: 'SET', field: 'sessionError', value: '' },
      { type: 'SET', field: 'openSessionMenuId', value: '' },
      { type: 'SET', field: 'pendingChatJob', value: null },
      { type: 'SET', field: 'sending', value: false },
      { type: 'SET', field: 'input', value: '' },
    ]})
    setActiveSession(next)
    dispatch({ type: 'UPDATE_SESSIONS', updater: (prev) => {
      if (prev.some((item) => item.session_id === next)) return prev
      return [{ session_id: next, updated_at: new Date().toISOString(), message_count: 0, preview: '' }, ...prev]
    }})
    dispatch({ type: 'SET', field: 'messages', value: [{ id: makeId(), role: 'assistant' as const, content: STUDENT_NEW_SESSION_MESSAGE, time: nowTime() }] })
    closeSidebarOnMobile()
  }, [closeSidebarOnMobile, sessionRequestRef, setActiveSession, dispatch])

  const renameSession = useCallback((sessionId: string) => {
    const sid = String(sessionId || '').trim()
    if (sid) dispatch({ type: 'SET', field: 'renameDialogSessionId', value: sid })
  }, [dispatch])

  const toggleSessionArchive = useCallback((sessionId: string) => {
    const sid = String(sessionId || '').trim()
    if (sid) dispatch({ type: 'SET', field: 'archiveDialogSessionId', value: sid })
  }, [dispatch])

  const focusSessionMenuTrigger = useCallback((sessionId: string) => {
    const sid = String(sessionId || '').trim()
    if (!sid) return
    const domSafe = sid.replace(/[^a-zA-Z0-9_-]/g, '_')
    const triggerId = `student-session-menu-${domSafe}-trigger`
    window.setTimeout(() => { (document.getElementById(triggerId) as HTMLButtonElement | null)?.focus?.() }, 0)
  }, [])

  const cancelRenameDialog = useCallback(() => {
    const sid = renameDialogSessionId
    dispatch({ type: 'BATCH', actions: [
      { type: 'SET', field: 'renameDialogSessionId', value: null },
      { type: 'SET', field: 'openSessionMenuId', value: '' },
    ]})
    if (sid) focusSessionMenuTrigger(sid)
  }, [focusSessionMenuTrigger, renameDialogSessionId, dispatch])

  const confirmRenameDialog = useCallback((nextTitle: string) => {
    const sid = renameDialogSessionId
    if (!sid) return
    const title = String(nextTitle || '').trim()
    dispatch({ type: 'UPDATE_SESSION_TITLE_MAP', updater: (prev) => {
      const next = { ...prev }
      if (title) next[sid] = title
      else delete next[sid]
      return next
    }})
    dispatch({ type: 'BATCH', actions: [
      { type: 'SET', field: 'renameDialogSessionId', value: null },
      { type: 'SET', field: 'openSessionMenuId', value: '' },
    ]})
    focusSessionMenuTrigger(sid)
  }, [focusSessionMenuTrigger, renameDialogSessionId, dispatch])

  const cancelArchiveDialog = useCallback(() => {
    dispatch({ type: 'SET', field: 'archiveDialogSessionId', value: null })
  }, [dispatch])

  const confirmArchiveDialog = useCallback(() => {
    const sid = archiveDialogSessionId
    if (!sid) return
    const isArchived = deletedSessionIds.includes(sid)
    dispatch({ type: 'BATCH', actions: [
      { type: 'SET', field: 'archiveDialogSessionId', value: null },
      { type: 'SET', field: 'openSessionMenuId', value: '' },
    ]})
    dispatch({ type: 'UPDATE_DELETED_SESSION_IDS', updater: (prev) => {
      if (isArchived) return prev.filter((id) => id !== sid)
      if (prev.includes(sid)) return prev
      return [...prev, sid]
    }})
    focusSessionMenuTrigger(sid)
    if (!isArchived && activeSessionId === sid) {
      const next = visibleSessions.find((item) => item.session_id !== sid)?.session_id
      if (next) {
        setActiveSession(next)
        dispatch({ type: 'BATCH', actions: [
          { type: 'SET', field: 'sessionCursor', value: -1 },
          { type: 'SET', field: 'sessionHasMore', value: false },
          { type: 'SET', field: 'sessionError', value: '' },
        ]})
      } else {
        startNewStudentSession()
      }
    }
  }, [activeSessionId, archiveDialogSessionId, deletedSessionIds, focusSessionMenuTrigger, visibleSessions, setActiveSession, startNewStudentSession, dispatch])

  const { archiveDialogIsArchived, archiveDialogActionLabel } = selectArchiveDialogMeta(
    archiveDialogSessionId,
    deletedSessionIds,
  )

  return {
    refreshSessions,
    loadSessionMessages,
    getSessionTitle,
    visibleSessions,
    groupedSessions,
    selectStudentSession,
    resetVerification,
    startNewStudentSession,
    renameSession,
    toggleSessionArchive,
    cancelRenameDialog,
    confirmRenameDialog,
    cancelArchiveDialog,
    confirmArchiveDialog,
    archiveDialogIsArchived,
    archiveDialogActionLabel,
  }
}
