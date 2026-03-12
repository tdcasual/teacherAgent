import { act, renderHook, waitFor } from '@testing-library/react'
import * as React from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type {
  ExecutionTimelineEntry,
  Message,
  PendingChatJob,
  PendingToolRun,
  Skill,
  StudentMemoryInsightsResponse,
  StudentMemoryProposal,
  TeacherHistorySession,
  TeacherMemoryInsightsResponse,
  TeacherMemoryProposal,
  WheelScrollZone,
} from '../../appTypes'
import { TEACHER_AUTH_ACCESS_TOKEN_KEY } from '../auth/teacherAuth'
import { useTeacherChatApi, type UseTeacherChatApiParams } from './useTeacherChatApi'

type StreamLogs = {
  streamStages: string[]
  queueHints: string[]
  toolRunSnapshots: PendingToolRun[][]
}

const noop = () => undefined

type LocalStorageMock = {
  getItem: (key: string) => string | null
  setItem: (key: string, value: string) => void
  removeItem: (key: string) => void
  clear: () => void
}

const jsonResponse = (payload: unknown, status = 200): Response =>
  new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })

const toSseEvent = (eventId: number, eventType: string, payload: Record<string, unknown>): string =>
  `id:${eventId}\nevent:${eventType}\ndata:${JSON.stringify({ type: eventType, event_id: eventId, payload })}\n\n`

const toRawSseEvent = (eventId: number, eventType: string, rawData: string): string =>
  `id:${eventId}\nevent:${eventType}\ndata:${rawData}\n\n`

const sseResponse = (body: string): Response => {
  const encoder = new TextEncoder()
  return new Response(
    new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(body))
        controller.close()
      },
    }),
    {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
    },
  )
}

const toUrl = (input: RequestInfo | URL): string => {
  if (typeof input === 'string') return input
  if (input instanceof URL) return input.toString()
  return input.url
}

const installLocalStorageMock = (): LocalStorageMock => {
  const store = new Map<string, string>()
  const localStorageMock: LocalStorageMock = {
    getItem: (key) => (store.has(key) ? store.get(key) || null : null),
    setItem: (key, value) => {
      store.set(key, String(value))
    },
    removeItem: (key) => {
      store.delete(key)
    },
    clear: () => {
      store.clear()
    },
  }
  vi.stubGlobal('localStorage', localStorageMock)
  return localStorageMock
}

const renderTeacherChatHarness = (apiBase = 'http://localhost:8000') =>
  renderHook(() => {
    const [messages, setMessages] = React.useState<Message[]>([])
    const [activeSessionId, setActiveSessionId] = React.useState('main')
    const [pendingChatJob, setPendingChatJob] = React.useState<PendingChatJob | null>(null)
    const [, setSending] = React.useState(false)
    const [, setInput] = React.useState('')
    const [composerWarning, setComposerWarning] = React.useState('')
    const [chatQueueHint, setChatQueueHintState] = React.useState('')
    const [pendingStreamStage, setPendingStreamStageState] = React.useState('')
    const [pendingToolRuns, setPendingToolRunsState] = React.useState<PendingToolRun[]>([])
    const [executionTimeline, setExecutionTimeline] = React.useState<ExecutionTimelineEntry[]>([])
    const [skillList, setSkillList] = React.useState<Skill[]>([
      {
        id: 'physics-teacher-ops',
        title: '考试分析',
        desc: 'ops',
        instructions: 'ops',
        prompts: [],
        examples: [],
        keywords: [],
        source_type: 'system',
      },
      {
        id: 'physics-homework-generator',
        title: '作业生成',
        desc: 'homework',
        instructions: 'homework',
        prompts: [],
        examples: [],
        keywords: [],
        source_type: 'system',
      },
    ])
    const [, setSkillsLoading] = React.useState(false)
    const [, setSkillsError] = React.useState('')

    const [historySessions, setHistorySessionsState] = React.useState<TeacherHistorySession[]>([])
    const [, setHistoryLoading] = React.useState(false)
    const [, setHistoryError] = React.useState('')
    const [, setHistoryCursor] = React.useState(0)
    const [, setHistoryHasMore] = React.useState(false)
    const [, setLocalDraftSessionIds] = React.useState<string[]>([])
    const [, setSessionLoading] = React.useState(false)
    const [, setSessionError] = React.useState('')
    const [, setSessionCursor] = React.useState(0)
    const [, setSessionHasMore] = React.useState(false)

    const [, setProposalLoading] = React.useState(false)
    const [, setProposalError] = React.useState('')
    const [, setProposals] = React.useState<TeacherMemoryProposal[]>([])
    const [, setMemoryInsights] = React.useState<TeacherMemoryInsightsResponse | null>(null)
    const [, setStudentProposalLoading] = React.useState(false)
    const [, setStudentProposalError] = React.useState('')
    const [, setStudentProposals] = React.useState<StudentMemoryProposal[]>([])
    const [, setStudentMemoryInsights] = React.useState<StudentMemoryInsightsResponse | null>(null)

    const logsRef = React.useRef<StreamLogs>({ streamStages: [], queueHints: [], toolRunSnapshots: [] })

    const trackedSetPendingStreamStage = React.useCallback<React.Dispatch<React.SetStateAction<string>>>((value) => {
      setPendingStreamStageState((prev) => {
        const next = typeof value === 'function' ? value(prev) : value
        logsRef.current.streamStages.push(next)
        return next
      })
    }, [])

    const trackedSetChatQueueHint = React.useCallback<React.Dispatch<React.SetStateAction<string>>>((value) => {
      setChatQueueHintState((prev) => {
        const next = typeof value === 'function' ? value(prev) : value
        logsRef.current.queueHints.push(next)
        return next
      })
    }, [])

    const trackedSetPendingToolRuns = React.useCallback<React.Dispatch<React.SetStateAction<PendingToolRun[]>>>((value) => {
      setPendingToolRunsState((prev) => {
        const next = typeof value === 'function' ? value(prev) : value
        logsRef.current.toolRunSnapshots.push(next.map((item) => ({ ...item })))
        return next
      })
    }, [])

    const api = useTeacherChatApi({
      apiBase,
      activeSessionId,
      messages,
      activeSkillId: 'physics-teacher-ops',
      skillPinned: false,
      skillList,
      pendingChatJob,
      memoryStatusFilter: 'all',
      studentMemoryStatusFilter: 'all',
      studentMemoryStudentFilter: '',
      skillsOpen: false,
      workbenchTab: 'workflow',
      setMessages,
      setSending,
      setActiveSessionId,
      setPendingChatJob,
      setChatQueueHint: trackedSetChatQueueHint,
      setPendingStreamStage: trackedSetPendingStreamStage,
      setPendingToolRuns: trackedSetPendingToolRuns,
      setExecutionTimeline,
      setComposerWarning,
      setInput,
      setHistorySessions: setHistorySessionsState,
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
      chooseSkill: noop,
      enableAutoScroll: noop,
      setWheelScrollZone: ((_: WheelScrollZone) => undefined) as UseTeacherChatApiParams['setWheelScrollZone'],
    })

    return {
      api,
      messages,
      pendingChatJob,
      pendingStreamStage,
      pendingToolRuns,
      executionTimeline,
      chatQueueHint,
      streamLogs: logsRef.current,
      historySessions,
      composerWarning,
    }
  })

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('useTeacherChatApi stream mapping', () => {
  it('shows a low-noise workflow explanation when the backend resolves a capability', async () => {
    const localStorageMock = installLocalStorageMock()
    localStorageMock.setItem(TEACHER_AUTH_ACCESS_TOKEN_KEY, 'token')
    localStorageMock.setItem('teacherAuthSubject', JSON.stringify({ teacher_id: 'teacher-1', teacher_name: 'Teacher 1' }))

    const streamBody = [
      toSseEvent(1, 'job.processing', {}),
      toSseEvent(2, 'workflow.resolved', {
        requested_skill_id: '',
        effective_skill_id: 'physics-homework-generator',
        reason: 'auto_rule',
        confidence: 0.64,
      }),
      toSseEvent(3, 'job.done', { reply: '已完成' }),
    ].join('')

    const fetchMock = vi.fn(async (input: RequestInfo | URL): Promise<Response> => {
      const url = toUrl(input)
      if (url.endsWith('/chat/start')) {
        return jsonResponse({ ok: true, job_id: 'job-2', status: 'queued' })
      }
      if (url.includes('/chat/stream')) {
        return sseResponse(streamBody)
      }
      if (url.includes('/teacher/history/sessions')) {
        return jsonResponse({ ok: true, teacher_id: 'teacher-1', sessions: [], next_cursor: null })
      }
      if (url.includes('/skills')) {
        return jsonResponse({
          skills: [
            { id: 'physics-teacher-ops', title: 'Physics Ops', desc: 'ops' },
            { id: 'physics-homework-generator', title: '作业生成', desc: 'homework' },
          ],
        })
      }
      return jsonResponse({ ok: true })
    })
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderTeacherChatHarness()

    await act(async () => {
      const ok = await result.current.api.submitMessage('请帮我生成作业')
      expect(ok).toBe(true)
    })

    await waitFor(() => {
      expect(result.current.composerWarning).toContain('作业生成')
    })
    expect(result.current.composerWarning).toContain('已按')
  })

  it('shows a light fallback hint when the backend falls back to the default workflow', async () => {
    const localStorageMock = installLocalStorageMock()
    localStorageMock.setItem(TEACHER_AUTH_ACCESS_TOKEN_KEY, 'token')
    localStorageMock.setItem('teacherAuthSubject', JSON.stringify({ teacher_id: 'teacher-1', teacher_name: 'Teacher 1' }))

    const streamBody = [
      toSseEvent(1, 'job.processing', {}),
      toSseEvent(2, 'workflow.resolved', {
        requested_skill_id: '',
        effective_skill_id: 'physics-teacher-ops',
        reason: 'role_default',
        confidence: 0.28,
      }),
      toSseEvent(3, 'job.done', { reply: '已完成' }),
    ].join('')

    const fetchMock = vi.fn(async (input: RequestInfo | URL): Promise<Response> => {
      const url = toUrl(input)
      if (url.endsWith('/chat/start')) {
        return jsonResponse({ ok: true, job_id: 'job-default', status: 'queued' })
      }
      if (url.includes('/chat/stream')) {
        return sseResponse(streamBody)
      }
      if (url.includes('/teacher/history/sessions')) {
        return jsonResponse({ ok: true, teacher_id: 'teacher-1', sessions: [], next_cursor: null })
      }
      if (url.includes('/skills')) {
        return jsonResponse({
          skills: [
            { id: 'physics-teacher-ops', title: '考试分析', desc: 'ops' },
          ],
        })
      }
      return jsonResponse({ ok: true })
    })
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderTeacherChatHarness()

    await act(async () => {
      const ok = await result.current.api.submitMessage('我想要一个分析方案')
      expect(ok).toBe(true)
    })

    await waitFor(() => {
      expect(result.current.composerWarning).toContain('未明确指定')
    })
    expect(result.current.composerWarning).toContain('考试分析')
  })

  it('reflects queue + tool progress and completes assistant reply from SSE events', async () => {
    const localStorageMock = installLocalStorageMock()
    localStorageMock.setItem(TEACHER_AUTH_ACCESS_TOKEN_KEY, 'token')
    localStorageMock.setItem('teacherAuthSubject', JSON.stringify({ teacher_id: 'teacher-1', teacher_name: 'Teacher 1' })) 

    const streamBody = [
      toSseEvent(1, 'job.queued', { lane_queue_position: 2, lane_queue_size: 4 }),
      toSseEvent(2, 'job.processing', {}),
      toSseEvent(3, 'tool.start', { tool_name: 'exam.get', tool_call_id: 'call-1' }),
      toSseEvent(4, 'tool.finish', { tool_name: 'exam.get', tool_call_id: 'call-1', ok: true, duration_ms: 80 }),
      toSseEvent(5, 'tool.start', { tool_name: 'exam.analysis.get', tool_call_id: 'call-2' }),
      toSseEvent(6, 'tool.finish', { tool_name: 'exam.analysis.get', tool_call_id: 'call-2', ok: false, error: 'timeout' }),
      toSseEvent(7, 'assistant.delta', { delta: '第一段' }),
      toSseEvent(8, 'assistant.delta', { delta: '第二段' }),
      toSseEvent(9, 'job.done', { reply: '第一段第二段' }),
    ].join('')

    const fetchMock = vi.fn(async (input: RequestInfo | URL): Promise<Response> => {
      const url = toUrl(input)
      if (url.endsWith('/chat/start')) {
        return jsonResponse({
          ok: true,
          job_id: 'job-1',
          status: 'queued',
          lane_id: 'teacher-default',
          lane_queue_position: 2,
          lane_queue_size: 4,
        })
      }
      if (url.includes('/chat/stream')) {
        return sseResponse(streamBody)
      }
      if (url.includes('/teacher/history/sessions')) {
        return jsonResponse({ ok: true, teacher_id: 'teacher-1', sessions: [], next_cursor: null })
      }
      if (url.includes('/teacher/history/session')) {
        return jsonResponse({
          ok: true,
          teacher_id: 'teacher-1',
          session_id: 'main',
          messages: [],
          next_cursor: 0,
        })
      }
      if (url.endsWith('/skills')) {
        return jsonResponse({ skills: [] })
      }
      if (url.includes('/chat/status')) {
        return jsonResponse({ job_id: 'job-1', status: 'done', reply: 'fallback reply' })
      }
      return jsonResponse({ ok: true })
    })

    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderTeacherChatHarness()

    await act(async () => {
      const ok = await result.current.api.submitMessage('请给出结果')
      expect(ok).toBe(true)
    })

    await waitFor(() => {
      expect(result.current.pendingChatJob).toBeNull()
    })

    await waitFor(() => {
      expect(result.current.messages.some((item) => item.role === 'assistant' && item.content === '第一段第二段')).toBe(true)
    })

    expect(result.current.pendingStreamStage).toBe('')
    expect(result.current.pendingToolRuns).toEqual([])
    expect(result.current.chatQueueHint).toBe('')
    expect(result.current.executionTimeline.map((item) => item.type)).toEqual([
      'job.queued',
      'job.processing',
      'tool.start',
      'tool.finish',
      'tool.start',
      'tool.finish',
      'job.done',
    ])
    expect(result.current.executionTimeline[result.current.executionTimeline.length - 1]?.summary).toBe('任务完成')

    expect(result.current.streamLogs.streamStages).toContain('排队中...')
    expect(result.current.streamLogs.streamStages).toContain('处理中...')
    expect(result.current.streamLogs.queueHints).toContain('排队中，前方 2 条（队列 4）')
    expect(result.current.streamLogs.queueHints).toContain('处理中...')

    const snapshots = result.current.streamLogs.toolRunSnapshots
    expect(snapshots.some((runs) => runs.some((run) => run.name === 'exam.get' && run.status === 'running'))).toBe(true)
    expect(
      snapshots.some((runs) =>
        runs.some((run) => run.name === 'exam.get' && run.status === 'ok' && run.durationMs === 80),
      ),
    ).toBe(true)
    expect(
      snapshots.some((runs) =>
        runs.some(
          (run) =>
            run.name === 'exam.analysis.get' && run.status === 'failed' && run.error === 'timeout',
        ),
      ),
    ).toBe(true)

    expect(fetchMock.mock.calls.some(([input]) => toUrl(input).includes('/chat/status'))).toBe(false)
    expect(result.current.historySessions).toEqual([])
  })

  it('falls back to polling when stream reconnect keeps failing', async () => {
    vi.useFakeTimers()
    const localStorageMock = installLocalStorageMock()
    localStorageMock.setItem(TEACHER_AUTH_ACCESS_TOKEN_KEY, 'token')
    localStorageMock.setItem('teacherAuthSubject', JSON.stringify({ teacher_id: 'teacher-1', teacher_name: 'Teacher 1' })) 

    let streamAttempts = 0
    let statusCalls = 0
    const fetchMock = vi.fn(async (input: RequestInfo | URL): Promise<Response> => {
      const url = toUrl(input)
      if (url.endsWith('/chat/start')) {
        return jsonResponse({
          ok: true,
          job_id: 'job-2',
          status: 'queued',
          lane_id: 'teacher-default',
          lane_queue_position: 1,
          lane_queue_size: 3,
        })
      }
      if (url.includes('/chat/stream')) {
        streamAttempts += 1
        throw new Error('stream unavailable')
      }
      if (url.includes('/chat/status')) {
        statusCalls += 1
        return jsonResponse({
          job_id: 'job-2',
          status: 'done',
          reply: 'fallback reply',
          execution_timeline: [
            { type: 'job.queued', summary: '排队中（前方 1）', ts: '2026-03-12T09:00:00Z' },
            { type: 'job.done', summary: '任务完成', ts: '2026-03-12T09:00:05Z' },
          ],
        })
      }
      if (url.includes('/teacher/history/sessions')) {
        return jsonResponse({ ok: true, teacher_id: 'teacher-1', sessions: [], next_cursor: null })
      }
      if (url.includes('/teacher/history/session')) {
        return jsonResponse({
          ok: true,
          teacher_id: 'teacher-1',
          session_id: 'main',
          messages: [],
          next_cursor: 0,
        })
      }
      if (url.endsWith('/skills')) {
        return jsonResponse({ skills: [] })
      }
      return jsonResponse({ ok: true })
    })
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderTeacherChatHarness()

    await act(async () => {
      const ok = await result.current.api.submitMessage('请走回退流程')
      expect(ok).toBe(true)
    })

    await act(async () => {
      await vi.advanceTimersByTimeAsync(6000)
      await Promise.resolve()
    })

    expect(streamAttempts).toBeGreaterThanOrEqual(4)
    expect(statusCalls).toBeGreaterThan(0)
    expect(result.current.pendingChatJob).toBeNull()
    expect(result.current.messages.some((item) => item.role === 'assistant' && item.content === 'fallback reply')).toBe(true)
    expect(result.current.pendingStreamStage).toBe('')
    expect(result.current.pendingToolRuns).toEqual([])
    expect(result.current.chatQueueHint).toBe('')
    expect(result.current.executionTimeline.map((item) => item.summary)).toEqual(['排队中（前方 1）', '任务完成'])
    expect(fetchMock.mock.calls.some(([input]) => toUrl(input).includes('/chat/status'))).toBe(true)
  })

  it('reconnects stream with last_event_id to continue unfinished output', async () => {
    const localStorageMock = installLocalStorageMock()
    localStorageMock.setItem(TEACHER_AUTH_ACCESS_TOKEN_KEY, 'token')
    localStorageMock.setItem('teacherAuthSubject', JSON.stringify({ teacher_id: 'teacher-1', teacher_name: 'Teacher 1' })) 

    const firstStreamBody = [
      toSseEvent(1, 'job.processing', {}),
      toSseEvent(2, 'assistant.delta', { delta: '第一段' }),
    ].join('')
    const secondStreamBody = [
      toSseEvent(3, 'assistant.delta', { delta: '第二段' }),
      toSseEvent(4, 'job.done', { reply: '第一段第二段' }),
    ].join('')

    const streamRequestUrls: string[] = []
    let streamCalls = 0
    const fetchMock = vi.fn(async (input: RequestInfo | URL): Promise<Response> => {
      const url = toUrl(input)
      if (url.endsWith('/chat/start')) {
        return jsonResponse({
          ok: true,
          job_id: 'job-3',
          status: 'queued',
          lane_id: 'teacher-default',
          lane_queue_position: 0,
          lane_queue_size: 1,
        })
      }
      if (url.includes('/chat/stream')) {
        streamCalls += 1
        streamRequestUrls.push(url)
        return streamCalls === 1 ? sseResponse(firstStreamBody) : sseResponse(secondStreamBody)
      }
      if (url.includes('/teacher/history/sessions')) {
        return jsonResponse({ ok: true, teacher_id: 'teacher-1', sessions: [], next_cursor: null })
      }
      if (url.includes('/teacher/history/session')) {
        return jsonResponse({
          ok: true,
          teacher_id: 'teacher-1',
          session_id: 'main',
          messages: [],
          next_cursor: 0,
        })
      }
      if (url.endsWith('/skills')) {
        return jsonResponse({ skills: [] })
      }
      if (url.includes('/chat/status')) {
        return jsonResponse({ job_id: 'job-3', status: 'processing' })
      }
      return jsonResponse({ ok: true })
    })
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderTeacherChatHarness()

    await act(async () => {
      const ok = await result.current.api.submitMessage('请验证续流')
      expect(ok).toBe(true)
    })

    await waitFor(() => {
      expect(result.current.pendingChatJob).toBeNull()
    })

    expect(streamCalls).toBeGreaterThanOrEqual(2)
    expect(streamRequestUrls[0] || '').not.toContain('last_event_id=')
    expect(streamRequestUrls[1] || '').toContain('last_event_id=2')
    expect(result.current.messages.some((item) => item.role === 'assistant' && item.content === '第一段第二段')).toBe(true)
    expect(fetchMock.mock.calls.some(([input]) => toUrl(input).includes('/chat/status'))).toBe(true)
  })

  it('does not spam tool-state updates for assistant delta-only chunks', async () => {
    const localStorageMock = installLocalStorageMock()
    localStorageMock.setItem(TEACHER_AUTH_ACCESS_TOKEN_KEY, 'token')
    localStorageMock.setItem('teacherAuthSubject', JSON.stringify({ teacher_id: 'teacher-1', teacher_name: 'Teacher 1' })) 

    const streamBody = [
      toSseEvent(1, 'job.processing', {}),
      toSseEvent(2, 'assistant.delta', { delta: 'A' }),
      toSseEvent(3, 'assistant.delta', { delta: 'B' }),
      toSseEvent(4, 'assistant.delta', { delta: 'C' }),
      toSseEvent(5, 'assistant.delta', { delta: 'D' }),
      toSseEvent(6, 'assistant.delta', { delta: 'E' }),
      toSseEvent(7, 'job.done', { reply: 'ABCDE' }),
    ].join('')

    const fetchMock = vi.fn(async (input: RequestInfo | URL): Promise<Response> => {
      const url = toUrl(input)
      if (url.endsWith('/chat/start')) {
        return jsonResponse({
          ok: true,
          job_id: 'job-4',
          status: 'queued',
          lane_id: 'teacher-default',
          lane_queue_position: 0,
          lane_queue_size: 1,
        })
      }
      if (url.includes('/chat/stream')) {
        return sseResponse(streamBody)
      }
      if (url.includes('/teacher/history/sessions')) {
        return jsonResponse({ ok: true, teacher_id: 'teacher-1', sessions: [], next_cursor: null })
      }
      if (url.includes('/teacher/history/session')) {
        return jsonResponse({
          ok: true,
          teacher_id: 'teacher-1',
          session_id: 'main',
          messages: [],
          next_cursor: 0,
        })
      }
      if (url.endsWith('/skills')) {
        return jsonResponse({ skills: [] })
      }
      return jsonResponse({ ok: true })
    })
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderTeacherChatHarness()

    await act(async () => {
      const ok = await result.current.api.submitMessage('请输出 ABCDE')
      expect(ok).toBe(true)
    })

    await waitFor(() => {
      expect(result.current.pendingChatJob).toBeNull()
    })

    const snapshots = result.current.streamLogs.toolRunSnapshots
    // Expected stable behavior: no tool events => only init/teardown snapshots, not per-delta spam.
    expect(snapshots.length).toBeLessThanOrEqual(3)
    expect(snapshots.every((item) => item.length === 0)).toBe(true)
    expect(result.current.messages.some((item) => item.role === 'assistant' && item.content === 'ABCDE')).toBe(true)
  })

  it('resolves terminal status after clean stream EOF to avoid reconnect spin', async () => {
    const localStorageMock = installLocalStorageMock()
    localStorageMock.setItem(TEACHER_AUTH_ACCESS_TOKEN_KEY, 'token')
    localStorageMock.setItem('teacherAuthSubject', JSON.stringify({ teacher_id: 'teacher-1', teacher_name: 'Teacher 1' })) 

    const firstStreamBody = [
      toSseEvent(1, 'job.processing', {}),
      toSseEvent(2, 'assistant.delta', { delta: '部分输出' }),
    ].join('')

    let streamCalls = 0
    let statusCalls = 0
    const fetchMock = vi.fn(async (input: RequestInfo | URL): Promise<Response> => {
      const url = toUrl(input)
      if (url.endsWith('/chat/start')) {
        return jsonResponse({
          ok: true,
          job_id: 'job-5',
          status: 'queued',
          lane_id: 'teacher-default',
          lane_queue_position: 0,
          lane_queue_size: 1,
        })
      }
      if (url.includes('/chat/stream')) {
        streamCalls += 1
        return sseResponse(firstStreamBody)
      }
      if (url.includes('/chat/status')) {
        statusCalls += 1
        return jsonResponse({ job_id: 'job-5', status: 'done', reply: 'EOF 后完成' })
      }
      if (url.includes('/teacher/history/sessions')) {
        return jsonResponse({ ok: true, teacher_id: 'teacher-1', sessions: [], next_cursor: null })
      }
      if (url.includes('/teacher/history/session')) {
        return jsonResponse({
          ok: true,
          teacher_id: 'teacher-1',
          session_id: 'main',
          messages: [],
          next_cursor: 0,
        })
      }
      if (url.endsWith('/skills')) {
        return jsonResponse({ skills: [] })
      }
      return jsonResponse({ ok: true })
    })
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderTeacherChatHarness()

    await act(async () => {
      const ok = await result.current.api.submitMessage('请验证 EOF 终态兜底')
      expect(ok).toBe(true)
    })

    await waitFor(() => {
      expect(result.current.pendingChatJob).toBeNull()
    })

    expect(streamCalls).toBe(1)
    expect(statusCalls).toBeGreaterThan(0)
    expect(result.current.messages.some((item) => item.role === 'assistant' && item.content === 'EOF 后完成')).toBe(true)
  })

  it('falls back to polling on unsupported stream event version', async () => {
    const localStorageMock = installLocalStorageMock()
    localStorageMock.setItem(TEACHER_AUTH_ACCESS_TOKEN_KEY, 'token')
    localStorageMock.setItem('teacherAuthSubject', JSON.stringify({ teacher_id: 'teacher-1', teacher_name: 'Teacher 1' })) 

    const streamBody = toRawSseEvent(
      1,
      'assistant.delta',
      JSON.stringify({
        event_id: 1,
        type: 'assistant.delta',
        event_version: 2,
        payload: { delta: 'ignored' },
      }),
    )

    let streamCalls = 0
    let statusCalls = 0
    const fetchMock = vi.fn(async (input: RequestInfo | URL): Promise<Response> => {
      const url = toUrl(input)
      if (url.endsWith('/chat/start')) {
        return jsonResponse({
          ok: true,
          job_id: 'job-6',
          status: 'queued',
          lane_id: 'teacher-default',
          lane_queue_position: 0,
          lane_queue_size: 1,
        })
      }
      if (url.includes('/chat/stream')) {
        streamCalls += 1
        return sseResponse(streamBody)
      }
      if (url.includes('/chat/status')) {
        statusCalls += 1
        return jsonResponse({ job_id: 'job-6', status: 'done', reply: '版本降级成功' })
      }
      if (url.includes('/teacher/history/sessions')) {
        return jsonResponse({ ok: true, teacher_id: 'teacher-1', sessions: [], next_cursor: null })
      }
      if (url.includes('/teacher/history/session')) {
        return jsonResponse({
          ok: true,
          teacher_id: 'teacher-1',
          session_id: 'main',
          messages: [],
          next_cursor: 0,
        })
      }
      if (url.endsWith('/skills')) {
        return jsonResponse({ skills: [] })
      }
      return jsonResponse({ ok: true })
    })
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderTeacherChatHarness()

    await act(async () => {
      const ok = await result.current.api.submitMessage('请验证版本门禁')
      expect(ok).toBe(true)
    })

    await waitFor(() => {
      expect(result.current.pendingChatJob).toBeNull()
    })

    expect(streamCalls).toBe(1)
    expect(statusCalls).toBeGreaterThan(0)
    expect(result.current.messages.some((item) => item.role === 'assistant' && item.content === '版本降级成功')).toBe(true)
  })

  it('consumes SSE metadata when envelope omits type and event_id', async () => {
    const localStorageMock = installLocalStorageMock()
    localStorageMock.setItem(TEACHER_AUTH_ACCESS_TOKEN_KEY, 'token')
    localStorageMock.setItem('teacherAuthSubject', JSON.stringify({ teacher_id: 'teacher-1', teacher_name: 'Teacher 1' })) 

    const streamBody = [
      toRawSseEvent(1, 'assistant.delta', JSON.stringify({ payload: { delta: 'A' }, event_version: 1 })),
      toRawSseEvent(2, 'job.done', JSON.stringify({ payload: { reply: 'A' }, event_version: 1 })),
    ].join('')

    const fetchMock = vi.fn(async (input: RequestInfo | URL): Promise<Response> => {
      const url = toUrl(input)
      if (url.endsWith('/chat/start')) {
        return jsonResponse({
          ok: true,
          job_id: 'job-7',
          status: 'queued',
          lane_id: 'teacher-default',
          lane_queue_position: 0,
          lane_queue_size: 1,
        })
      }
      if (url.includes('/chat/stream')) {
        return sseResponse(streamBody)
      }
      if (url.includes('/teacher/history/sessions')) {
        return jsonResponse({ ok: true, teacher_id: 'teacher-1', sessions: [], next_cursor: null })
      }
      if (url.includes('/teacher/history/session')) {
        return jsonResponse({
          ok: true,
          teacher_id: 'teacher-1',
          session_id: 'main',
          messages: [],
          next_cursor: 0,
        })
      }
      if (url.endsWith('/skills')) {
        return jsonResponse({ skills: [] })
      }
      return jsonResponse({ ok: true })
    })
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderTeacherChatHarness()

    await act(async () => {
      const ok = await result.current.api.submitMessage('请验证 envelope 兼容')
      expect(ok).toBe(true)
    })

    await waitFor(() => {
      expect(result.current.pendingChatJob).toBeNull()
    })

    expect(result.current.messages.some((item) => item.role === 'assistant' && item.content === 'A')).toBe(true)
    expect(fetchMock.mock.calls.some(([input]) => toUrl(input).includes('/chat/status'))).toBe(false)
  })

  it('ignores id-less events when cursor already advanced', async () => {
    const localStorageMock = installLocalStorageMock()
    localStorageMock.setItem(TEACHER_AUTH_ACCESS_TOKEN_KEY, 'token')
    localStorageMock.setItem('teacherAuthSubject', JSON.stringify({ teacher_id: 'teacher-1', teacher_name: 'Teacher 1' })) 

    const firstStreamBody = [
      toSseEvent(1, 'assistant.delta', { delta: 'A' }),
      'event: assistant.delta\ndata: {"payload":{"delta":"B"},"event_version":1}\n\n',
    ].join('')
    const secondStreamBody = [
      toSseEvent(2, 'job.done', {}),
    ].join('')

    let streamCalls = 0
    const fetchMock = vi.fn(async (input: RequestInfo | URL): Promise<Response> => {
      const url = toUrl(input)
      if (url.endsWith('/chat/start')) {
        return jsonResponse({
          ok: true,
          job_id: 'job-8',
          status: 'queued',
          lane_id: 'teacher-default',
          lane_queue_position: 0,
          lane_queue_size: 1,
        })
      }
      if (url.includes('/chat/stream')) {
        streamCalls += 1
        return streamCalls === 1 ? sseResponse(firstStreamBody) : sseResponse(secondStreamBody)
      }
      if (url.includes('/chat/status')) {
        return jsonResponse({ job_id: 'job-8', status: 'processing' })
      }
      if (url.includes('/teacher/history/sessions')) {
        return jsonResponse({ ok: true, teacher_id: 'teacher-1', sessions: [], next_cursor: null })
      }
      if (url.includes('/teacher/history/session')) {
        return jsonResponse({
          ok: true,
          teacher_id: 'teacher-1',
          session_id: 'main',
          messages: [],
          next_cursor: 0,
        })
      }
      if (url.endsWith('/skills')) {
        return jsonResponse({ skills: [] })
      }
      return jsonResponse({ ok: true })
    })
    vi.stubGlobal('fetch', fetchMock)

    const { result } = renderTeacherChatHarness()

    await act(async () => {
      const ok = await result.current.api.submitMessage('请验证 id-less 事件兜底')
      expect(ok).toBe(true)
    })

    await waitFor(() => {
      expect(result.current.pendingChatJob).toBeNull()
    })

    expect(result.current.messages.some((item) => item.role === 'assistant' && item.content === 'A')).toBe(true)
    expect(result.current.messages.some((item) => item.role === 'assistant' && item.content === 'AB')).toBe(false)
  })
})
