import { useCallback, useReducer, useRef } from 'react'
import { makeId } from '../../../shared/id'
import { safeLocalStorageGetItem } from '../../../shared/storage'
import { nowTime } from '../../../shared/time'
import { toUserFacingErrorMessage } from '../../../shared/errorMessage'
import { readStudentAccessToken } from '../features/auth/studentAuth'
import type {
  AssignmentDetail,
  Message,
  PendingChatJob,
  StudentPersonaCard,
  StudentHistorySession,
  VerifiedStudent,
} from '../appTypes'
import { parsePendingChatJobFromStorage } from '../features/chat/pendingChatJob'

export type RecentCompletedReply = {
  session_id: string
  user_text: string
  reply_text: string
  completed_at: number
}

export const PENDING_CHAT_KEY_PREFIX = 'studentPendingChatJob:'
export const RECENT_COMPLETION_KEY_PREFIX = 'studentRecentCompletion:'
export const RECENT_COMPLETION_TTL_MS = 3 * 60 * 1000
export const STUDENT_WELCOME_MESSAGE = '学生端已就绪。请先填写姓名完成验证，然后开始提问或进入作业讨论。'
export const STUDENT_NEW_SESSION_MESSAGE = '已开启新会话。你可以继续提问，或输入"开始今天作业"。'

const DEFAULT_API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const recentCompletionKeyOf = (item: RecentCompletedReply) =>
  `${item.session_id}::${item.completed_at}::${item.user_text}::${item.reply_text}`

export const normalizeRecentCompletedReplies = (items: RecentCompletedReply[]) => {
  const now = Date.now()
  const sorted = items
    .map((item) => ({
      session_id: String(item?.session_id || '').trim(),
      user_text: typeof item?.user_text === 'string' ? item.user_text : '',
      reply_text: typeof item?.reply_text === 'string' ? item.reply_text : '',
      completed_at: Number(item?.completed_at || 0),
    }))
    .filter((item) => item.session_id && item.reply_text && Number.isFinite(item.completed_at) && item.completed_at > 0)
    .filter((item) => now - item.completed_at <= RECENT_COMPLETION_TTL_MS)
    .sort((a, b) => a.completed_at - b.completed_at)
  const seen = new Set<string>()
  const deduped: RecentCompletedReply[] = []
  for (const item of sorted) {
    const key = recentCompletionKeyOf(item)
    if (seen.has(key)) continue
    seen.add(key)
    deduped.push(item)
  }
  return deduped.slice(-20)
}

export const parseRecentCompletedReplies = (raw: string | null): RecentCompletedReply[] => {
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw)
    if (Array.isArray(parsed)) {
      const items = parsed
        .map((entry: Partial<RecentCompletedReply>) => ({
          session_id: String(entry?.session_id || '').trim(),
          user_text: typeof entry?.user_text === 'string' ? entry.user_text : '',
          reply_text: typeof entry?.reply_text === 'string' ? entry.reply_text : '',
          completed_at: Number(entry?.completed_at || 0),
        }))
        .filter((entry) => entry.session_id && entry.reply_text && Number.isFinite(entry.completed_at) && entry.completed_at > 0)
      return normalizeRecentCompletedReplies(items)
    }
    const candidate = parsed as Partial<RecentCompletedReply>
    const legacyItem: RecentCompletedReply = {
      session_id: String(candidate?.session_id || '').trim(),
      user_text: typeof candidate?.user_text === 'string' ? candidate.user_text : '',
      reply_text: typeof candidate?.reply_text === 'string' ? candidate.reply_text : '',
      completed_at: Number(candidate?.completed_at || 0),
    }
    return normalizeRecentCompletedReplies([legacyItem])
  } catch {
    return []
  }
}

export const todayDate = () => new Date().toLocaleDateString('sv-SE')

export const isAbortError = (error: unknown): boolean => {
  if (error instanceof DOMException) return error.name === 'AbortError'
  if (!error || typeof error !== 'object') return false
  return (error as { name?: unknown }).name === 'AbortError'
}

export const toErrorMessage = (error: unknown, fallback = '请求失败') => {
  return toUserFacingErrorMessage(error, fallback)
}

export type StudentState = {
  apiBase: string
  verifiedStudent: VerifiedStudent | null
  verifyOpen: boolean
  nameInput: string
  classInput: string
  credentialInput: string
  credentialType: 'token' | 'password'
  newPasswordInput: string
  verifying: boolean
  settingPassword: boolean
  verifyError: string
  verifyInfo: string
  sessions: StudentHistorySession[]
  activeSessionId: string
  historyLoading: boolean
  historyError: string
  historyCursor: number
  historyHasMore: boolean
  historyQuery: string
  showArchivedSessions: boolean
  sessionTitleMap: Record<string, string>
  deletedSessionIds: string[]
  localDraftSessionIds: string[]
  sessionLoading: boolean
  sessionError: string
  sessionCursor: number
  sessionHasMore: boolean
  messages: Message[]
  input: string
  sending: boolean
  pendingChatJob: PendingChatJob | null
  recentCompletedReplies: RecentCompletedReply[]
  todayAssignment: AssignmentDetail | null
  assignmentLoading: boolean
  assignmentError: string
  sidebarOpen: boolean
  openSessionMenuId: string
  renameDialogSessionId: string | null
  archiveDialogSessionId: string | null
  forceSessionLoadToken: number
  personaEnabled: boolean
  personaPickerOpen: boolean
  activePersonaId: string
  personaCards: StudentPersonaCard[]
  personaLoading: boolean
  personaError: string
}

export type StudentAction =
  | { type: 'SET'; field: keyof StudentState; value: StudentState[keyof StudentState] }
  | { type: 'UPDATE_MESSAGES'; updater: (prev: Message[]) => Message[] }
  | { type: 'UPDATE_SESSIONS'; updater: (prev: StudentHistorySession[]) => StudentHistorySession[] }
  | { type: 'UPDATE_SESSION_TITLE_MAP'; updater: (prev: Record<string, string>) => Record<string, string> }
  | { type: 'UPDATE_DELETED_SESSION_IDS'; updater: (prev: string[]) => string[] }
  | { type: 'UPDATE_LOCAL_DRAFT_SESSION_IDS'; updater: (prev: string[]) => string[] }
  | { type: 'UPDATE_RECENT_COMPLETED_REPLIES'; updater: (prev: RecentCompletedReply[]) => RecentCompletedReply[] }
  | { type: 'BATCH'; actions: StudentAction[] }

function studentReducer(state: StudentState, action: StudentAction): StudentState {
  switch (action.type) {
    case 'SET':
      if (state[action.field] === action.value) return state
      return { ...state, [action.field]: action.value }
    case 'UPDATE_MESSAGES':
      return { ...state, messages: action.updater(state.messages) }
    case 'UPDATE_SESSIONS':
      return { ...state, sessions: action.updater(state.sessions) }
    case 'UPDATE_SESSION_TITLE_MAP':
      return { ...state, sessionTitleMap: action.updater(state.sessionTitleMap) }
    case 'UPDATE_DELETED_SESSION_IDS':
      return { ...state, deletedSessionIds: action.updater(state.deletedSessionIds) }
    case 'UPDATE_LOCAL_DRAFT_SESSION_IDS':
      return { ...state, localDraftSessionIds: action.updater(state.localDraftSessionIds) }
    case 'UPDATE_RECENT_COMPLETED_REPLIES':
      return { ...state, recentCompletedReplies: action.updater(state.recentCompletedReplies) }
    case 'BATCH': {
      let s = state
      for (const a of action.actions) s = studentReducer(s, a)
      return s
    }
    default:
      return state
  }
}

function buildInitialState(): StudentState {
  const apiBase = safeLocalStorageGetItem('apiBaseStudent') || DEFAULT_API_URL
  let verifiedStudent: VerifiedStudent | null = null
  const rawVerified = safeLocalStorageGetItem('verifiedStudent')
  if (rawVerified) {
    try { verifiedStudent = JSON.parse(rawVerified) as VerifiedStudent } catch { /* ignore */ }
  }
  if (!readStudentAccessToken()) {
    verifiedStudent = null
  }
  let pendingChatJob: PendingChatJob | null = null
  let recentCompletedReplies: RecentCompletedReply[] = []
  const sid = verifiedStudent?.student_id?.trim() || ''
  if (sid) {
    const rawPending = safeLocalStorageGetItem(`${PENDING_CHAT_KEY_PREFIX}${sid}`)
    pendingChatJob = parsePendingChatJobFromStorage(rawPending)
    recentCompletedReplies = parseRecentCompletedReplies(
      safeLocalStorageGetItem(`${RECENT_COMPLETION_KEY_PREFIX}${sid}`),
    )
  }
  return {
    apiBase,
    verifiedStudent,
    verifyOpen: !verifiedStudent,
    nameInput: '',
    classInput: '',
    credentialInput: '',
    credentialType: 'token',
    newPasswordInput: '',
    verifying: false,
    settingPassword: false,
    verifyError: '',
    verifyInfo: '',
    sessions: [],
    activeSessionId: '',
    historyLoading: false,
    historyError: '',
    historyCursor: 0,
    historyHasMore: false,
    historyQuery: '',
    showArchivedSessions: false,
    sessionTitleMap: {},
    deletedSessionIds: [],
    localDraftSessionIds: [],
    sessionLoading: false,
    sessionError: '',
    sessionCursor: 0,
    sessionHasMore: false,
    messages: [{ id: makeId(), role: 'assistant', content: STUDENT_WELCOME_MESSAGE, time: nowTime() }],
    input: '',
    sending: false,
    pendingChatJob,
    recentCompletedReplies,
    todayAssignment: null,
    assignmentLoading: false,
    assignmentError: '',
    sidebarOpen: safeLocalStorageGetItem('studentSidebarOpen') !== 'false',
    openSessionMenuId: '',
    renameDialogSessionId: null,
    archiveDialogSessionId: null,
    forceSessionLoadToken: 0,
    personaEnabled: false,
    personaPickerOpen: false,
    activePersonaId: '',
    personaCards: [],
    personaLoading: false,
    personaError: '',
  }
}

export function useStudentState() {
  const [state, dispatch] = useReducer(studentReducer, undefined, buildInitialState)

  const activeSessionRef = useRef('')
  const pendingChatJobRef = useRef<PendingChatJob | null>(state.pendingChatJob)
  const recentCompletedRepliesRef = useRef<RecentCompletedReply[]>(state.recentCompletedReplies)
  const pendingRecoveredFromStorageRef = useRef(false)
  const skipAutoSessionLoadIdRef = useRef('')
  const historyRequestRef = useRef(0)
  const sessionRequestRef = useRef(0)
  const markdownCacheRef = useRef(new Map<string, { content: string; html: string; apiBase: string }>())

  const setActiveSession = useCallback((sessionId: string) => {
    const sid = String(sessionId || '').trim()
    activeSessionRef.current = sid
    dispatch({ type: 'SET', field: 'activeSessionId', value: sid })
  }, [])

  return {
    state,
    dispatch,
    refs: {
      activeSessionRef,
      pendingChatJobRef,
      recentCompletedRepliesRef,
      pendingRecoveredFromStorageRef,
      skipAutoSessionLoadIdRef,
      historyRequestRef,
      sessionRequestRef,
      markdownCacheRef,
    },
    setActiveSession,
  }
}
