import { safeLocalStorageGetItem } from '../../../../shared/storage'

export const STUDENT_SESSION_VIEW_STATE_KEY_PREFIX = 'studentSessionViewState:'
export const STUDENT_LOCAL_DRAFT_SESSIONS_KEY_PREFIX = 'studentLocalDraftSessionIds:'

export type SessionViewStatePayload = {
  title_map: Record<string, string>
  hidden_ids: string[]
  active_session_id: string
  updated_at: string
}

const parseOptionalIso = (value?: string) => {
  const raw = String(value || '').trim()
  if (!raw) return null
  const ms = Date.parse(raw)
  return Number.isNaN(ms) ? null : ms
}

export const compareSessionViewStateUpdatedAt = (a?: string, b?: string) => {
  const ma = parseOptionalIso(a)
  const mb = parseOptionalIso(b)
  if (ma === null && mb === null) return 0
  if (ma === null) return -1
  if (mb === null) return 1
  return ma === mb ? 0 : ma > mb ? 1 : -1
}

export const normalizeSessionViewStatePayload = (raw: any): SessionViewStatePayload => {
  const titleRaw = raw && typeof raw === 'object' && raw.title_map && typeof raw.title_map === 'object' ? raw.title_map : {}
  const titleMap: Record<string, string> = {}
  for (const [key, value] of Object.entries(titleRaw)) {
    const sid = String(key || '').trim()
    const title = String(value || '').trim()
    if (!sid || !title) continue
    titleMap[sid] = title
  }
  const hiddenRaw: unknown[] = Array.isArray(raw?.hidden_ids) ? raw.hidden_ids : []
  const hiddenIds = Array.from(new Set(hiddenRaw.map((item: unknown) => String(item || '').trim()).filter(Boolean)))
  const activeSessionId = String(raw?.active_session_id || '').trim()
  const updatedAt = parseOptionalIso(raw?.updated_at) !== null ? String(raw?.updated_at) : ''
  return {
    title_map: titleMap,
    hidden_ids: hiddenIds,
    active_session_id: activeSessionId,
    updated_at: updatedAt,
  }
}

export const buildSessionViewStateSignature = (state: SessionViewStatePayload) => {
  const titleEntries = Object.entries(state.title_map).sort((a, b) => a[0].localeCompare(b[0]))
  const normalized = {
    title_map: Object.fromEntries(titleEntries),
    hidden_ids: [...state.hidden_ids],
    updated_at: state.updated_at || '',
  }
  return JSON.stringify(normalized)
}

export const readStudentLocalViewState = (studentId: string): SessionViewStatePayload => {
  const sid = String(studentId || '').trim()
  if (!sid) {
    return normalizeSessionViewStatePayload({
      title_map: {},
      hidden_ids: [],
      active_session_id: '',
      updated_at: new Date().toISOString(),
    })
  }
  try {
    const raw = safeLocalStorageGetItem(`${STUDENT_SESSION_VIEW_STATE_KEY_PREFIX}${sid}`)
    if (raw) {
      const parsed = normalizeSessionViewStatePayload(JSON.parse(raw))
      if (!parsed.active_session_id) {
        parsed.active_session_id = String(safeLocalStorageGetItem(`studentActiveSession:${sid}`) || '').trim()
      }
      if (parsed.updated_at) return parsed
    }
  } catch {
    // ignore
  }
  let titleMap: Record<string, string> = {}
  let hiddenIds: string[] = []
  const activeSessionId = String(safeLocalStorageGetItem(`studentActiveSession:${sid}`) || '').trim()
  try {
    const parsed = JSON.parse(safeLocalStorageGetItem(`studentSessionTitles:${sid}`) || '{}')
    if (parsed && typeof parsed === 'object') titleMap = parsed
  } catch {
    titleMap = {}
  }
  try {
    const parsed = JSON.parse(safeLocalStorageGetItem(`studentDeletedSessions:${sid}`) || '[]')
    if (Array.isArray(parsed)) hiddenIds = parsed.map((item) => String(item || '').trim()).filter(Boolean)
  } catch {
    hiddenIds = []
  }
  return normalizeSessionViewStatePayload({
    title_map: titleMap,
    hidden_ids: hiddenIds,
    active_session_id: activeSessionId,
    updated_at: new Date().toISOString(),
  })
}

export const readStudentLocalDraftSessionIds = (studentId: string): string[] => {
  const sid = String(studentId || '').trim()
  if (!sid) return []
  try {
    const raw = safeLocalStorageGetItem(`${STUDENT_LOCAL_DRAFT_SESSIONS_KEY_PREFIX}${sid}`)
    const parsed = raw ? JSON.parse(raw) : []
    if (!Array.isArray(parsed)) return []
    const cleaned = parsed.map((item) => String(item || '').trim()).filter(Boolean)
    return Array.from(new Set(cleaned))
  } catch {
    return []
  }
}
