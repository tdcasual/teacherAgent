import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { absolutizeChartImageUrls, renderMarkdown } from './markdown'
import { stripTransientPendingBubbles, withPendingChatOverlay } from './pendingOverlay'
import { buildSkill, fallbackSkills, TEACHER_GREETING } from './catalog'
import { parseInvocationInput } from './invocation'
import { decideSkillRouting } from './requestRouting'
import { CHAT_STREAM_EVENT_VERSION, parseChatStreamEnvelope } from './streamEventProtocol'
import { startVisibilityAwareBackoffPolling } from '../../../../shared/visibilityBackoffPolling'
import { toUserFacingErrorMessage } from '../../../../shared/errorMessage'
import { safeLocalStorageGetItem } from '../../utils/storage'
import { TEACHER_AUTH_EVENT, readTeacherAccessToken } from '../auth/teacherAuth'
import { makeId } from '../../utils/id'
import { nowTime, timeFromIso } from '../../utils/time'
import type {
  ChatJobStatus,
  ChatStartResult,
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
  const markdownCacheRef = useRef(new Map<string, { content: string; html: string; apiBase: string }>())
  const [authToken, setAuthToken] = useState(() => readTeacherAccessToken())

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

  // Clear markdown cache when apiBase changes
  useEffect(() => { markdownCacheRef.current.clear() }, [apiBase])

  // ── renderedMessages memo ─────────────────────────────────────────────
  const renderedMessages = useMemo(() => {
    const cache = markdownCacheRef.current
    return messages.map((msg): RenderedMessage => {
      const cached = cache.get(msg.id)
      if (cached && cached.content === msg.content && cached.apiBase === apiBase) {
        return { ...msg, html: cached.html }
      }
      const html = absolutizeChartImageUrls(renderMarkdown(msg.content), apiBase)
      cache.set(msg.id, { content: msg.content, html, apiBase })
      return { ...msg, html }
    })
  }, [messages, apiBase])

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
            // keep recovered pending bubbles if current payload is empty.
            if (prev.some((item) => String(item.id || '').startsWith('pending_user_'))) {
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
      setSkillsError(toErrorMessage(err, '无法加载技能列表'))
      setSkillList(fallbackSkills)
    } finally {
      setSkillsLoading(false)
    }
  }, [apiBase, authToken, setSkillsLoading, setSkillsError, setSkillList])

  // ── submitMessage ─────────────────────────────────────────────────────
  const submitMessage = useCallback(
    async (inputText: string, options?: { attachments?: Array<{ attachment_id: string }> }) => {
      if (!authToken) {
        setComposerWarning('请先在顶部完成教师认证。')
        return false
      }
      if (pendingChatJob?.job_id) return false
      const attachmentRefs = Array.isArray(options?.attachments)
        ? options?.attachments.filter((item) => String(item?.attachment_id || '').trim())
        : []
      const trimmed = inputText.trim()
      if (!trimmed && attachmentRefs.length === 0) return false
      const parsedInvocation = parseInvocationInput(trimmed, {
        knownSkillIds: skillList.map((item) => item.id),
        activeSkillId: activeSkillId || 'physics-teacher-ops',
      })
      let cleanedText = parsedInvocation.cleanedInput.trim()
      if (!cleanedText && attachmentRefs.length > 0) {
        cleanedText = '请阅读我上传的附件并回答。'
      }
      if (!cleanedText) {
        setComposerWarning('请在召唤后补充问题内容。')
        return false
      }
      const routingDecision = decideSkillRouting({
        parsedInvocation,
        activeSkillId,
        skillPinned,
      })
      if (routingDecision.normalizedWarnings.length) {
        setComposerWarning(routingDecision.normalizedWarnings.join('；'))
      } else {
        setComposerWarning('')
      }
      if (routingDecision.shouldPinEffectiveSkill && parsedInvocation.effectiveSkillId) {
        chooseSkill(parsedInvocation.effectiveSkillId, true)
      }
      const sessionId = activeSessionId || 'main'
      if (!activeSessionId) setActiveSessionId(sessionId)
      const requestId = `tchat_${Date.now()}_${Math.random().toString(16).slice(2)}`
      const placeholderId = `asst_${Date.now()}_${Math.random().toString(16).slice(2)}`
      const routingTeacherId = (safeLocalStorageGetItem('teacherRoutingTeacherId') || '').trim()

      setWheelScrollZone('chat')
      enableAutoScroll()
      setMessages((prev) => {
        const next = stripTransientPendingBubbles(prev)
        return [
          ...next,
          { id: makeId(), role: 'user' as const, content: cleanedText, time: nowTime() },
          { id: placeholderId, role: 'assistant' as const, content: '正在生成…', time: nowTime() },
        ]
      })
      setInput('')

      const contextMessages = [...messages, { id: 'temp', role: 'user' as const, content: cleanedText, time: '' }]
        .slice(-40)
        .map((msg) => ({ role: msg.role, content: msg.content }))

      setSending(true)
      try {
        const res = await fetch(`${apiBase}/chat/start`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            request_id: requestId,
            session_id: sessionId,
            messages: contextMessages,
            role: 'teacher',
            teacher_id: routingTeacherId || undefined,
            skill_id: routingDecision.skillIdForRequest,
            attachments: attachmentRefs.length ? attachmentRefs : undefined,
          }),
        })
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `状态码 ${res.status}`)
        }
        const data = (await res.json()) as ChatStartResult
        if (!data?.job_id) throw new Error('任务编号缺失')
        const runtimeWarnings = Array.isArray(data.warnings)
          ? data.warnings.map((item) => String(item || '').trim()).filter(Boolean)
          : []
        if (runtimeWarnings.length) {
          setComposerWarning(runtimeWarnings.join('；'))
        }
        const lanePos = Number(data.lane_queue_position || 0)
        const laneSize = Number(data.lane_queue_size || 0)
        setChatQueueHint(lanePos > 0 ? `排队中，前方 ${lanePos} 条（队列 ${laneSize}）` : '处理中...')
        const nextPendingJob: PendingChatJob = {
          job_id: data.job_id,
          request_id: requestId,
          placeholder_id: placeholderId,
          user_text: cleanedText,
          session_id: sessionId,
          lane_id: data.lane_id,
          created_at: Date.now(),
        }
        pendingChatJobRef.current = nextPendingJob
        setPendingChatJob(nextPendingJob)
        setPendingStreamStage('排队中...')
        setPendingToolRuns([])
        return true
      } catch (err: unknown) {
        const errorMessage = toErrorMessage(err)
        setMessages((prev) =>
          prev.map((m) =>
            m.id === placeholderId
              ? { ...m, content: `抱歉，请求失败：${errorMessage}`, time: nowTime() }
              : m,
          ),
        )
        setSending(false)
        setChatQueueHint('')
        setPendingStreamStage('')
        setPendingToolRuns([])
        pendingChatJobRef.current = null
        setPendingChatJob(null)
        return false
      }
    },
    [
      pendingChatJob?.job_id, skillList, activeSkillId, skillPinned, activeSessionId, messages, apiBase,
      authToken,
      setComposerWarning, chooseSkill, setActiveSessionId, setWheelScrollZone, enableAutoScroll,
      setMessages, setInput, setSending, setChatQueueHint, setPendingStreamStage, setPendingToolRuns, setPendingChatJob,
    ],
  )

  // ── Pending chat job stream effect (fallback to polling) ──────────────
  useEffect(() => {
    if (!authToken) return
    if (!pendingChatJob?.job_id) return
    let stopped = false
    let pollCleanup: (() => void) | null = null
    let pollStarted = false
    const controller = new AbortController()
    const targetSessionId = activeSessionId || pendingChatJob.session_id || 'main'
    const sameSession =
      !pendingChatJob.session_id || !activeSessionId || pendingChatJob.session_id === activeSessionId

    const setPlaceholderContent = (content: string) => {
      if (!sameSession) return
      setMessages((prev) => {
        const overlaid = withPendingChatOverlay(prev, pendingChatJob, targetSessionId)
        return overlaid.map((item) =>
          item.id === pendingChatJob.placeholder_id ? { ...item, content, time: nowTime() } : item,
        )
      })
    }

    const finishSuccess = (replyText: string) => {
      setMessages((prev) => {
        const overlaid = withPendingChatOverlay(prev, pendingChatJob, targetSessionId)
        return overlaid.map((item) =>
          item.id === pendingChatJob.placeholder_id ? { ...item, content: replyText || '已收到。', time: nowTime() } : item,
        )
      })
      pendingChatJobRef.current = null
      setPendingChatJob(null)
      setChatQueueHint('')
      setPendingStreamStage('')
      setPendingToolRuns([])
      setSending(false)
      void refreshTeacherSessions()
    }

    const finishFailure = (message: string) => {
      setMessages((prev) => {
        const overlaid = withPendingChatOverlay(prev, pendingChatJob, targetSessionId)
        return overlaid.map((item) =>
          item.id === pendingChatJob.placeholder_id
            ? { ...item, content: `抱歉，请求失败：${message || '请求失败'}`, time: nowTime() }
            : item,
        )
      })
      pendingChatJobRef.current = null
      setPendingChatJob(null)
      setChatQueueHint('')
      setPendingStreamStage('')
      setPendingToolRuns([])
      setSending(false)
    }

    const startFallbackPolling = () => {
      if (pollStarted || stopped) return
      pollStarted = true
      pollCleanup = startVisibilityAwareBackoffPolling(
        async ({ signal }) => {
          if (pendingChatJob.session_id && activeSessionId && pendingChatJob.session_id !== activeSessionId) {
            return 'continue'
          }

          const res = await fetch(`${apiBase}/chat/status?job_id=${encodeURIComponent(pendingChatJob.job_id)}`, { signal })
          if (!res.ok) {
            const text = await res.text()
            throw new Error(text || `状态码 ${res.status}`)
          }
          const data = (await res.json()) as ChatJobStatus
          if (data.status === 'done') {
            finishSuccess(data.reply || '')
            return 'stop'
          }
          if (data.status === 'failed' || data.status === 'cancelled') {
            finishFailure(data.error_detail || data.error || '请求失败')
            return 'stop'
          }
          const lanePos = Number(data.lane_queue_position || 0)
          const laneSize = Number(data.lane_queue_size || 0)
          if (data.status === 'queued') {
            setChatQueueHint(lanePos > 0 ? `排队中，前方 ${lanePos} 条（队列 ${laneSize}）` : '排队中...')
            setPendingStreamStage('排队中...')
          } else if (data.status === 'processing') {
            setChatQueueHint('处理中...')
            setPendingStreamStage('处理中...')
          } else {
            setChatQueueHint('')
            setPendingStreamStage('')
          }
          return 'continue'
        },
        (err) => {
          const msg = toErrorMessage(err, '网络错误')
          setPlaceholderContent(`网络波动，正在重试…（${msg}）`)
        },
        { kickMode: 'direct', pollTimeoutMs: 15000, inFlightTimeoutMs: 20000 },
      )
    }

    const streamSleep = async (ms: number) =>
      new Promise<void>((resolve) => window.setTimeout(resolve, ms))

    const runStream = async () => {
      let cursor = 0
      let reconnectAttempts = 0
      let assistantText = ''
      let toolCounter = 0
      const toolStates: PendingToolRun[] = []
      let assistantRenderTimer: number | null = null
      let assistantRenderScheduled = false

      const clearAssistantRenderTimer = () => {
        if (assistantRenderTimer !== null) {
          window.clearTimeout(assistantRenderTimer)
          assistantRenderTimer = null
        }
        assistantRenderScheduled = false
      }

      const flushAssistantPlaceholder = () => {
        assistantRenderTimer = null
        assistantRenderScheduled = false
        setPlaceholderContent(assistantText || '正在生成…')
      }

      const scheduleAssistantPlaceholder = () => {
        if (assistantRenderScheduled) return
        assistantRenderScheduled = true
        assistantRenderTimer = window.setTimeout(() => {
          flushAssistantPlaceholder()
        }, 40)
      }

      const renderStreamingPlaceholder = () => {
        clearAssistantRenderTimer()
        setPendingToolRuns([...toolStates])
        setPlaceholderContent(assistantText || '正在生成…')
      }

      const applyStreamEvent = (eventType: string, payload: Record<string, unknown>, eventId: number) => {
        if (eventId > cursor) cursor = eventId
        if (eventType === 'job.queued') {
          const lanePos = Number(payload.lane_queue_position || 0)
          const laneSize = Number(payload.lane_queue_size || 0)
          setChatQueueHint(lanePos > 0 ? `排队中，前方 ${lanePos} 条（队列 ${laneSize}）` : '排队中...')
          setPendingStreamStage('排队中...')
          return
        }
        if (eventType === 'job.processing') {
          setChatQueueHint('处理中...')
          setPendingStreamStage('处理中...')
          return
        }
        if (eventType === 'tool.start') {
          toolCounter += 1
          const toolName = String(payload.tool_name || '').trim() || 'tool'
          const callId = String(payload.tool_call_id || '').trim()
          const key = callId || `${toolName}#${toolCounter}`
          toolStates.push({ key, name: toolName, status: 'running' })
          renderStreamingPlaceholder()
          return
        }
        if (eventType === 'tool.finish') {
          const toolName = String(payload.tool_name || '').trim() || 'tool'
          const callId = String(payload.tool_call_id || '').trim()
          const byCallId = callId ? toolStates.findIndex((item) => item.key === callId) : -1
          const byName = toolStates.findIndex((item) => item.status === 'running' && item.name === toolName)
          const idx = byCallId >= 0 ? byCallId : byName
          const ok = Boolean(payload.ok)
          const durationMs = Number(payload.duration_ms || 0)
          const error = String(payload.error || '').trim()
          if (idx >= 0) {
            toolStates[idx] = {
              ...toolStates[idx],
              status: ok ? 'ok' : 'failed',
              durationMs: Number.isFinite(durationMs) && durationMs > 0 ? durationMs : undefined,
              error: error || undefined,
            }
          } else {
            toolStates.push({
              key: callId || `${toolName}#${toolCounter + 1}`,
              name: toolName,
              status: ok ? 'ok' : 'failed',
              durationMs: Number.isFinite(durationMs) && durationMs > 0 ? durationMs : undefined,
              error: error || undefined,
            })
          }
          renderStreamingPlaceholder()
          return
        }
        if (eventType === 'assistant.delta') {
          const delta = String(payload.delta || '')
          if (delta) {
            assistantText += delta
            scheduleAssistantPlaceholder()
          }
          return
        }
        if (eventType === 'assistant.done') {
          const text = String(payload.text || '')
          if (text) assistantText = text
          scheduleAssistantPlaceholder()
          return
        }
        if (eventType === 'job.done') {
          clearAssistantRenderTimer()
          const text = String(payload.reply || assistantText || '')
          finishSuccess(text)
          stopped = true
          return
        }
        if (eventType === 'job.failed' || eventType === 'job.cancelled') {
          clearAssistantRenderTimer()
          const err = String(payload.error_detail || payload.error || '请求失败')
          finishFailure(err)
          stopped = true
        }
      }

      while (!stopped) {
        if (!pendingChatJobRef.current?.job_id) return
        try {
          const url = new URL(`${apiBase}/chat/stream`)
          url.searchParams.set('job_id', pendingChatJob.job_id)
          if (cursor > 0) url.searchParams.set('last_event_id', String(cursor))
          const res = await fetch(url.toString(), {
            signal: controller.signal,
            headers: { Accept: 'text/event-stream' },
          })
          if (!res.ok || !res.body) {
            const text = await res.text()
            throw new Error(text || `状态码 ${res.status}`)
          }
          const reader = res.body.getReader()
          const decoder = new TextDecoder('utf-8')
          let buffer = ''
          let sawEventInCurrentStream = false
          while (!stopped) {
            const { done, value } = await reader.read()
            if (done) break
            buffer += decoder.decode(value, { stream: true })
            const normalized = buffer.replace(/\r/g, '')
            const parts = normalized.split('\n\n')
            buffer = parts.pop() || ''
            for (const raw of parts) {
              const block = raw.trim()
              if (!block || block.startsWith(':')) continue
              let eventType = ''
              let eventId = 0
              const dataLines: string[] = []
              for (const line of block.split('\n')) {
                if (line.startsWith('event:')) {
                  eventType = line.slice(6).trim()
                } else if (line.startsWith('id:')) {
                  const parsed = Number(line.slice(3).trim())
                  if (Number.isFinite(parsed) && parsed > 0) eventId = parsed
                } else if (line.startsWith('data:')) {
                  dataLines.push(line.slice(5).trim())
                }
              }
              if (!dataLines.length) continue
              const rawData = dataLines.join('\n')
              const payloadEnvelope = parseChatStreamEnvelope(rawData)
              if (!payloadEnvelope) continue
              if (payloadEnvelope.eventVersion !== CHAT_STREAM_EVENT_VERSION) {
                clearAssistantRenderTimer()
                setPlaceholderContent('检测到新版流协议，已自动切换到稳态轮询…')
                startFallbackPolling()
                return
              }
              const finalType = String(eventType || payloadEnvelope.eventType || '').trim()
              if (!finalType) continue
              const payload = payloadEnvelope.payload
              const finalEventId = Number(payloadEnvelope.eventId ?? eventId ?? 0)
              if (!Number.isFinite(finalEventId) || finalEventId <= cursor) continue
              sawEventInCurrentStream = true
              applyStreamEvent(finalType, payload, finalEventId)
              if (stopped) break
            }
          }
          if (stopped || !pendingChatJobRef.current?.job_id) return
          const statusRes = await fetch(`${apiBase}/chat/status?job_id=${encodeURIComponent(pendingChatJob.job_id)}`, {
            signal: controller.signal,
          })
          if (!statusRes.ok) {
            const text = await statusRes.text()
            throw new Error(text || `状态码 ${statusRes.status}`)
          }
          const statusData = (await statusRes.json()) as ChatJobStatus
          if (statusData.status === 'done') {
            clearAssistantRenderTimer()
            finishSuccess(statusData.reply || assistantText || '')
            stopped = true
            return
          }
          if (statusData.status === 'failed' || statusData.status === 'cancelled') {
            clearAssistantRenderTimer()
            finishFailure(statusData.error_detail || statusData.error || '请求失败')
            stopped = true
            return
          }
          const lanePos = Number(statusData.lane_queue_position || 0)
          const laneSize = Number(statusData.lane_queue_size || 0)
          if (statusData.status === 'queued') {
            setChatQueueHint(lanePos > 0 ? `排队中，前方 ${lanePos} 条（队列 ${laneSize}）` : '排队中...')
            setPendingStreamStage('排队中...')
          } else if (statusData.status === 'processing') {
            setChatQueueHint('处理中...')
            setPendingStreamStage('处理中...')
          }
          if (sawEventInCurrentStream) reconnectAttempts = 0
          reconnectAttempts += 1
          if (reconnectAttempts >= 4) {
            startFallbackPolling()
            return
          }
          await streamSleep(Math.min(3000, reconnectAttempts * 800))
        } catch (err: unknown) {
          clearAssistantRenderTimer()
          if (controller.signal.aborted || stopped) return
          reconnectAttempts += 1
          if (reconnectAttempts >= 4) {
            startFallbackPolling()
            return
          }
          await streamSleep(Math.min(3000, reconnectAttempts * 800))
        }
      }
      clearAssistantRenderTimer()
    }

    void runStream()

    return () => {
      stopped = true
      controller.abort()
      setChatQueueHint('')
      setPendingStreamStage('')
      setPendingToolRuns([])
      if (pollCleanup) pollCleanup()
    }
  }, [pendingChatJob, pendingChatJob?.job_id, apiBase, authToken, refreshTeacherSessions, activeSessionId, setMessages, setPendingChatJob, setChatQueueHint, setPendingStreamStage, setPendingToolRuns, setSending])

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
  }
}
