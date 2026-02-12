import { useCallback, useMemo, type Dispatch, type MutableRefObject, type SetStateAction } from 'react'
import { sessionGroupFromIso, sessionGroupOrder } from '../../../../shared/sessionGrouping'
import { makeId } from '../../../../shared/id'
import { nowTime } from '../../../../shared/time'
import type { Message, PendingChatJob, SessionGroup, StudentHistorySession, VerifiedStudent } from '../../appTypes'

type UseStudentSessionActionsParams = {
  sessions: StudentHistorySession[]
  deletedSessionIds: string[]
  historyQuery: string
  sessionTitleMap: Record<string, string>
  showArchivedSessions: boolean
  activeSessionId: string
  renameDialogSessionId: string | null
  archiveDialogSessionId: string | null
  sessionRequestRef: MutableRefObject<number>
  todayDate: () => string
  newSessionMessage: string

  setSidebarOpen: Dispatch<SetStateAction<boolean>>
  setForceSessionLoadToken: Dispatch<SetStateAction<number>>
  setActiveSession: (sessionId: string) => void
  setSessionCursor: (value: number) => void
  setSessionHasMore: (value: boolean) => void
  setSessionError: (value: string) => void
  setOpenSessionMenuId: (value: string) => void
  setVerifiedStudent: Dispatch<SetStateAction<VerifiedStudent | null>>
  setNameInput: (value: string) => void
  setClassInput: (value: string) => void
  setVerifyError: (value: string) => void
  setVerifyOpen: (value: boolean) => void
  setLocalDraftSessionIds: Dispatch<SetStateAction<string[]>>
  setShowArchivedSessions: Dispatch<SetStateAction<boolean>>
  setPendingChatJob: (value: PendingChatJob | null) => void
  setSending: (value: boolean) => void
  setInput: (value: string) => void
  setSessions: Dispatch<SetStateAction<StudentHistorySession[]>>
  setMessages: Dispatch<SetStateAction<Message[]>>
  setRenameDialogSessionId: (value: string | null) => void
  setArchiveDialogSessionId: (value: string | null) => void
  setSessionTitleMap: Dispatch<SetStateAction<Record<string, string>>>
  setDeletedSessionIds: Dispatch<SetStateAction<string[]>>
}

export function useStudentSessionActions(params: UseStudentSessionActionsParams) {
  const {
    sessions,
    deletedSessionIds,
    historyQuery,
    sessionTitleMap,
    showArchivedSessions,
    activeSessionId,
    renameDialogSessionId,
    archiveDialogSessionId,
    sessionRequestRef,
    todayDate,
    newSessionMessage,
    setSidebarOpen,
    setForceSessionLoadToken,
    setActiveSession,
    setSessionCursor,
    setSessionHasMore,
    setSessionError,
    setOpenSessionMenuId,
    setVerifiedStudent,
    setNameInput,
    setClassInput,
    setVerifyError,
    setVerifyOpen,
    setLocalDraftSessionIds,
    setShowArchivedSessions,
    setPendingChatJob,
    setSending,
    setInput,
    setSessions,
    setMessages,
    setRenameDialogSessionId,
    setArchiveDialogSessionId,
    setSessionTitleMap,
    setDeletedSessionIds,
  } = params

  const getSessionTitle = useCallback(
    (sessionId: string) => {
      const sid = String(sessionId || '').trim()
      if (!sid) return '未命名会话'
      return sessionTitleMap[sid] || sid
    },
    [sessionTitleMap],
  )

  const visibleSessions = useMemo(() => {
    const archived = new Set(deletedSessionIds)
    const q = historyQuery.trim().toLowerCase()
    return sessions.filter((item) => {
      const sid = String(item.session_id || '').trim()
      if (!sid) return false
      const title = (sessionTitleMap[sid] || '').toLowerCase()
      const preview = (item.preview || '').toLowerCase()
      const matched = !q || sid.toLowerCase().includes(q) || title.includes(q) || preview.includes(q)
      if (!matched) return false
      return showArchivedSessions ? archived.has(sid) : !archived.has(sid)
    })
  }, [sessions, deletedSessionIds, historyQuery, sessionTitleMap, showArchivedSessions])

  const groupedSessions = useMemo(() => {
    const buckets = new Map<string, SessionGroup<StudentHistorySession>>()
    for (const item of visibleSessions) {
      const info = sessionGroupFromIso(item.updated_at)
      const existing = buckets.get(info.key)
      if (existing) {
        existing.items.push(item)
      } else {
        buckets.set(info.key, { key: info.key, label: info.label, items: [item] })
      }
    }
    return Array.from(buckets.values()).sort((a, b) => {
      const oa = sessionGroupOrder[a.key] ?? 99
      const ob = sessionGroupOrder[b.key] ?? 99
      if (oa !== ob) return oa - ob
      return a.label.localeCompare(b.label)
    })
  }, [visibleSessions])

  const closeSidebarOnMobile = useCallback(() => {
    if (typeof window === 'undefined') return
    if (window.matchMedia('(max-width: 900px)').matches) {
      setSidebarOpen(false)
    }
  }, [setSidebarOpen])

  const selectStudentSession = useCallback(
    (sessionId: string) => {
      const sid = String(sessionId || '').trim()
      if (!sid) return
      setForceSessionLoadToken((prev) => prev + 1)
      setActiveSession(sid)
      setSessionCursor(-1)
      setSessionHasMore(false)
      setSessionError('')
      setOpenSessionMenuId('')
      closeSidebarOnMobile()
    },
    [
      closeSidebarOnMobile,
      setForceSessionLoadToken,
      setActiveSession,
      setSessionCursor,
      setSessionHasMore,
      setSessionError,
      setOpenSessionMenuId,
    ],
  )

  const resetVerification = useCallback(() => {
    setVerifiedStudent(null)
    setNameInput('')
    setClassInput('')
    setVerifyError('')
    setVerifyOpen(true)
  }, [setVerifiedStudent, setNameInput, setClassInput, setVerifyError, setVerifyOpen])

  const startNewStudentSession = useCallback(() => {
    const next = `general_${todayDate()}_${Math.random().toString(16).slice(2, 6)}`
    sessionRequestRef.current += 1
    setLocalDraftSessionIds((prev) => (prev.includes(next) ? prev : [next, ...prev]))
    setShowArchivedSessions(false)
    setActiveSession(next)
    setSessionCursor(-1)
    setSessionHasMore(false)
    setSessionError('')
    setOpenSessionMenuId('')
    setPendingChatJob(null)
    setSending(false)
    setInput('')
    setSessions((prev) => {
      if (prev.some((item) => item.session_id === next)) return prev
      const nowIso = new Date().toISOString()
      return [
        { session_id: next, updated_at: nowIso, message_count: 0, preview: '' },
        ...prev,
      ]
    })
    setMessages([
      {
        id: makeId(),
        role: 'assistant',
        content: newSessionMessage,
        time: nowTime(),
      },
    ])
    closeSidebarOnMobile()
  }, [
    closeSidebarOnMobile,
    todayDate,
    sessionRequestRef,
    setLocalDraftSessionIds,
    setShowArchivedSessions,
    setActiveSession,
    setSessionCursor,
    setSessionHasMore,
    setSessionError,
    setOpenSessionMenuId,
    setPendingChatJob,
    setSending,
    setInput,
    setSessions,
    setMessages,
    newSessionMessage,
  ])

  const renameSession = useCallback(
    (sessionId: string) => {
      const sid = String(sessionId || '').trim()
      if (!sid) return
      setRenameDialogSessionId(sid)
    },
    [setRenameDialogSessionId],
  )

  const toggleSessionArchive = useCallback(
    (sessionId: string) => {
      const sid = String(sessionId || '').trim()
      if (!sid) return
      setArchiveDialogSessionId(sid)
    },
    [setArchiveDialogSessionId],
  )

  const focusSessionMenuTrigger = useCallback((sessionId: string) => {
    const sid = String(sessionId || '').trim()
    if (!sid) return
    const domSafe = sid.replace(/[^a-zA-Z0-9_-]/g, '_')
    const triggerId = `student-session-menu-${domSafe}-trigger`
    window.setTimeout(() => {
      const node = document.getElementById(triggerId) as HTMLButtonElement | null
      node?.focus?.()
    }, 0)
  }, [])

  const cancelRenameDialog = useCallback(() => {
    const sid = renameDialogSessionId
    setRenameDialogSessionId(null)
    setOpenSessionMenuId('')
    if (sid) focusSessionMenuTrigger(sid)
  }, [focusSessionMenuTrigger, renameDialogSessionId, setRenameDialogSessionId, setOpenSessionMenuId])

  const confirmRenameDialog = useCallback(
    (nextTitle: string) => {
      const sid = renameDialogSessionId
      if (!sid) return
      const title = String(nextTitle || '').trim()
      setSessionTitleMap((prev) => {
        const next = { ...prev }
        if (title) next[sid] = title
        else delete next[sid]
        return next
      })
      setRenameDialogSessionId(null)
      setOpenSessionMenuId('')
      focusSessionMenuTrigger(sid)
    },
    [focusSessionMenuTrigger, renameDialogSessionId, setSessionTitleMap, setRenameDialogSessionId, setOpenSessionMenuId],
  )

  const cancelArchiveDialog = useCallback(() => {
    setArchiveDialogSessionId(null)
  }, [setArchiveDialogSessionId])

  const confirmArchiveDialog = useCallback(() => {
    const sid = archiveDialogSessionId
    if (!sid) return
    const isArchived = deletedSessionIds.includes(sid)
    setArchiveDialogSessionId(null)
    setOpenSessionMenuId('')
    setDeletedSessionIds((prev) => {
      if (isArchived) return prev.filter((id) => id !== sid)
      if (prev.includes(sid)) return prev
      return [...prev, sid]
    })
    focusSessionMenuTrigger(sid)
    if (!isArchived && activeSessionId === sid) {
      const next = visibleSessions.find((item) => item.session_id !== sid)?.session_id
      if (next) {
        setActiveSession(next)
        setSessionCursor(-1)
        setSessionHasMore(false)
        setSessionError('')
      } else {
        startNewStudentSession()
      }
    }
  }, [
    activeSessionId,
    archiveDialogSessionId,
    deletedSessionIds,
    setArchiveDialogSessionId,
    setOpenSessionMenuId,
    setDeletedSessionIds,
    focusSessionMenuTrigger,
    visibleSessions,
    setActiveSession,
    setSessionCursor,
    setSessionHasMore,
    setSessionError,
    startNewStudentSession,
  ])

  const archiveDialogIsArchived = archiveDialogSessionId ? deletedSessionIds.includes(archiveDialogSessionId) : false
  const archiveDialogActionLabel = archiveDialogIsArchived ? '恢复' : '归档'

  return {
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
