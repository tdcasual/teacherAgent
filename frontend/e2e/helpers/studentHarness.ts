import { expect, type Page } from '@playwright/test'

type LocalStorageState = Record<string, string | null | undefined>

type StudentHistoryMessage = {
  ts?: string
  role?: string
  content?: string
}

type StudentHistoryBySession = Record<string, StudentHistoryMessage[]>

type SetupApiMocksOptions = {
  historyBySession?: StudentHistoryBySession
}

type OpenStudentAppOptions = {
  clearLocalStorage?: boolean
  stateOverrides?: LocalStorageState
  apiMocks?: SetupApiMocksOptions
}

const defaultLocalStorageState: LocalStorageState = {
  apiBaseStudent: 'http://localhost:8000',
  studentSidebarOpen: 'true',
  studentAuthAccessToken: 'e2e-student-token',
  verifiedStudent: JSON.stringify({
    student_id: 'S001',
    student_name: '测试学生',
    class_name: '高二1班',
  }),
}

export const setupStudentState = async (
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

export const setupBasicStudentApiMocks = async (
  page: Page,
  options: SetupApiMocksOptions = {},
) => {
  const historyBySession = options.historyBySession ?? {
    main: [{ ts: new Date().toISOString(), role: 'assistant', content: '欢迎使用学生端' }],
    s2: [{ ts: new Date().toISOString(), role: 'assistant', content: '会话二内容' }],
  }
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
    const pathname = url.pathname

    if (method === 'GET' && pathname === '/assignment/today') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, assignment: null }),
      })
      return
    }

    if (method === 'GET' && pathname === '/student/history/sessions') {
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
          student_id: 'S001',
          sessions,
          next_cursor: null,
          total: sessions.length,
        }),
      })
      return
    }

    if (method === 'GET' && pathname === '/student/history/session') {
      const sessionId = url.searchParams.get('session_id') || 'main'
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          student_id: 'S001',
          session_id: sessionId,
          messages: historyBySession[sessionId] || [],
          next_cursor: -1,
        }),
      })
      return
    }

    if (pathname === '/student/session/view-state' && method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, state: viewStatePayload }),
      })
      return
    }

    if (pathname === '/student/session/view-state' && (method === 'POST' || method === 'PUT')) {
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

    if (pathname === '/chat/start' && method === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          job_id: 'student_job_1',
          status: 'done',
          reply: '已收到',
        }),
      })
      return
    }

    if (pathname === '/chat/status' && method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: 'student_job_1',
          status: 'done',
          reply: '已收到',
        }),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true }),
    })
  })
}

export const openStudentApp = async (
  page: Page,
  options: OpenStudentAppOptions = {},
) => {
  await setupStudentState(page, {
    clearLocalStorage: options.clearLocalStorage,
    stateOverrides: options.stateOverrides,
  })
  await setupBasicStudentApiMocks(page, options.apiMocks)
  await page.goto('/')
  await expect(page.getByRole('button', { name: '发送' })).toBeVisible()
}
