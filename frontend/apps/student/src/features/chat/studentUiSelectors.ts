import { sessionGroupFromIso, sessionGroupOrder } from '../../../../shared/sessionGrouping'
import type { SessionGroup, StudentHistorySession, VerifiedStudent } from '../../appTypes'

type VisibleSessionsParams = {
  sessions: StudentHistorySession[]
  deletedSessionIds: string[]
  historyQuery: string
  sessionTitleMap: Record<string, string>
  showArchivedSessions: boolean
}

export const selectVisibleSessions = ({
  sessions,
  deletedSessionIds,
  historyQuery,
  sessionTitleMap,
  showArchivedSessions,
}: VisibleSessionsParams): StudentHistorySession[] => {
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
}

export const selectGroupedSessions = (
  visibleSessions: StudentHistorySession[],
): Array<SessionGroup<StudentHistorySession>> => {
  const buckets = new Map<string, SessionGroup<StudentHistorySession>>()
  for (const item of visibleSessions) {
    const info = sessionGroupFromIso(item.updated_at)
    const existing = buckets.get(info.key)
    if (existing) existing.items.push(item)
    else buckets.set(info.key, { key: info.key, label: info.label, items: [item] })
  }
  return Array.from(buckets.values()).sort((a, b) => {
    const oa = sessionGroupOrder[a.key] ?? 99
    const ob = sessionGroupOrder[b.key] ?? 99
    if (oa !== ob) return oa - ob
    return a.label.localeCompare(b.label)
  })
}

export const selectArchiveDialogMeta = (
  archiveDialogSessionId: string | null,
  deletedSessionIds: string[],
) => {
  const archiveDialogIsArchived = archiveDialogSessionId ? deletedSessionIds.includes(archiveDialogSessionId) : false
  return {
    archiveDialogIsArchived,
    archiveDialogActionLabel: archiveDialogIsArchived ? '恢复' : '归档',
  }
}

type ComposerHintParams = {
  verifiedStudent: VerifiedStudent | null
  pendingChatJobId: string
  sending: boolean
}

export const selectComposerHint = ({
  verifiedStudent,
  pendingChatJobId,
  sending,
}: ComposerHintParams): string => {
  if (!verifiedStudent) return '请先完成身份验证'
  if (pendingChatJobId) return '正在生成回复，请稍候…'
  if (sending) return '正在提交请求…'
  return 'Enter 发送 · Shift+Enter 换行'
}
