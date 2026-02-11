import { useCallback, useEffect, useMemo, useRef } from 'react'
import { absolutizeChartImageUrls, renderMarkdown } from './markdown'
import { stripTransientPendingBubbles, withPendingChatOverlay } from './pendingOverlay'
import { buildSkill, fallbackSkills, TEACHER_GREETING } from './catalog'
import { parseInvocationInput } from './invocation'
import { decideSkillRouting } from './requestRouting'
import { startVisibilityAwareBackoffPolling } from '../../../../shared/visibilityBackoffPolling'
import { safeLocalStorageGetItem } from '../../utils/storage'
import { makeId } from '../../utils/id'
import { nowTime, timeFromIso } from '../../utils/time'
import type {
  ChatJobStatus,
  ChatStartResult,
  Message,
  PendingChatJob,
  RenderedMessage,
  Skill,
  SkillResponse,
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
  sending: boolean
  activeSkillId: string
  skillPinned: boolean
  skillList: Skill[]
  pendingChatJob: PendingChatJob | null
  memoryStatusFilter: string
  skillsOpen: boolean
  workbenchTab: WorkbenchTab

  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
  setSending: React.Dispatch<React.SetStateAction<boolean>>
  setActiveSessionId: React.Dispatch<React.SetStateAction<string>>
  setPendingChatJob: React.Dispatch<React.SetStateAction<PendingChatJob | null>>
  setChatQueueHint: React.Dispatch<React.SetStateAction<string>>
  setComposerWarning: React.Dispatch<React.SetStateAction<string>>
  setInput: React.Dispatch<React.SetStateAction<string>>

  // Session state setters (from useTeacherSessionState — useReducer-based)
  setHistorySessions: (value: any[] | ((prev: any[]) => any[])) => void
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

  // Skill setters (from useState — React.Dispatch compatible)
  setSkillList: React.Dispatch<React.SetStateAction<Skill[]>>
  setSkillsLoading: React.Dispatch<React.SetStateAction<boolean>>
  setSkillsError: React.Dispatch<React.SetStateAction<string>>

  // Callbacks from parent
  chooseSkill: (skillId: string, pinned?: boolean) => void
  enableAutoScroll: () => void
  setWheelScrollZone: (zone: WheelScrollZone) => void
}

export function useTeacherChatApi(params: UseTeacherChatApiParams) {
  const {
    apiBase,
    activeSessionId,
    messages,
    sending,
    activeSkillId,
    skillPinned,
    skillList,
    pendingChatJob,
    memoryStatusFilter,
    skillsOpen,
    workbenchTab,
    setMessages,
    setSending,
    setActiveSessionId,
    setPendingChatJob,
    setChatQueueHint,
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

  // ── Ref sync effects ──────────────────────────────────────────────────
  useEffect(() => { activeSessionRef.current = activeSessionId }, [activeSessionId])
  useEffect(() => { pendingChatJobRef.current = pendingChatJob }, [pendingChatJob])

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

  // ── appendMessage / updateMessage helpers ─────────────────────────────
  const appendMessage = useCallback(
    (roleType: 'user' | 'assistant', content: string) => {
      setMessages((prev) => [...prev, { id: makeId(), role: roleType, content, time: nowTime() }])
    },
    [setMessages],
  )

  const updateMessage = useCallback(
    (id: string, patch: Partial<Message>) => {
      setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...patch } : m)))
    },
    [setMessages],
  )

  // ── refreshTeacherSessions ────────────────────────────────────────────
  const refreshTeacherSessions = useCallback(
    async (mode: 'reset' | 'more' = 'reset') => {
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
            const existingIds = new Set(prev.map((item: any) => item.session_id))
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
              .map((id) => prev.find((item: any) => item.session_id === id) || { session_id: id, updated_at: new Date().toISOString(), message_count: 0, preview: '' })
            const seeded = [...draftItems, ...serverSessions]
            const seen = new Set(seeded.map((item: any) => item.session_id))
            for (const item of prev) {
              if (seen.has((item as any).session_id)) continue
              seeded.push(item)
            }
            return seeded
          })
        }
      } catch (err: any) {
        if (requestNo !== historyRequestRef.current) return
        setHistoryError(err.message || String(err))
      } finally {
        if (requestNo !== historyRequestRef.current) return
        setHistoryLoading(false)
      }
    },
    [apiBase, setHistoryLoading, setHistoryError, setLocalDraftSessionIds, setHistoryCursor, setHistoryHasMore, setHistorySessions, syncHistoryCursor, syncHistoryHasMore],
  )

  // ── loadTeacherSessionMessages ────────────────────────────────────────
  const loadTeacherSessionMessages = useCallback(
    async (sessionId: string, cursor: number, append: boolean) => {
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
          setMessages(
            mappedWithPending.length
              ? mappedWithPending
              : [
                  {
                    id: makeId(),
                    role: 'assistant',
                    content: TEACHER_GREETING,
                    time: nowTime(),
                  },
                ],
          )
        }
      } catch (err: any) {
        if (requestNo !== sessionRequestRef.current || activeSessionRef.current !== targetSessionId) return
        setSessionError(err.message || String(err))
      } finally {
        if (requestNo !== sessionRequestRef.current || activeSessionRef.current !== targetSessionId) return
        setSessionLoading(false)
      }
    },
    [apiBase, setSessionLoading, setSessionError, setSessionCursor, setSessionHasMore, setMessages],
  )

  // ── refreshMemoryProposals ────────────────────────────────────────────
  const refreshMemoryProposals = useCallback(async () => {
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
    } catch (err: any) {
      setProposalError(err.message || String(err))
    } finally {
      setProposalLoading(false)
    }
  }, [apiBase, memoryStatusFilter, setProposalLoading, setProposalError, setProposals])

  // ── refreshMemoryInsights ─────────────────────────────────────────────
  const refreshMemoryInsights = useCallback(async () => {
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
  }, [apiBase, setMemoryInsights])

  // ── fetchSkills ───────────────────────────────────────────────────────
  const fetchSkills = useCallback(async () => {
    setSkillsLoading(true)
    setSkillsError('')
    try {
      const res = await fetch(`${apiBase}/skills`)
      if (!res.ok) throw new Error(`状态码 ${res.status}`)
      const data = (await res.json()) as SkillResponse
      const raw = Array.isArray(data.skills) ? data.skills : []
      const teacherSkills = raw.filter((skill) => {
        const roles = skill.allowed_roles
        return !Array.isArray(roles) || roles.includes('teacher')
      })
      if (teacherSkills.length === 0) {
        setSkillList(fallbackSkills)
        return
      }
      setSkillList(teacherSkills.map((skill) => buildSkill(skill)))
    } catch (err: any) {
      setSkillsError(err.message || '无法加载技能列表')
      setSkillList(fallbackSkills)
    } finally {
      setSkillsLoading(false)
    }
  }, [apiBase, setSkillsLoading, setSkillsError, setSkillList])

  // ── submitMessage ─────────────────────────────────────────────────────
  const submitMessage = useCallback(
    async (inputText: string) => {
      if (pendingChatJob?.job_id) return
      const trimmed = inputText.trim()
      if (!trimmed) return
      const parsedInvocation = parseInvocationInput(trimmed, {
        knownSkillIds: skillList.map((item) => item.id),
        activeSkillId: activeSkillId || 'physics-teacher-ops',
      })
      const cleanedText = parsedInvocation.cleanedInput.trim()
      if (!cleanedText) {
        setComposerWarning('请在召唤后补充问题内容。')
        return
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
          }),
        })
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `状态码 ${res.status}`)
        }
        const data = (await res.json()) as ChatStartResult
        if (!data?.job_id) throw new Error('任务编号缺失')
        const lanePos = Number(data.lane_queue_position || 0)
        const laneSize = Number(data.lane_queue_size || 0)
        setChatQueueHint(lanePos > 0 ? `排队中，前方 ${lanePos} 条（队列 ${laneSize}）` : '处理中...')
        setPendingChatJob({
          job_id: data.job_id,
          request_id: requestId,
          placeholder_id: placeholderId,
          user_text: cleanedText,
          session_id: sessionId,
          lane_id: data.lane_id,
          created_at: Date.now(),
        })
      } catch (err: any) {
        setMessages((prev) => prev.map((m) => (m.id === placeholderId ? { ...m, content: `抱歉，请求失败：${err.message || err}`, time: nowTime() } : m)))
        setSending(false)
        setChatQueueHint('')
        setPendingChatJob(null)
      }
    },
    [
      pendingChatJob?.job_id, skillList, activeSkillId, skillPinned, activeSessionId, messages, apiBase,
      setComposerWarning, chooseSkill, setActiveSessionId, setWheelScrollZone, enableAutoScroll,
      setMessages, setInput, setSending, setChatQueueHint, setPendingChatJob,
    ],
  )

  // ── Pending chat job polling effect ───────────────────────────────────
  useEffect(() => {
    if (!pendingChatJob?.job_id) return
    const cleanup = startVisibilityAwareBackoffPolling(
      async () => {
        if (pendingChatJob.session_id && activeSessionId && pendingChatJob.session_id !== activeSessionId) {
          return 'continue'
        }

        const res = await fetch(`${apiBase}/chat/status?job_id=${encodeURIComponent(pendingChatJob.job_id)}`)
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `状态码 ${res.status}`)
        }
        const data = (await res.json()) as ChatJobStatus
        if (data.status === 'done') {
          setMessages((prev) => {
            const overlaid = withPendingChatOverlay(prev, pendingChatJob, activeSessionId || pendingChatJob.session_id || 'main')
            return overlaid.map((msg) =>
              msg.id === pendingChatJob.placeholder_id ? { ...msg, content: data.reply || '已收到。', time: nowTime() } : msg,
            )
          })
          setPendingChatJob(null)
          setChatQueueHint('')
          setSending(false)
          void refreshTeacherSessions()
          return 'stop'
        }
        if (data.status === 'failed' || data.status === 'cancelled') {
          const msg = data.error_detail || data.error || '请求失败'
          setMessages((prev) => {
            const overlaid = withPendingChatOverlay(prev, pendingChatJob, activeSessionId || pendingChatJob.session_id || 'main')
            return overlaid.map((item) =>
              item.id === pendingChatJob.placeholder_id ? { ...item, content: `抱歉，请求失败：${msg}`, time: nowTime() } : item,
            )
          })
          setPendingChatJob(null)
          setChatQueueHint('')
          setSending(false)
          return 'stop'
        }
        const lanePos = Number((data as any).lane_queue_position || 0)
        const laneSize = Number((data as any).lane_queue_size || 0)
        if (data.status === 'queued') {
          setChatQueueHint(lanePos > 0 ? `排队中，前方 ${lanePos} 条（队列 ${laneSize}）` : '排队中...')
        } else if (data.status === 'processing') {
          setChatQueueHint('处理中...')
        } else {
          setChatQueueHint('')
        }
        return 'continue'
      },
      (err) => {
        const msg = (err as any)?.message || String(err)
        setMessages((prev) => {
          const overlaid = withPendingChatOverlay(prev, pendingChatJob, activeSessionId || pendingChatJob.session_id || 'main')
          return overlaid.map((item) =>
            item.id === pendingChatJob.placeholder_id ? { ...item, content: `网络波动，正在重试…（${msg}）`, time: nowTime() } : item,
          )
        })
      },
      { kickMode: 'direct' },
    )

    return () => {
      setChatQueueHint('')
      cleanup()
    }
  }, [pendingChatJob?.job_id, apiBase, refreshTeacherSessions, activeSessionId, setMessages, setPendingChatJob, setChatQueueHint, setSending])

  // ── Session refresh on mount ──────────────────────────────────────────
  useEffect(() => {
    void refreshTeacherSessions()
  }, [refreshTeacherSessions])

  // ── Load messages when activeSessionId changes ────────────────────────
  useEffect(() => {
    if (!activeSessionId) return
    void loadTeacherSessionMessages(activeSessionId, -1, false)
  }, [activeSessionId, loadTeacherSessionMessages])

  // ── Session refresh 30s interval ──────────────────────────────────────
  useEffect(() => {
    const timer = window.setInterval(() => {
      void refreshTeacherSessions()
    }, 30000)
    return () => window.clearInterval(timer)
  }, [refreshTeacherSessions])

  // ── Memory refresh effects ────────────────────────────────────────────
  useEffect(() => {
    if (!skillsOpen) return
    if (workbenchTab !== 'memory') return
    void refreshMemoryProposals()
    void refreshMemoryInsights()
  }, [skillsOpen, workbenchTab, refreshMemoryInsights, refreshMemoryProposals])

  // ── Skill fetch on mount ──────────────────────────────────────────────
  useEffect(() => {
    void fetchSkills()
  }, [fetchSkills])

  // ── Skill fetch when workbench skills tab opens ───────────────────────
  useEffect(() => {
    if (!skillsOpen || workbenchTab !== 'skills') return
    void fetchSkills()
  }, [skillsOpen, workbenchTab, fetchSkills])

  // ── Skill polling 30s when skills tab is open ─────────────────────────
  useEffect(() => {
    if (!skillsOpen || workbenchTab !== 'skills') return
    const timer = window.setInterval(() => {
      void fetchSkills()
    }, 30000)
    return () => window.clearInterval(timer)
  }, [skillsOpen, workbenchTab, fetchSkills])

  // ── Return ────────────────────────────────────────────────────────────
  return {
    refreshTeacherSessions,
    loadTeacherSessionMessages,
    refreshMemoryProposals,
    refreshMemoryInsights,
    submitMessage,
    appendMessage,
    updateMessage,
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
