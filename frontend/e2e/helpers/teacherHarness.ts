import { expect, type Page } from '@playwright/test'

export const TEACHER_COMPOSER_PLACEHOLDER =
  '输入指令或问题，使用 $ 查看技能。回车发送，上档键+回车换行'

type LocalStorageState = Record<string, string | null | undefined>

export type ChatStartPayload = {
  request_id?: string
  session_id?: string
  messages?: Array<{ role?: string; content?: string }>
  role?: string
  teacher_id?: string
  skill_id?: string
}

export type ChatStatusPayload = {
  job_id: string
  status: 'queued' | 'processing' | 'done' | 'failed' | 'cancelled' | string
  reply?: string
  error?: string
  error_detail?: string
  lane_queue_position?: number
  lane_queue_size?: number
}

export type TeacherHistoryMessage = {
  ts?: string
  role?: string
  content?: string
}

export type MockSkill = {
  id: string
  title: string
  desc: string
  prompts: string[]
  examples: string[]
  allowed_roles: string[]
}

export const defaultMockSkills: MockSkill[] = [
  {
    id: 'physics-teacher-ops',
    title: '教学运营',
    desc: '老师运营流程',
    prompts: ['请总结班级学习情况'],
    examples: ['查看班级趋势'],
    allowed_roles: ['teacher'],
  },
  {
    id: 'physics-homework-generator',
    title: '作业生成',
    desc: '生成分层作业',
    prompts: ['生成静电场作业'],
    examples: ['高二静电场 8 题'],
    allowed_roles: ['teacher'],
  },
]

const defaultLocalStorageState: LocalStorageState = {
  teacherMainView: 'chat',
  teacherSessionSidebarOpen: 'false',
  teacherSkillsOpen: 'true',
  teacherWorkbenchTab: 'skills',
  teacherSkillPinned: 'false',
  teacherActiveSkillId: 'physics-teacher-ops',
  apiBaseTeacher: 'http://localhost:8000',
}

type ChatStartHookResult = {
  jobId?: string
  status?: string
  reply?: string
  laneId?: string
  laneQueuePosition?: number
  laneQueueSize?: number
}

type SetupApiMocksOptions = {
  skills?: MockSkill[]
  historyBySession?: Record<string, TeacherHistoryMessage[]>
  statusFailuresBeforeDone?: number
  onChatStart?: (args: { payload: ChatStartPayload; callIndex: number }) => ChatStartHookResult | void
  onChatStatus?: (args: { jobId: string; callCount: number; startPayload?: ChatStartPayload }) => ChatStatusPayload | void
}

export type SetupApiMocksResult = {
  chatStartCalls: ChatStartPayload[]
  getStatusCallCount: (jobId: string) => number
}

type OpenTeacherAppOptions = {
  clearLocalStorage?: boolean
  stateOverrides?: LocalStorageState
  apiMocks?: SetupApiMocksOptions
}

export const buildHistoryMessages = (count: number) => {
  const messages: TeacherHistoryMessage[] = []
  for (let i = 1; i <= count; i += 1) {
    messages.push({
      ts: new Date(Date.now() - (count - i) * 1000).toISOString(),
      role: i % 2 === 0 ? 'user' : 'assistant',
      content: `历史消息-${i} ` + '内容 '.repeat(18),
    })
  }
  return messages
}

export const setupTeacherState = async (
  page: Page,
  options: { clearLocalStorage?: boolean; stateOverrides?: LocalStorageState } = {},
) => {
  const clearLocalStorage = options.clearLocalStorage ?? true
  const stateOverrides = options.stateOverrides ?? {}

  await page.addInitScript(
    ({ clear, defaults, overrides }) => {
      if (clear) localStorage.clear()
      const state = { ...defaults, ...overrides }
      for (const [key, rawValue] of Object.entries(state)) {
        if (rawValue === undefined) continue
        if (rawValue === null) {
          localStorage.removeItem(key)
          continue
        }
        localStorage.setItem(key, String(rawValue))
      }
    },
    {
      clear: clearLocalStorage,
      defaults: defaultLocalStorageState,
      overrides: stateOverrides,
    },
  )
}

export const setupBasicTeacherApiMocks = async (
  page: Page,
  options: SetupApiMocksOptions = {},
): Promise<SetupApiMocksResult> => {
  const skills = options.skills ?? defaultMockSkills
  const historyBySession = options.historyBySession ?? { main: [] }
  const chatStartCalls: ChatStartPayload[] = []
  const chatStartByJob = new Map<string, ChatStartPayload>()
  const statusCallCountByJob = new Map<string, number>()
  const statusReplyByJob = new Map<string, string>()
  let viewStatePayload = {
    title_map: {},
    hidden_ids: [],
    active_session_id: 'main',
    updated_at: new Date().toISOString(),
  }

  await page.route('http://localhost:8000/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const method = request.method().toUpperCase()
    const path = url.pathname

    if (method === 'GET' && path === '/skills') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ skills }),
      })
      return
    }

    if (method === 'GET' && path === '/teacher/history/sessions') {
      const sessions = Object.entries(historyBySession).map(([sessionId, messages]) => {
        const latest = messages[messages.length - 1]
        return {
          session_id: sessionId,
          updated_at: latest?.ts || new Date().toISOString(),
          preview: latest?.content || '',
          message_count: messages.length,
        }
      })
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          teacher_id: 'T001',
          sessions,
          next_cursor: null,
          total: sessions.length,
        }),
      })
      return
    }

    if (method === 'GET' && path === '/teacher/history/session') {
      const sessionId = url.searchParams.get('session_id') || 'main'
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          teacher_id: 'T001',
          session_id: sessionId,
          messages: historyBySession[sessionId] || [],
          next_cursor: -1,
        }),
      })
      return
    }

    if (path === '/teacher/session/view-state' && method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, state: viewStatePayload }),
      })
      return
    }

    if (path === '/teacher/session/view-state' && method === 'PUT') {
      const body = JSON.parse(request.postData() || '{}') as { state?: Record<string, unknown> }
      const state = body?.state && typeof body.state === 'object' ? body.state : {}
      viewStatePayload = {
        title_map: (state.title_map as Record<string, string>) || {},
        hidden_ids: Array.isArray(state.hidden_ids) ? (state.hidden_ids as string[]) : [],
        active_session_id: 'main',
        updated_at: new Date().toISOString(),
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, state: viewStatePayload }),
      })
      return
    }

    if (method === 'POST' && path === '/chat/start') {
      const payload = JSON.parse(request.postData() || '{}') as ChatStartPayload
      chatStartCalls.push(payload)
      const callIndex = chatStartCalls.length
      const hook = options.onChatStart?.({ payload, callIndex }) || {}
      const jobId = hook.jobId || `job_${callIndex}`
      const finalStatus = hook.status || 'queued'
      const lastUserText = payload.messages?.[payload.messages.length - 1]?.content || ''
      const reply = hook.reply || `回执：${lastUserText}`

      chatStartByJob.set(jobId, payload)
      statusReplyByJob.set(jobId, reply)

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          job_id: jobId,
          status: finalStatus,
          lane_id: hook.laneId || 'teacher-main',
          lane_queue_position: hook.laneQueuePosition ?? 0,
          lane_queue_size: hook.laneQueueSize ?? 1,
        }),
      })
      return
    }

    if (method === 'GET' && path === '/chat/status') {
      const jobId = url.searchParams.get('job_id') || 'unknown_job'
      const callCount = (statusCallCountByJob.get(jobId) || 0) + 1
      statusCallCountByJob.set(jobId, callCount)

      if (callCount <= (options.statusFailuresBeforeDone || 0)) {
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'temporary status error' }),
        })
        return
      }

      const custom = options.onChatStatus?.({
        jobId,
        callCount,
        startPayload: chatStartByJob.get(jobId),
      })
      const fallback: ChatStatusPayload = {
        job_id: jobId,
        status: 'done',
        reply: statusReplyByJob.get(jobId) || '已收到。',
      }

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(custom || fallback),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true }),
    })
  })

  return {
    chatStartCalls,
    getStatusCallCount: (jobId: string) => statusCallCountByJob.get(jobId) || 0,
  }
}

export const openTeacherApp = async (
  page: Page,
  options: OpenTeacherAppOptions = {},
): Promise<SetupApiMocksResult> => {
  await setupTeacherState(page, {
    clearLocalStorage: options.clearLocalStorage,
    stateOverrides: options.stateOverrides,
  })

  const mocks = await setupBasicTeacherApiMocks(page, options.apiMocks)
  await page.goto('/')
  await expect(page.getByRole('button', { name: '发送' })).toBeVisible()
  await expect(page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER)).toBeVisible()
  return mocks
}
