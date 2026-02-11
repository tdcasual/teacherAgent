import { useCallback } from 'react'
import type { Message, PendingChatJob, TeacherHistorySession } from '../../appTypes'
import { makeId } from '../../utils/id'
import { nowTime } from '../../utils/time'
import { TEACHER_GREETING } from './catalog'

export type UseSessionActionsDeps = {
  /** Ref whose `.current` is incremented to cancel in-flight session requests. */
  sessionRequestRef: React.MutableRefObject<number>
  /** Visible (non-archived) history sessions used by confirmArchiveDialog. */
  visibleHistorySessions: TeacherHistorySession[]

  // --- state values read by action callbacks ---
  activeSessionId: string
  renameDialogSessionId: string | null
  archiveDialogSessionId: string | null
  deletedSessionIds: string[]

  // --- setters ---
  setLocalDraftSessionIds: (value: string[] | ((prev: string[]) => string[])) => void
  setShowArchivedSessions: (value: boolean | ((prev: boolean) => boolean)) => void
  setActiveSessionId: (value: string | ((prev: string) => string)) => void
  setSessionCursor: (value: number) => void
  setSessionHasMore: (value: boolean) => void
  setSessionError: (value: string) => void
  setOpenSessionMenuId: (value: string | ((prev: string) => string)) => void
  setPendingChatJob: (value: PendingChatJob | null) => void
  setSending: (value: boolean) => void
  setInput: (value: string) => void
  setChatQueueHint: (value: string) => void
  setHistorySessions: (
    value: TeacherHistorySession[] | ((prev: TeacherHistorySession[]) => TeacherHistorySession[]),
  ) => void
  setMessages: (value: Message[] | ((prev: Message[]) => Message[])) => void
  setRenameDialogSessionId: (value: string | null) => void
  setArchiveDialogSessionId: (value: string | null) => void
  setSessionTitleMap: (
    value: Record<string, string> | ((prev: Record<string, string>) => Record<string, string>),
  ) => void
  setDeletedSessionIds: (value: string[] | ((prev: string[]) => string[])) => void
  setSessionSidebarOpen: (value: boolean | ((prev: boolean) => boolean)) => void
  setSkillsOpen: (value: boolean | ((prev: boolean) => boolean)) => void

  /** Returns true when the viewport is at or below the mobile breakpoint. */
  isMobileViewport: () => boolean
}

export function useSessionActions(deps: UseSessionActionsDeps) {
  const {
    sessionRequestRef,
    visibleHistorySessions,
    activeSessionId,
    renameDialogSessionId,
    archiveDialogSessionId,
    deletedSessionIds,
    setLocalDraftSessionIds,
    setShowArchivedSessions,
    setActiveSessionId,
    setSessionCursor,
    setSessionHasMore,
    setSessionError,
    setOpenSessionMenuId,
    setPendingChatJob,
    setSending,
    setInput,
    setChatQueueHint,
    setHistorySessions,
    setMessages,
    setRenameDialogSessionId,
    setArchiveDialogSessionId,
    setSessionTitleMap,
    setDeletedSessionIds,
    setSessionSidebarOpen,
    setSkillsOpen,
    isMobileViewport,
  } = deps

  const closeSessionSidebarOnMobile = useCallback(() => {
    if (isMobileViewport()) {
      setSessionSidebarOpen(false)
    }
  }, [isMobileViewport, setSessionSidebarOpen])

  const toggleSessionSidebar = useCallback(() => {
    setSessionSidebarOpen((prev: boolean) => {
      const next = !prev
      if (next && isMobileViewport()) setSkillsOpen(false)
      return next
    })
  }, [isMobileViewport, setSessionSidebarOpen, setSkillsOpen])

  const startNewTeacherSession = useCallback(() => {
    const next = `session_${new Date().toISOString().slice(0, 10)}_${Math.random().toString(16).slice(2, 6)}`
    sessionRequestRef.current += 1
    setLocalDraftSessionIds((prev) => (prev.includes(next) ? prev : [next, ...prev]))
    setShowArchivedSessions(false)
    setActiveSessionId(next)
    setSessionCursor(-1)
    setSessionHasMore(false)
    setSessionError('')
    setOpenSessionMenuId('')
    setPendingChatJob(null)
    setSending(false)
    setInput('')
    setChatQueueHint('')
    setHistorySessions((prev) => {
      if (prev.some((item) => item.session_id === next)) return prev
      const nowIso = new Date().toISOString()
      return [{ session_id: next, updated_at: nowIso, message_count: 0, preview: '' }, ...prev]
    })
    setMessages([
      {
        id: makeId(),
        role: 'assistant',
        content: TEACHER_GREETING,
        time: nowTime(),
      },
    ])
    closeSessionSidebarOnMobile()
  }, [
    closeSessionSidebarOnMobile,
    sessionRequestRef,
    setLocalDraftSessionIds,
    setShowArchivedSessions,
    setActiveSessionId,
    setSessionCursor,
    setSessionHasMore,
    setSessionError,
    setOpenSessionMenuId,
    setPendingChatJob,
    setSending,
    setInput,
    setChatQueueHint,
    setHistorySessions,
    setMessages,
  ])

  const renameSession = useCallback(
    (sessionId: string) => {
      const sid = String(sessionId || '').trim()
      if (!sid) return
      setRenameDialogSessionId(sid)
    },
    [setRenameDialogSessionId],
  )

  const toggleSessionMenu = useCallback(
    (sessionId: string) => {
      const sid = String(sessionId || '').trim()
      if (!sid) return
      setOpenSessionMenuId((prev: string) => (prev === sid ? '' : sid))
    },
    [setOpenSessionMenuId],
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
    const triggerId = `teacher-session-menu-${domSafe}-trigger`
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
    const sid = archiveDialogSessionId
    setArchiveDialogSessionId(null)
    setOpenSessionMenuId('')
    if (sid) focusSessionMenuTrigger(sid)
  }, [archiveDialogSessionId, focusSessionMenuTrigger, setArchiveDialogSessionId, setOpenSessionMenuId])

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
      const nextSession = visibleHistorySessions.find((item) => item.session_id !== sid)?.session_id
      if (nextSession) {
        setActiveSessionId(nextSession)
        setSessionCursor(-1)
        setSessionHasMore(false)
        setSessionError('')
      } else {
        startNewTeacherSession()
      }
    }
  }, [
    activeSessionId,
    archiveDialogSessionId,
    deletedSessionIds,
    focusSessionMenuTrigger,
    setArchiveDialogSessionId,
    setOpenSessionMenuId,
    setDeletedSessionIds,
    setActiveSessionId,
    setSessionCursor,
    setSessionHasMore,
    setSessionError,
    startNewTeacherSession,
    visibleHistorySessions,
  ])

  return {
    startNewTeacherSession,
    renameSession,
    toggleSessionMenu,
    toggleSessionArchive,
    focusSessionMenuTrigger,
    cancelRenameDialog,
    confirmRenameDialog,
    cancelArchiveDialog,
    confirmArchiveDialog,
    closeSessionSidebarOnMobile,
    toggleSessionSidebar,
  }
}
