import { useEffect, type Dispatch, type MutableRefObject } from 'react'
import { makeId } from '../../../shared/id'
import { safeLocalStorageGetItem, safeLocalStorageRemoveItem, safeLocalStorageSetItem } from '../../../shared/storage'
import { nowTime } from '../../../shared/time'
import { startVisibilityAwareBackoffPolling } from '../../../shared/visibilityBackoffPolling'
import { stripTransientPendingBubbles } from '../features/chat/pendingOverlay'
import { parsePendingChatJobFromStorage, PENDING_CHAT_MAX_AGE_MS } from '../features/chat/pendingChatJob'
import { clearStudentAccessToken } from '../features/auth/studentAuth'
import type { ChatJobStatus, PendingChatJob, VerifiedStudent } from '../appTypes'
import {
  normalizeRecentCompletedReplies,
  parseRecentCompletedReplies,
  PENDING_CHAT_KEY_PREFIX,
  RECENT_COMPLETION_KEY_PREFIX,
  recentCompletionKeyOf,
  RECENT_COMPLETION_TTL_MS,
  toErrorMessage,
  type RecentCompletedReply,
  type StudentAction,
  type StudentState,
} from './useStudentState'

type Refs = {
  pendingChatJobRef: MutableRefObject<PendingChatJob | null>
  recentCompletedRepliesRef: MutableRefObject<RecentCompletedReply[]>
  pendingRecoveredFromStorageRef: MutableRefObject<boolean>
  skipAutoSessionLoadIdRef: MutableRefObject<string>
}

type UseChatPollingParams = {
  state: StudentState
  dispatch: Dispatch<StudentAction>
  refs: Refs
  setActiveSession: (sessionId: string) => void
  refreshSessions: () => Promise<void>
}

export function useChatPolling({ state, dispatch, refs, setActiveSession, refreshSessions }: UseChatPollingParams) {
  const { apiBase, verifiedStudent, pendingChatJob, activeSessionId } = state
  const { pendingChatJobRef, recentCompletedRepliesRef, pendingRecoveredFromStorageRef, skipAutoSessionLoadIdRef } = refs

  // Sync refs
  useEffect(() => { pendingChatJobRef.current = pendingChatJob }, [pendingChatJob, pendingChatJobRef])
  useEffect(() => { recentCompletedRepliesRef.current = state.recentCompletedReplies }, [state.recentCompletedReplies, recentCompletedRepliesRef])

  // Persist verified student
  useEffect(() => {
    if (verifiedStudent) safeLocalStorageSetItem('verifiedStudent', JSON.stringify(verifiedStudent))
    else safeLocalStorageRemoveItem('verifiedStudent')
  }, [verifiedStudent])

  useEffect(() => {
    if (verifiedStudent) dispatch({ type: 'SET', field: 'verifyOpen', value: false })
  }, [verifiedStudent, dispatch])

  // Persist apiBase
  useEffect(() => { safeLocalStorageSetItem('apiBaseStudent', apiBase) }, [apiBase])

  // Persist sidebarOpen
  useEffect(() => { safeLocalStorageSetItem('studentSidebarOpen', state.sidebarOpen ? 'true' : 'false') }, [state.sidebarOpen])

  // Recover pending from storage on student change
  useEffect(() => {
    const sid = verifiedStudent?.student_id?.trim() || ''
    if (!sid) { pendingRecoveredFromStorageRef.current = false; dispatch({ type: 'SET', field: 'pendingChatJob', value: null }); return }
    const key = `${PENDING_CHAT_KEY_PREFIX}${sid}`
    const raw = safeLocalStorageGetItem(key)
    if (!raw) { pendingRecoveredFromStorageRef.current = false; dispatch({ type: 'SET', field: 'pendingChatJob', value: null }); return }
    const parsed = parsePendingChatJobFromStorage(raw)
    if (!parsed) { safeLocalStorageRemoveItem(key); pendingRecoveredFromStorageRef.current = false; dispatch({ type: 'SET', field: 'pendingChatJob', value: null }); return }
    pendingRecoveredFromStorageRef.current = Boolean(parsed.job_id)
    dispatch({ type: 'SET', field: 'pendingChatJob', value: parsed })
  }, [verifiedStudent?.student_id, pendingRecoveredFromStorageRef, dispatch])

  // Recover recent completed replies
  useEffect(() => {
    const sid = verifiedStudent?.student_id?.trim() || ''
    if (!sid) { dispatch({ type: 'SET', field: 'recentCompletedReplies', value: [] }); return }
    const key = `${RECENT_COMPLETION_KEY_PREFIX}${sid}`
    const recentReplies = parseRecentCompletedReplies(safeLocalStorageGetItem(key))
    if (!recentReplies.length) { safeLocalStorageRemoveItem(key); dispatch({ type: 'SET', field: 'recentCompletedReplies', value: [] }); return }
    dispatch({ type: 'SET', field: 'recentCompletedReplies', value: recentReplies })
  }, [verifiedStudent?.student_id, dispatch])

  // Persist pending chat job
  useEffect(() => {
    const sid = verifiedStudent?.student_id?.trim() || ''
    if (!sid) return
    const key = `${PENDING_CHAT_KEY_PREFIX}${sid}`
    try {
      if (pendingChatJob) safeLocalStorageSetItem(key, JSON.stringify(pendingChatJob))
      else safeLocalStorageRemoveItem(key)
    } catch { /* ignore */ }
  }, [pendingChatJob, verifiedStudent?.student_id])

  // Persist recent completed replies
  useEffect(() => {
    const sid = verifiedStudent?.student_id?.trim() || ''
    if (!sid) return
    const key = `${RECENT_COMPLETION_KEY_PREFIX}${sid}`
    try {
      if (state.recentCompletedReplies.length) safeLocalStorageSetItem(key, JSON.stringify(state.recentCompletedReplies))
      else safeLocalStorageRemoveItem(key)
    } catch { /* ignore */ }
  }, [state.recentCompletedReplies, verifiedStudent?.student_id])

  // Cross-tab localStorage sync
  useEffect(() => {
    if (typeof window === 'undefined') return
    const sid = verifiedStudent?.student_id?.trim() || ''

    const samePendingJob = (a: PendingChatJob | null, b: PendingChatJob | null) => {
      if (!a && !b) return true
      if (!a || !b) return false
      return a.job_id === b.job_id && a.request_id === b.request_id && a.placeholder_id === b.placeholder_id && a.user_text === b.user_text && a.session_id === b.session_id && Number(a.created_at) === Number(b.created_at)
    }

    const sameRecentReplies = (a: RecentCompletedReply[], b: RecentCompletedReply[]) => {
      if (a.length !== b.length) return false
      for (let i = 0; i < a.length; i++) { if (recentCompletionKeyOf(a[i]) !== recentCompletionKeyOf(b[i])) return false }
      return true
    }

    const clearVerifiedState = () => {
      clearStudentAccessToken()
      dispatch({ type: 'BATCH', actions: [
        { type: 'SET', field: 'verifiedStudent', value: null },
        { type: 'SET', field: 'verifyOpen', value: true },
        { type: 'SET', field: 'pendingChatJob', value: null },
        { type: 'SET', field: 'recentCompletedReplies', value: [] },
        { type: 'SET', field: 'sending', value: false },
      ]})
      pendingRecoveredFromStorageRef.current = false
    }

    const syncFromStorageSnapshot = () => {
      const rawVerified = safeLocalStorageGetItem('verifiedStudent')
      if (!rawVerified) { clearVerifiedState(); return }
      let parsedVerified: VerifiedStudent
      try { parsedVerified = JSON.parse(rawVerified) as VerifiedStudent } catch { clearVerifiedState(); return }
      const nextSid = String(parsedVerified?.student_id || '').trim()
      if (!nextSid) { clearVerifiedState(); return }
      if (nextSid !== sid) { dispatch({ type: 'SET', field: 'verifiedStudent', value: parsedVerified }); return }

      const pendingKey = `${PENDING_CHAT_KEY_PREFIX}${sid}`
      let nextPending: PendingChatJob | null = null
      const rawPending = safeLocalStorageGetItem(pendingKey)
      if (rawPending) { nextPending = parsePendingChatJobFromStorage(rawPending); if (!nextPending) safeLocalStorageRemoveItem(pendingKey) }
      if (!samePendingJob(pendingChatJobRef.current, nextPending)) {
        pendingRecoveredFromStorageRef.current = Boolean(nextPending?.job_id)
        dispatch({ type: 'SET', field: 'pendingChatJob', value: nextPending })
        if (!nextPending) dispatch({ type: 'SET', field: 'sending', value: false })
      }

      const recentKey = `${RECENT_COMPLETION_KEY_PREFIX}${sid}`
      const nextRecentReplies = parseRecentCompletedReplies(safeLocalStorageGetItem(recentKey))
      if (!nextRecentReplies.length) safeLocalStorageRemoveItem(recentKey)
      if (!sameRecentReplies(recentCompletedRepliesRef.current, nextRecentReplies)) {
        dispatch({ type: 'SET', field: 'recentCompletedReplies', value: nextRecentReplies })
      }
    }

    const handleStorage = (event: StorageEvent) => {
      if (event.storageArea && event.storageArea !== window.localStorage) return
      const pendingKey = sid ? `${PENDING_CHAT_KEY_PREFIX}${sid}` : ''
      const recentKey = sid ? `${RECENT_COMPLETION_KEY_PREFIX}${sid}` : ''
      if (event.key && event.key !== 'verifiedStudent' && event.key !== pendingKey && event.key !== recentKey) return
      syncFromStorageSnapshot()
    }

    syncFromStorageSnapshot()
    window.addEventListener('storage', handleStorage)
    window.addEventListener('focus', syncFromStorageSnapshot)
    document.addEventListener('visibilitychange', syncFromStorageSnapshot)
    const syncTimer = window.setInterval(syncFromStorageSnapshot, 1200)
    return () => {
      window.removeEventListener('storage', handleStorage)
      window.removeEventListener('focus', syncFromStorageSnapshot)
      document.removeEventListener('visibilitychange', syncFromStorageSnapshot)
      window.clearInterval(syncTimer)
    }
  }, [verifiedStudent?.student_id, pendingChatJobRef, recentCompletedRepliesRef, pendingRecoveredFromStorageRef, dispatch])

  // Inject pending bubbles when pending job changes
  useEffect(() => {
    if (!pendingChatJob?.job_id) return
    if (!activeSessionId || pendingChatJob.session_id !== activeSessionId) return
    dispatch({ type: 'UPDATE_MESSAGES', updater: (prev) => {
      const base = stripTransientPendingBubbles(prev)
      const hasUserText = pendingChatJob.user_text ? base.some((m) => m.role === 'user' && m.content === pendingChatJob.user_text) : true
      const hasPlaceholder = base.some((m) => m.id === pendingChatJob.placeholder_id)
      const next = [...base]
      if (!hasUserText && pendingChatJob.user_text) next.push({ id: makeId(), role: 'user' as const, content: pendingChatJob.user_text, time: nowTime() })
      if (!hasPlaceholder) next.push({ id: pendingChatJob.placeholder_id, role: 'assistant' as const, content: '正在回复中…', time: nowTime() })
      return next
    }})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeSessionId, pendingChatJob?.job_id, pendingChatJob?.session_id, dispatch])

  // Main polling effect
  useEffect(() => {
    if (!pendingChatJob?.job_id) return
    const cleanup = startVisibilityAwareBackoffPolling(
      async () => {
        const pendingAgeMs = Date.now() - Number(pendingChatJob.created_at || 0)
        if (!Number.isFinite(pendingAgeMs) || pendingAgeMs > PENDING_CHAT_MAX_AGE_MS) {
          const staleMsg = '上一条请求已过期，请重新发送。'
          dispatch({ type: 'UPDATE_MESSAGES', updater: (prev) => {
            const base = stripTransientPendingBubbles(prev)
            const hasPlaceholder = base.some((item) => item.id === pendingChatJob.placeholder_id)
            if (!hasPlaceholder) return base
            return base.map((item) => item.id === pendingChatJob.placeholder_id ? { ...item, content: staleMsg, time: nowTime() } : item)
          }})
          skipAutoSessionLoadIdRef.current = pendingChatJob.session_id || ''
          dispatch({ type: 'BATCH', actions: [{ type: 'SET', field: 'pendingChatJob', value: null }, { type: 'SET', field: 'sending', value: false }] })
          return 'stop'
        }
        if (pendingChatJob.session_id && activeSessionId && pendingChatJob.session_id !== activeSessionId) return 'continue'
        const res = await fetch(`${apiBase}/chat/status?job_id=${encodeURIComponent(pendingChatJob.job_id)}`)
        if (res.status === 404) {
          dispatch({ type: 'UPDATE_MESSAGES', updater: (prev) => stripTransientPendingBubbles(prev) })
          skipAutoSessionLoadIdRef.current = pendingChatJob.session_id || ''
          dispatch({ type: 'BATCH', actions: [{ type: 'SET', field: 'pendingChatJob', value: null }, { type: 'SET', field: 'sending', value: false }] })
          return 'stop'
        }
        if (!res.ok) { const text = await res.text(); throw new Error(text || `状态码 ${res.status}`) }
        const data = (await res.json()) as ChatJobStatus
        if (data.status === 'done') {
          const resolvedReply = data.reply || '已收到。'
          dispatch({ type: 'UPDATE_MESSAGES', updater: (prev) => {
            const base = stripTransientPendingBubbles(prev)
            const hasUserText = pendingChatJob.user_text ? base.some((m) => m.role === 'user' && m.content === pendingChatJob.user_text) : true
            const hasPlaceholder = base.some((m) => m.id === pendingChatJob.placeholder_id)
            const next = [...base]
            if (!hasUserText && pendingChatJob.user_text) next.push({ id: makeId(), role: 'user' as const, content: pendingChatJob.user_text, time: nowTime() })
            if (!hasPlaceholder) next.push({ id: pendingChatJob.placeholder_id, role: 'assistant' as const, content: '正在回复中…', time: nowTime() })
            return next.map((m) => m.id === pendingChatJob.placeholder_id ? { ...m, content: resolvedReply, time: nowTime() } : m)
          }})
          if (pendingChatJob.session_id) {
            const nextRecent: RecentCompletedReply = { session_id: pendingChatJob.session_id, user_text: pendingChatJob.user_text || '', reply_text: resolvedReply, completed_at: Date.now() }
            dispatch({ type: 'UPDATE_RECENT_COMPLETED_REPLIES', updater: (prev) => normalizeRecentCompletedReplies([...prev, nextRecent]) })
          }
          skipAutoSessionLoadIdRef.current = pendingChatJob.session_id || ''
          dispatch({ type: 'BATCH', actions: [{ type: 'SET', field: 'pendingChatJob', value: null }, { type: 'SET', field: 'sending', value: false }] })
          void refreshSessions()
          return 'stop'
        }
        if (data.status === 'failed' || data.status === 'cancelled') {
          const msg = data.error_detail || data.error || '请求失败'
          dispatch({ type: 'UPDATE_MESSAGES', updater: (prev) => {
            const base = stripTransientPendingBubbles(prev)
            const hasUserText = pendingChatJob.user_text ? base.some((m) => m.role === 'user' && m.content === pendingChatJob.user_text) : true
            const hasPlaceholder = base.some((m) => m.id === pendingChatJob.placeholder_id)
            const next = [...base]
            if (!hasUserText && pendingChatJob.user_text) next.push({ id: makeId(), role: 'user' as const, content: pendingChatJob.user_text, time: nowTime() })
            if (!hasPlaceholder) next.push({ id: pendingChatJob.placeholder_id, role: 'assistant' as const, content: '正在回复中…', time: nowTime() })
            return next.map((m) => m.id === pendingChatJob.placeholder_id ? { ...m, content: `抱歉，请求失败：${msg}`, time: nowTime() } : m)
          }})
          skipAutoSessionLoadIdRef.current = pendingChatJob.session_id || ''
          dispatch({ type: 'BATCH', actions: [{ type: 'SET', field: 'pendingChatJob', value: null }, { type: 'SET', field: 'sending', value: false }] })
          return 'stop'
        }
        return 'continue'
      },
      (err) => {
        const msg = toErrorMessage(err)
        dispatch({ type: 'UPDATE_MESSAGES', updater: (prev) => {
          const base = stripTransientPendingBubbles(prev)
          const hasUserText = pendingChatJob.user_text ? base.some((m) => m.role === 'user' && m.content === pendingChatJob.user_text) : true
          const hasPlaceholder = base.some((m) => m.id === pendingChatJob.placeholder_id)
          const next = [...base]
          if (!hasUserText && pendingChatJob.user_text) next.push({ id: makeId(), role: 'user' as const, content: pendingChatJob.user_text, time: nowTime() })
          if (!hasPlaceholder) next.push({ id: pendingChatJob.placeholder_id, role: 'assistant' as const, content: '正在回复中…', time: nowTime() })
          return next.map((m) => m.id === pendingChatJob.placeholder_id ? { ...m, content: `网络波动，正在重试…（${msg}）`, time: nowTime() } : m)
        }})
      },
      { kickMode: 'direct' },
    )
    return cleanup
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingChatJob?.job_id, activeSessionId, apiBase, dispatch])

  // Recover pending session on storage recovery
  useEffect(() => {
    if (!pendingChatJob?.job_id) return
    if (!pendingRecoveredFromStorageRef.current) return
    pendingRecoveredFromStorageRef.current = false
    if (pendingChatJob.session_id && pendingChatJob.session_id !== activeSessionId) {
      setActiveSession(pendingChatJob.session_id)
    }
  }, [activeSessionId, pendingChatJob?.job_id, pendingChatJob?.session_id, setActiveSession, pendingRecoveredFromStorageRef])
}
