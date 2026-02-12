import { useCallback, useMemo } from 'react'
import { sessionGroupFromIso, sessionGroupOrder } from '../../../../shared/sessionGrouping'
import type { SessionGroup, TeacherHistorySession } from '../../appTypes'

type UseTeacherSessionSidebarModelParams = {
  historySessions: TeacherHistorySession[]
  deletedSessionIds: string[]
  historyQuery: string
  sessionTitleMap: Record<string, string>
  showArchivedSessions: boolean
  archiveDialogSessionId: string | null
}

export function useTeacherSessionSidebarModel(params: UseTeacherSessionSidebarModelParams) {
  const {
    historySessions,
    deletedSessionIds,
    historyQuery,
    sessionTitleMap,
    showArchivedSessions,
    archiveDialogSessionId,
  } = params

  const visibleHistorySessions = useMemo(() => {
    const archived = new Set(deletedSessionIds)
    const q = historyQuery.trim().toLowerCase()
    return historySessions.filter((item) => {
      const sid = String(item.session_id || '').trim()
      if (!sid) return false
      const title = (sessionTitleMap[sid] || '').toLowerCase()
      const preview = (item.preview || '').toLowerCase()
      const matched = !q || sid.toLowerCase().includes(q) || title.includes(q) || preview.includes(q)
      if (!matched) return false
      return showArchivedSessions ? archived.has(sid) : !archived.has(sid)
    })
  }, [historySessions, deletedSessionIds, historyQuery, sessionTitleMap, showArchivedSessions])

  const groupedHistorySessions = useMemo(() => {
    const buckets = new Map<string, SessionGroup<TeacherHistorySession>>()
    for (const item of visibleHistorySessions) {
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
  }, [visibleHistorySessions])

  const getSessionTitle = useCallback(
    (sessionId: string) => {
      const sid = String(sessionId || '').trim()
      if (!sid) return '未命名会话'
      return sessionTitleMap[sid] || sid
    },
    [sessionTitleMap],
  )

  const archiveDialogIsArchived = archiveDialogSessionId ? deletedSessionIds.includes(archiveDialogSessionId) : false
  const archiveDialogActionLabel = archiveDialogIsArchived ? '恢复' : '归档'

  return {
    visibleHistorySessions,
    groupedHistorySessions,
    getSessionTitle,
    archiveDialogIsArchived,
    archiveDialogActionLabel,
  }
}
