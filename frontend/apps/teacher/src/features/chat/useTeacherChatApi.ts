import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { postTeacherToolConfirm, type TeacherToolConfirm } from './TeacherToolConfirmDialog'
import { absolutizeChartImageUrls, renderMarkdown, renderStreamingPlainText } from './markdown'
import { withPendingChatOverlay } from './pendingOverlay'
import { buildSkill, fallbackSkills, TEACHER_GREETING } from './catalog'
import { toUserFacingErrorMessage } from '../../../../shared/errorMessage'
import { TEACHER_AUTH_EVENT, readTeacherAccessToken } from '../auth/teacherAuth'
import { makeId } from '../../utils/id'
import { nowTime, timeFromIso } from '../../utils/time'
import { useTeacherChatSend } from './useTeacherChatSend'
import { useTeacherChatStream } from './useTeacherChatStream'
import type {
  ExecutionTimelineEntry,
  Message,
  PendingChatJob,
  PendingToolRun,
  RenderedMessage,
  Skill,
  SkillResponse,
  StudentMemoryInsightsResponse,
  StudentMemoryProposal,
  StudentMemoryProposalListResponse,
  TeacherHistorySession,
  TeacherHistorySessionResponse,
  TeacherHistorySessionsResponse,
  TeacherMemoryInsightsResponse,
  TeacherMemoryProposal,
  TeacherMemoryProposalListResponse,
  WheelScrollZone,
  WorkbenchTab,
} from '../../appTypes'

export type UseTeacherChatApiParams = {
  apiBase: string
  activeSessionId: string
  messages: Message[]
  activeSkillId: string
  skillPinned: boolean
  skillList: Skill[]
  pendingChatJob: PendingChatJob | null
  memoryStatusFilter: string
  studentMemoryStatusFilter: string
  studentMemoryStudentFilter: string
  skillsOpen: boolean
  workbenchTab: WorkbenchTab
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
  setSending: React.Dispatch<React.SetStateAction<boolean>>
  setActiveSessionId: React.Dispatch<React.SetStateAction<string>>
  setPendingChatJob: React.Dispatch<React.SetStateAction<PendingChatJob | null>>
  setChatQueueHint: React.Dispatch<React.SetStateAction<string>>
  setPendingStreamStage: React.Dispatch<React.SetStateAction<string>>
  setPendingToolRuns: React.Dispatch<React.SetStateAction<PendingToolRun[]>>
  setExecutionTimeline: React.Dispatch<React.SetStateAction<ExecutionTimelineEntry[]>>
  setComposerWarning: React.Dispatch<React.SetStateAction<string>>
  setInput: React.Dispatch<React.SetStateAction<string>>
  // Session state setters (from useTeacherSessionState — useReducer-based)
  setHistorySessions: (
    value:
      | TeacherHistorySession[]
      | ((prev: TeacherHistorySession[]) => TeacherHistorySession[])
  ) => void
  setHistoryLoading: (value: boolean) => void
  setHistoryError: (value: string) => void
  setHistoryCursor: (value: number) => void
  setHistoryHasMore: (value: boolean) => void
  setLocalDraftSessionIds: (value: string[] | ((prev: string[]) => string[])) => void
  setSessionLoading: (value: boolean) => void
  setSessionError: (value: string) => void
  setSessionCursor: (value: number) => void
  setSessionHasMore: (value: boolean) => void
  // Memory setters (from useTeacherWorkbenchState — useReducer-based)
  setProposalLoading: (value: boolean) => void
  setProposalError: (value: string) => void
  setProposals: (value: TeacherMemoryProposal[]) => void
  setMemoryInsights: (value: TeacherMemoryInsightsResponse | null) => void
  setStudentProposalLoading: (value: boolean) => void
  setStudentProposalError: (value: string) => void
  setStudentProposals: (value: StudentMemoryProposal[]) => void
  setStudentMemoryInsights: (value: StudentMemoryInsightsResponse | null) => void
  // Skill setters (from useState — React.Dispatch compatible)
  setSkillList: React.Dispatch<React.SetStateAction<Skill[]>>
  setSkillsLoading: React.Dispatch<React.SetStateAction<boolean>>
  setSkillsError: React.Dispatch<React.SetStateAction<string>>
  // Callbacks from parent
  chooseSkill: (skillId: string, pinned?: boolean) => void
  enableAutoScroll: () => void
  setWheelScrollZone: (zone: WheelScrollZone) => void
}

const toErrorMessage = (error: unknown, fallback = '请求失败') => {
  return toUserFacingErrorMessage(error, fallback)
}

export function useTeacherChatApi(params: UseTeacherChatApiParams) {
  const {
    apiBase,
    activeSessionId,
    messages,
    activeSkillId,
    skillPinned,
    skillList,
    pendingChatJob,
    memoryStatusFilter,
    studentMemoryStatusFilter,
    studentMemoryStudentFilter,
    skillsOpen,
    workbenchTab,
    setMessages,
    setSending,
    setActiveSessionId,
    setPendingChatJob,
    setChatQueueHint,
    setPendingStreamStage,
    setPendingToolRuns,
    setExecutionTimeline,
    setComposerWarning,
    setInput,
    setHistorySessions,
    setHistoryLoading,
    setHistoryError,
    setHistoryCursor,
    setHistoryHasMore,
    setLocalDraftSessionIds,
    setSessionLoading,
    setSessionError,
    setSessionCursor,
    setSessionHasMore,
    setProposalLoading,
    setProposalError,
    setProposals,
    setMemoryInsights,
    setStudentProposalLoading,
    setStudentProposalError,
    setStudentProposals,
    setStudentMemoryInsights,
    setSkillList,
    setSkillsLoading,
    setSkillsError,
    chooseSkill,
    enableAutoScroll,
    setWheelScrollZone,
  } = params
  // ── Refs ──────────────────────────────────────────────────────────────
  const activeSessionRef = useRef(activeSessionId)
  const historyRequestRef = useRef(0)
  const sessionRequestRef = useRef(0)
  const historyCursorRef = useRef(0)
  const historyHasMoreRef = useRef(false)
  const localDraftSessionIdsRef = useRef<string[]>([])
  const pendingChatJobRef = useRef<PendingChatJob | null>(pendingChatJob)
  const markdownCacheRef = useRef(new Map<string, { content: string; html: string; apiBase: string; authToken: string }>())
  const [authToken, setAuthToken] = useState(() => readTeacherAccessToken())
  const [toolConfirm, setToolConfirm] = useState<TeacherToolConfirm | null>(null)
  // ── Ref sync effects ──────────────────────────────────────────────────
  useEffect(() => { activeSessionRef.current = activeSessionId }, [activeSessionId])
  useEffect(() => { pendingChatJobRef.current = pendingChatJob }, [pendingChatJob])
  useEffect(() => {
    const sync = () => setAuthToken(readTeacherAccessToken())
    sync()
    window.addEventListener('storage', sync)
    window.addEventListener(TEACHER_AUTH_EVENT, sync as EventListener)
    return () => {
      window.removeEventListener('storage', sync)
      window.removeEventListener(TEACHER_AUTH_EVENT, sync as EventListener)
    }
  }, [])
  // Sync historyCursor / historyHasMore / localDraftSessionIds into refs
  // (these are read inside callbacks that must not re-create on every state change)
  const syncHistoryCursor = useCallback((val: number) => { historyCursorRef.current = val }, [])
  const syncHistoryHasMore = useCallback((val: boolean) => { historyHasMoreRef.current = val }, [])
  const syncLocalDraftSessionIds = useCallback((val: string[]) => { localDraftSessionIdsRef.current = val }, [])
  // Clear markdown cache when apiBase or auth token changes
  useEffect(() => { markdownCacheRef.current.clear() }, [apiBase, authToken])
  // ── renderedMessages memo ─────────────────────────────────────────────
  const renderedMessages = useMemo(() => {
    const cache = markdownCacheRef.current
    const pendingPlaceholderId = pendingChatJob?.job_id ? String(pendingChatJob.placeholder_id || '').trim() : ''
    return messages.map((msg): RenderedMessage => {
      if (pendingPlaceholderId && msg.id === pendingPlaceholderId) {
        return { ...msg, html: renderStreamingPlainText(msg.content) }
      }
      const cached = cache.get(msg.id)
      if (cached && cached.content === msg.content && cached.apiBase === apiBase && cached.authToken === authToken) {
        return { ...msg, html: cached.html }
      }
      const html = absolutizeChartImageUrls(renderMarkdown(msg.content), apiBase)
      cache.set(msg.id, { content: msg.content, html, apiBase, authToken })
      return { ...msg, html }
    })
  }, [messages, apiBase, authToken, pendingChatJob?.job_id, pendingChatJob?.placeholder_id])
  // ── refreshTeacherSessions ────────────────────────────────────────────
  const refreshTeacherSessions = useCallback(
    async (mode: 'reset' | 'more' = 'reset') => {
      if (!authToken) return
      if (mode === 'more' && !historyHasMoreRef.current) return
      const cursor = mode === 'more' ? historyCursorRef.current : 0
      const requestNo = ++historyRequestRef.current
      setHistoryLoading(true)
      if (mode === 'reset') setHistoryError('')
      try {
        const url = new URL(`${apiBase}/teacher/history/sessions`)
        url.searchParams.set('limit', '40')
        url.searchParams.set('cursor', String(cursor))
        const res = await fetch(url.toString())
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `状态码 ${res.status}`)
        }
        const data = (await res.json()) as TeacherHistorySessionsResponse
        if (requestNo !== historyRequestRef.current) return
        const serverSessions = Array.isArray(data.sessions) ? data.sessions : []
        const serverIds = new Set(serverSessions.map((item) => String(item.session_id || '').trim()).filter(Boolean))
        setLocalDraftSessionIds((prev) => prev.filter((id) => !serverIds.has(id)))
        const nextCursor = typeof data.next_cursor === 'number' ? data.next_cursor : null
        setHistoryCursor(nextCursor ?? 0)
        syncHistoryCursor(nextCursor ?? 0)
        setHistoryHasMore(nextCursor !== null)
        syncHistoryHasMore(nextCursor !== null)
        if (mode === 'more') {
          setHistorySessions((prev) => {
            const merged = [...prev]
            const existingIds = new Set(prev.map((item) => item.session_id))
            for (const item of serverSessions) {
              if (existingIds.has(item.session_id)) continue
              merged.push(item)
            }
            return merged
          })
        } else {
          setHistorySessions((prev) => {
            const draftItems = localDraftSessionIdsRef.current
              .filter((id) => !serverIds.has(id))
              .map(
                (id) =>
                  prev.find((item) => item.session_id === id) || {
                    session_id: id,
                    updated_at: new Date().toISOString(),
                    message_count: 0,
                    preview: '',
                  },
              )
            const seeded = [...draftItems, ...serverSessions]
            const seen = new Set(seeded.map((item) => item.session_id))
            for (const item of prev) {
              if (seen.has(item.session_id)) continue
              seeded.push(item)
            }
            return seeded
          })
        }
      } catch (err: unknown) {
        if (requestNo !== historyRequestRef.current) return
        setHistoryError(toErrorMessage(err))
      } finally {
        if (requestNo !== historyRequestRef.current) return
        setHistoryLoading(false)
      }
    },
    [apiBase, authToken, setHistoryLoading, setHistoryError, setLocalDraftSessionIds, setHistoryCursor, setHistoryHasMore, setHistorySessions, syncHistoryCursor, syncHistoryHasMore],
  )
  // ── loadTeacherSessionMessages ────────────────────────────────────────
  const loadTeacherSessionMessages = useCallback(
    async (sessionId: string, cursor: number, append: boolean) => {
      if (!authToken) return
      const targetSessionId = (sessionId || '').trim()
      if (!targetSessionId) return
      const requestNo = ++sessionRequestRef.current
      setSessionLoading(true)
      setSessionError('')
      try {
        const LIMIT = 80
        const url = new URL(`${apiBase}/teacher/history/session`)
        url.searchParams.set('session_id', targetSessionId)
        url.searchParams.set('cursor', String(cursor))
        url.searchParams.set('limit', String(LIMIT))
        url.searchParams.set('direction', 'backward')
        const res = await fetch(url.toString())
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `状态码 ${res.status}`)
        }
        const data = (await res.json()) as TeacherHistorySessionResponse
        if (requestNo !== sessionRequestRef.current || activeSessionRef.current !== targetSessionId) return
        const responseSessionId = String(data.session_id || '').trim()
        if (responseSessionId && responseSessionId !== targetSessionId) {
          throw new Error(`会话响应不匹配（请求=${targetSessionId}，返回=${responseSessionId}）`)
        }
        const raw = Array.isArray(data.messages) ? data.messages : []
        const mapped: Message[] = raw
          .map((m, idx) => {
            const roleRaw = String(m.role || '').toLowerCase()
            const role = roleRaw === 'user' ? 'user' : roleRaw === 'assistant' ? 'assistant' : null
            const content = typeof m.content === 'string' ? m.content : ''
            if (!role || !content) return null
            return {
              id: `thist_${targetSessionId}_${cursor}_${idx}_${m.ts || ''}`,
              role,
              content,
              time: timeFromIso(m.ts),
            } as Message
          })
          .filter(Boolean) as Message[]
        const mappedWithPending = append
          ? mapped
          : withPendingChatOverlay(mapped, pendingChatJobRef.current, targetSessionId)
        const next = typeof data.next_cursor === 'number' ? data.next_cursor : 0
        setSessionCursor(next)
        setSessionHasMore(mapped.length >= 1 && next > 0)
        if (append) {
          setMessages((prev) => [...mapped, ...prev])
        } else {
          setMessages((prev) => {
            if (mappedWithPending.length) return mappedWithPending
            // Guard against startup races during pending-job restore:
            // keep recovered pending bubbles only when they belong to this session.
            const pending = pendingChatJobRef.current
            const pendingBelongsToTargetSession = Boolean(
              pending?.job_id && (!pending.session_id || pending.session_id === targetSessionId),
            )
            if (pendingBelongsToTargetSession && prev.some((item) => String(item.id || '').startsWith('pending_user_'))) {
              return prev
            }
            return [
              {
                id: makeId(),
                role: 'assistant',
                content: TEACHER_GREETING,
                time: nowTime(),
              },
            ]
          })
        }
      } catch (err: unknown) {
        if (requestNo !== sessionRequestRef.current || activeSessionRef.current !== targetSessionId) return
        setSessionError(toErrorMessage(err))
      } finally {
        if (requestNo !== sessionRequestRef.current || activeSessionRef.current !== targetSessionId) return
        setSessionLoading(false)
      }
    },
    [apiBase, authToken, setSessionLoading, setSessionError, setSessionCursor, setSessionHasMore, setMessages],
  )
  // ── refreshMemoryProposals ────────────────────────────────────────────
  const refreshMemoryProposals = useCallback(async () => {
    if (!authToken) return
    setProposalLoading(true)
    setProposalError('')
    try {
      const url = new URL(`${apiBase}/teacher/memory/proposals`)
      if (memoryStatusFilter !== 'all') {
        url.searchParams.set('status', memoryStatusFilter)
      }
      url.searchParams.set('limit', '30')
      const res = await fetch(url.toString())
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `状态码 ${res.status}`)
      }
      const data = (await res.json()) as TeacherMemoryProposalListResponse
      setProposals(Array.isArray(data.proposals) ? data.proposals : [])
    } catch (err: unknown) {
      setProposalError(toErrorMessage(err))
    } finally {
      setProposalLoading(false)
    }
  }, [apiBase, authToken, memoryStatusFilter, setProposalLoading, setProposalError, setProposals])
  // ── refreshMemoryInsights ─────────────────────────────────────────────
  const refreshMemoryInsights = useCallback(async () => {
    if (!authToken) return
    try {
      const url = new URL(`${apiBase}/teacher/memory/insights`)
      url.searchParams.set('days', '14')
      const res = await fetch(url.toString())
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `状态码 ${res.status}`)
      }
      const data = (await res.json()) as TeacherMemoryInsightsResponse
      setMemoryInsights(data)
    } catch (err) {
      setMemoryInsights(null)
    }
  }, [apiBase, authToken, setMemoryInsights])
  // ── deleteMemoryProposal ──────────────────────────────────────────────
  const deleteMemoryProposal = useCallback(
    async (proposalId: string) => {
      if (!authToken) {
        throw new Error('请先完成教师认证。')
      }
      const pid = String(proposalId || '').trim()
      if (!pid) throw new Error('proposal_id 缺失')
      const res = await fetch(`${apiBase}/teacher/memory/proposals/${encodeURIComponent(pid)}`, {
        method: 'DELETE',
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `状态码 ${res.status}`)
      }
      await refreshMemoryProposals()
      await refreshMemoryInsights()
    },
    [apiBase, authToken, refreshMemoryInsights, refreshMemoryProposals],
  )
  // ── refreshStudentMemoryProposals ─────────────────────────────────────
  const refreshStudentMemoryProposals = useCallback(async () => {
    if (!authToken) return
    setStudentProposalLoading(true)
    setStudentProposalError('')
    try {
      const url = new URL(`${apiBase}/teacher/student-memory/proposals`)
      if (studentMemoryStatusFilter !== 'all') {
        url.searchParams.set('status', studentMemoryStatusFilter)
      }
      const studentId = String(studentMemoryStudentFilter || '').trim()
      if (studentId) {
        url.searchParams.set('student_id', studentId)
      }
      url.searchParams.set('limit', '40')
      const res = await fetch(url.toString())
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `状态码 ${res.status}`)
      }
      const data = (await res.json()) as StudentMemoryProposalListResponse
      setStudentProposals(Array.isArray(data.proposals) ? data.proposals : [])
    } catch (err: unknown) {
      setStudentProposalError(toErrorMessage(err))
    } finally {
      setStudentProposalLoading(false)
    }
  }, [
    apiBase,
    authToken,
    studentMemoryStatusFilter,
    studentMemoryStudentFilter,
    setStudentProposalLoading,
    setStudentProposalError,
    setStudentProposals,
  ])
  // ── refreshStudentMemoryInsights ──────────────────────────────────────
  const refreshStudentMemoryInsights = useCallback(async () => {
    if (!authToken) return
    try {
      const url = new URL(`${apiBase}/teacher/student-memory/insights`)
      url.searchParams.set('days', '14')
      const studentId = String(studentMemoryStudentFilter || '').trim()
      if (studentId) {
        url.searchParams.set('student_id', studentId)
      }
      const res = await fetch(url.toString())
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `状态码 ${res.status}`)
      }
      const data = (await res.json()) as StudentMemoryInsightsResponse
      setStudentMemoryInsights(data)
    } catch (err) {
      setStudentMemoryInsights(null)
    }
  }, [apiBase, authToken, studentMemoryStudentFilter, setStudentMemoryInsights])
  // ── reviewStudentMemoryProposal ───────────────────────────────────────
  const reviewStudentMemoryProposal = useCallback(
    async (proposalId: string, approve: boolean) => {
      if (!authToken) {
        throw new Error('请先完成教师认证。')
      }
      const pid = String(proposalId || '').trim()
      if (!pid) throw new Error('proposal_id 缺失')
      const res = await fetch(`${apiBase}/teacher/student-memory/proposals/${encodeURIComponent(pid)}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approve }),
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `状态码 ${res.status}`)
      }
      await refreshStudentMemoryProposals()
      await refreshStudentMemoryInsights()
    },
    [apiBase, authToken, refreshStudentMemoryInsights, refreshStudentMemoryProposals],
  )
  // ── deleteStudentMemoryProposal ───────────────────────────────────────
  const deleteStudentMemoryProposal = useCallback(
    async (proposalId: string) => {
      if (!authToken) {
        throw new Error('请先完成教师认证。')
      }
      const pid = String(proposalId || '').trim()
      if (!pid) throw new Error('proposal_id 缺失')
      const res = await fetch(`${apiBase}/teacher/student-memory/proposals/${encodeURIComponent(pid)}`, {
        method: 'DELETE',
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || `状态码 ${res.status}`)
      }
      await refreshStudentMemoryProposals()
      await refreshStudentMemoryInsights()
    },
    [apiBase, authToken, refreshStudentMemoryInsights, refreshStudentMemoryProposals],
  )
  // ── fetchSkills ───────────────────────────────────────────────────────
  const fetchSkills = useCallback(async () => {
    if (!authToken) {
      setSkillList(fallbackSkills)
      setSkillsError('')
      setSkillsLoading(false)
      return
    }
    setSkillsLoading(true)
    setSkillsError('')
    try {
      const res = await fetch(`${apiBase}/skills`)
      if (!res.ok) throw new Error(`状态码 ${res.status}`)
      const data = (await res.json()) as SkillResponse
      const raw = Array.isArray(data.skills) ? data.skills : []
      const teacherSkills = raw.filter((skill) => {
        const roles = skill.allowed_roles
        return !Array.isArray(roles) || roles.length === 0 || roles.includes('teacher')
      })
      if (teacherSkills.length === 0) {
        setSkillList(fallbackSkills)
        return
      }
      setSkillList(teacherSkills.map((skill) => buildSkill(skill)))
    } catch (err: unknown) {
      setSkillsError(toErrorMessage(err, '无法加载能力列表'))
      setSkillList(fallbackSkills)
    } finally {
      setSkillsLoading(false)
    }
  }, [apiBase, authToken, setSkillsLoading, setSkillsError, setSkillList])
  const { submitMessage } = useTeacherChatSend({
    apiBase,
    authToken,
    pendingChatJob,
    pendingChatJobRef,
    skillList,
    activeSkillId,
    skillPinned,
    activeSessionId,
    messages,
    setComposerWarning,
    chooseSkill,
    setActiveSessionId,
    setWheelScrollZone,
    enableAutoScroll,
    setMessages,
    setInput,
    setSending,
    setChatQueueHint,
    setPendingStreamStage,
    setPendingToolRuns,
    setExecutionTimeline,
    setPendingChatJob,
  })
  useTeacherChatStream({
    apiBase,
    authToken,
    pendingChatJob,
    pendingChatJobRef,
    activeSessionId,
    skillList,
    setMessages,
    setPendingChatJob,
    setChatQueueHint,
    setPendingStreamStage,
    setPendingToolRuns,
    setExecutionTimeline,
    setSending,
    setComposerWarning,
    refreshTeacherSessions,
    setToolConfirm,
  })
  // ── Session refresh on mount ──────────────────────────────────────────
  useEffect(() => {
    if (!authToken) return
    void refreshTeacherSessions()
  }, [authToken, refreshTeacherSessions])
  // ── Load messages when activeSessionId changes ────────────────────────
  useEffect(() => {
    if (!authToken) return
    if (!activeSessionId) return
    void loadTeacherSessionMessages(activeSessionId, -1, false)
  }, [activeSessionId, authToken, loadTeacherSessionMessages])
  // ── Session refresh 30s interval ──────────────────────────────────────
  useEffect(() => {
    if (!authToken) return
    const timer = window.setInterval(() => {
      void refreshTeacherSessions()
    }, 30000)
    return () => window.clearInterval(timer)
  }, [authToken, refreshTeacherSessions])
  // ── Memory refresh effects ────────────────────────────────────────────
  useEffect(() => {
    if (!authToken) return
    if (!skillsOpen) return
    if (workbenchTab !== 'memory') return
    void refreshMemoryProposals()
    void refreshMemoryInsights()
    void refreshStudentMemoryProposals()
    void refreshStudentMemoryInsights()
  }, [
    skillsOpen,
    workbenchTab,
    authToken,
    refreshMemoryInsights,
    refreshMemoryProposals,
    refreshStudentMemoryProposals,
    refreshStudentMemoryInsights,
  ])
  // ── Skill fetch on mount ──────────────────────────────────────────────
  useEffect(() => {
    if (!authToken) return
    void fetchSkills()
  }, [authToken, fetchSkills])
  // ── Skill fetch when workbench skills tab opens ───────────────────────
  useEffect(() => {
    if (!authToken) return
    if (!skillsOpen || workbenchTab !== 'skills') return
    void fetchSkills()
  }, [skillsOpen, workbenchTab, authToken, fetchSkills])
  // ── Skill polling 30s when skills tab is open ─────────────────────────
  useEffect(() => {
    if (!authToken) return
    if (!skillsOpen || workbenchTab !== 'skills') return
    const timer = window.setInterval(() => {
      void fetchSkills()
    }, 30000)
    return () => window.clearInterval(timer)
  }, [skillsOpen, workbenchTab, authToken, fetchSkills])
  const postToolConfirm = useCallback(async (confirmed: boolean) => {
    const pending = toolConfirm
    if (!pending?.confirm_id) return
    setToolConfirm(null)
    try {
      await postTeacherToolConfirm(apiBase, pending.confirm_id, confirmed)
      if (!confirmed) setPendingStreamStage('已取消写操作，继续生成…')
    } catch (err: unknown) {
      setComposerWarning(toErrorMessage(err, '确认失败'))
    }
  }, [apiBase, setComposerWarning, setPendingStreamStage, toolConfirm])
  const confirmToolWrite = useCallback(() => { void postToolConfirm(true) }, [postToolConfirm])
  const cancelToolConfirm = useCallback(() => { void postToolConfirm(false) }, [postToolConfirm])
  // ── Return ────────────────────────────────────────────────────────────
  return {
    refreshTeacherSessions,
    loadTeacherSessionMessages,
    refreshMemoryProposals,
    refreshMemoryInsights,
    deleteMemoryProposal,
    refreshStudentMemoryProposals,
    refreshStudentMemoryInsights,
    reviewStudentMemoryProposal,
    deleteStudentMemoryProposal,
    submitMessage,
    fetchSkills,
    renderedMessages,
    // Expose ref sync helpers so the parent can keep refs in sync
    syncHistoryCursor,
    syncHistoryHasMore,
    syncLocalDraftSessionIds,
    // Expose refs the parent may need for direct access
    activeSessionRef,
    historyRequestRef,
    sessionRequestRef,
    historyCursorRef,
    historyHasMoreRef,
    localDraftSessionIdsRef,
    pendingChatJobRef,
    markdownCacheRef,
    toolConfirm,
    confirmToolWrite,
    cancelToolConfirm,
  }
}
