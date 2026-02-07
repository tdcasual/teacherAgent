import { expect } from '@playwright/test'
import type { MatrixCase, MatrixCaseRunner } from './helpers/e2eMatrixCases'
import { registerMatrixCases } from './helpers/e2eMatrixCases'
import {
  TEACHER_COMPOSER_PLACEHOLDER,
  openTeacherApp,
  setupBasicTeacherApiMocks,
  setupTeacherState,
} from './helpers/teacherHarness'

const chatCases: MatrixCase[] = [
  {
    id: 'A001',
    priority: 'P0',
    title: 'IME Enter does not submit during composition',
    given: 'Composer is in IME composing state',
    when: 'Press Enter',
    then: 'No request is sent to /chat/start',
  },
  {
    id: 'A002',
    priority: 'P0',
    title: 'Start request failure shows recoverable error',
    given: '/chat/start returns 500',
    when: 'Click send',
    then: 'Error is shown and composer is re-enabled',
  },
  {
    id: 'A003',
    priority: 'P0',
    title: 'Processing status transitions to final reply',
    given: '/chat/status returns processing then done',
    when: 'Send one message',
    then: 'Placeholder message is replaced by final reply',
  },
  {
    id: 'A004',
    priority: 'P0',
    title: 'Failed status clears pending state',
    given: '/chat/status returns failed with detail',
    when: 'Send one message',
    then: 'Readable failure is shown and pending state is cleared',
  },
  {
    id: 'A005',
    priority: 'P0',
    title: 'Cancelled status allows next send',
    given: '/chat/status returns cancelled',
    when: 'Send one message',
    then: 'Message is marked cancelled and next send is allowed',
  },
  {
    id: 'A006',
    priority: 'P1',
    title: 'Queued response shows queue metrics',
    given: '/chat/start returns lane queue position and size',
    when: 'Send one message',
    then: 'Queue hint displays position and size',
  },
  {
    id: 'A007',
    priority: 'P1',
    title: 'Visibility restore triggers immediate poll',
    given: 'A pending chat job exists from a queued start response',
    when: 'Document visibility changes to visible',
    then: 'Polling runs immediately and state refreshes',
  },
  {
    id: 'A008',
    priority: 'P0',
    title: 'Duplicate send is blocked while pending',
    given: 'A pending chat job exists',
    when: 'Click send repeatedly',
    then: 'Only one /chat/start call is made',
  },
  {
    id: 'A009',
    priority: 'P1',
    title: 'Context window contract holds for long inputs',
    given: 'Long conversation history exists',
    when: 'Send a very long prompt',
    then: 'Payload context is trimmed to contract limits',
  },
  {
    id: 'A010',
    priority: 'P1',
    title: 'Last valid invocation token wins',
    given: 'Composer contains multiple @agent and $skill tokens',
    when: 'Send message',
    then: 'Payload uses the last valid agent and skill tokens',
  },
  {
    id: 'A011',
    priority: 'P1',
    title: 'Mention insertion in middle keeps spacing',
    given: 'Cursor is in the middle of existing text',
    when: 'Insert mention token from panel',
    then: 'Surrounding text and spaces remain correct',
  },
  {
    id: 'A012',
    priority: 'P2',
    title: 'Mixed locale text parsing remains stable',
    given: 'Prompt includes mixed CJK and ASCII punctuation',
    when: 'Send message',
    then: 'Content is not corrupted or truncated',
  },
  {
    id: 'A013',
    priority: 'P1',
    title: 'Invocation-only input is blocked',
    given: 'Composer only contains invocation tokens',
    when: 'Click send',
    then: 'Message is not sent and input remains visible',
  },
  {
    id: 'A014',
    priority: 'P1',
    title: 'Shift+Enter inserts newline, Enter submits',
    given: 'Composer has one line',
    when: 'Press Shift+Enter then Enter',
    then: 'Newline is inserted first and message sends on Enter',
  },
  {
    id: 'A015',
    priority: 'P0',
    title: 'Delayed start survives session switch',
    given: '/chat/start is delayed and source session has pending message',
    when: 'Switch to another session and back',
    then: 'Source session keeps user message and placeholder',
  },
  {
    id: 'A016',
    priority: 'P1',
    title: 'Unknown terminal status falls back gracefully',
    given: '/chat/status returns unknown terminal value',
    when: 'Send message',
    then: 'UI enters fallback error state and does not hang',
  },
]

const sessionCases: MatrixCase[] = [
  {
    id: 'B001',
    priority: 'P0',
    title: 'New session becomes active immediately',
    given: 'Session sidebar is open',
    when: 'Click new session',
    then: 'A session_* id appears and is active',
  },
  {
    id: 'B002',
    priority: 'P1',
    title: 'Rename updates list, search, and view-state',
    given: 'An existing session supports rename',
    when: 'Rename the session',
    then: 'Title and search index update and view-state syncs',
  },
  {
    id: 'B003',
    priority: 'P0',
    title: 'Archive moves session out of active list',
    given: 'A session can be archived',
    when: 'Confirm archive action',
    then: 'Session disappears from active and appears in archived view',
  },
  {
    id: 'B004',
    priority: 'P1',
    title: 'Archive cancel keeps state unchanged',
    given: 'Archive confirm dialog is shown',
    when: 'Dismiss dialog',
    then: 'Menu closes and session state does not change',
  },
  {
    id: 'B005',
    priority: 'P1',
    title: 'Session search matches id, title, and preview',
    given: 'Multiple sessions with different ids and previews',
    when: 'Enter search text',
    then: 'Matching sessions are filtered correctly',
  },
  {
    id: 'B006',
    priority: 'P1',
    title: 'Session menu closes on outside click and Escape',
    given: 'Session menu is open',
    when: 'Click outside or press Escape',
    then: 'Menu closes and aria-expanded resets',
  },
  {
    id: 'B007',
    priority: 'P0',
    title: 'Pending reply stays in source session',
    given: 'Main and secondary sessions exist',
    when: 'Send in main and switch to secondary',
    then: 'Reply is attached only to main session',
  },
  {
    id: 'B008',
    priority: 'P1',
    title: 'Session-local transient errors do not leak',
    given: 'Session A has a transient error state',
    when: 'Switch to session B',
    then: 'Session B has no leaked error banner',
  },
  {
    id: 'B009',
    priority: 'P1',
    title: 'Load-more sessions disabled at end cursor',
    given: 'Session list has no next cursor',
    when: 'Inspect load-more control',
    then: 'Button is disabled with terminal label',
  },
  {
    id: 'B010',
    priority: 'P1',
    title: 'Load older messages disabled at beginning',
    given: 'Current session has no older cursor',
    when: 'Inspect load-older control',
    then: 'Button is disabled with no-more label',
  },
  {
    id: 'B011',
    priority: 'P0',
    title: 'Draft session persists across page reload',
    given: 'Draft session exists locally but not server-persisted',
    when: 'Reload page',
    then: 'Draft session remains visible in sidebar',
  },
  {
    id: 'B012',
    priority: 'P2',
    title: 'Long sidebar list does not scroll bleed',
    given: 'Sidebar has long session list',
    when: 'Perform continuous scroll',
    then: 'Main page does not scroll through the sidebar',
  },
]

const implementations: Partial<Record<string, MatrixCaseRunner>> = {
  A001: async ({ page }) => {
    const { chatStartCalls } = await openTeacherApp(page)
    const composer = page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER)

    await composer.fill('输入法回车保护')
    await composer.focus()
    await composer.evaluate((node) => {
      const event = new KeyboardEvent('keydown', {
        key: 'Enter',
        bubbles: true,
        cancelable: true,
        isComposing: true,
      })
      node.dispatchEvent(event)
    })

    await page.waitForTimeout(150)
    expect(chatStartCalls.length).toBe(0)
  },

  A002: async ({ page }) => {
    let startCalls = 0

    await setupTeacherState(page)
    await setupBasicTeacherApiMocks(page)
    await page.route('http://localhost:8000/chat/start', async (route) => {
      startCalls += 1
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'start backend unavailable' }),
      })
    })

    await page.goto('/')
    await page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER).fill('start 失败回退')
    await page.getByRole('button', { name: '发送' }).click()

    await expect.poll(() => startCalls).toBe(1)
    await expect(page.getByText('抱歉，请求失败')).toBeVisible()
    await expect(page.getByRole('button', { name: '发送' })).toBeEnabled()
  },

  A003: async ({ page }) => {
    const prompt = '轮询转终态'
    const mocks = await openTeacherApp(page, {
      apiMocks: {
        onChatStatus: ({ jobId, callCount }) =>
          callCount < 2
            ? { job_id: jobId, status: 'processing' }
            : {
                job_id: jobId,
                status: 'done',
                reply: `回执：${prompt}`,
              },
      },
    })

    await page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER).fill(prompt)
    await page.getByRole('button', { name: '发送' }).click()

    await expect(page.locator('.messages').getByText(`回执：${prompt}`)).toBeVisible()
    await expect.poll(() => mocks.getStatusCallCount('job_1')).toBeGreaterThan(1)
  },

  A004: async ({ page }) => {
    await openTeacherApp(page, {
      apiMocks: {
        onChatStatus: ({ jobId }) => ({
          job_id: jobId,
          status: 'failed',
          error: '上游失败',
          error_detail: 'mock failed detail',
        }),
      },
    })

    await page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER).fill('失败状态处理')
    await page.getByRole('button', { name: '发送' }).click()

    await expect(page.getByText('抱歉，请求失败：mock failed detail')).toBeVisible()
    await expect(page.getByRole('button', { name: '发送' })).toBeEnabled()
    await expect.poll(async () => page.evaluate(() => localStorage.getItem('teacherPendingChatJob'))).toBeNull()
  },

  A005: async ({ page }) => {
    const { chatStartCalls } = await openTeacherApp(page, {
      apiMocks: {
        onChatStatus: ({ jobId }) => ({
          job_id: jobId,
          status: 'cancelled',
          error: '任务取消',
        }),
      },
    })

    const composer = page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER)
    await composer.fill('第一次发送')
    await page.getByRole('button', { name: '发送' }).click()
    await expect(page.getByText('抱歉，请求失败：任务取消')).toBeVisible()

    await composer.fill('第二次发送')
    await page.getByRole('button', { name: '发送' }).click()
    await expect.poll(() => chatStartCalls.length).toBe(2)
  },

  A008: async ({ page }) => {
    const { chatStartCalls } = await openTeacherApp(page, {
      apiMocks: {
        onChatStatus: ({ jobId }) => ({ job_id: jobId, status: 'processing' }),
      },
    })

    const composer = page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER)
    const sendBtn = page.getByRole('button', { name: '发送' })

    await composer.fill('重复点击拦截')
    await sendBtn.click()
    await sendBtn.click()
    await sendBtn.click()

    await expect.poll(() => chatStartCalls.length).toBe(1)
  },

  A015: async ({ page }) => {
    const historyBySession = {
      main: [{ ts: new Date().toISOString(), role: 'assistant', content: 'main 初始化' }],
      s2: [{ ts: new Date().toISOString(), role: 'assistant', content: 's2 初始化' }],
    }
    let statusCalls = 0
    let delayedResolved = false

    await openTeacherApp(page, {
      stateOverrides: {
        teacherSessionSidebarOpen: 'true',
      },
      apiMocks: {
        historyBySession,
      },
    })

    await page.route('http://localhost:8000/chat/start', async (route) => {
      await page.waitForTimeout(350)
      delayedResolved = true
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          job_id: 'job_delayed_start_1',
          status: 'queued',
          lane_id: 'teacher-main',
          lane_queue_position: 0,
          lane_queue_size: 1,
        }),
      })
    })

    await page.route('http://localhost:8000/chat/status**', async (route) => {
      statusCalls += 1
      if (statusCalls < 2) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ job_id: 'job_delayed_start_1', status: 'processing' }),
        })
        return
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: 'job_delayed_start_1',
          status: 'done',
          reply: '回执：延迟切会话',
        }),
      })
    })

    const composer = page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER)
    await composer.fill('延迟切会话')
    await page.getByRole('button', { name: '发送' }).click()

    const otherSession = page.locator('.session-item').filter({ hasText: 's2' }).first()
    await otherSession.locator('.session-select').click()

    const mainSession = page.locator('.session-item').filter({ hasText: 'main' }).first()
    await mainSession.locator('.session-select').click()

    await expect.poll(() => delayedResolved).toBe(true)
    await expect(page.locator('.messages').getByText('延迟切会话')).toBeVisible()
    await expect(page.locator('.messages').getByText('回执：延迟切会话')).toBeVisible()
  },

  B001: async ({ page }) => {
    await openTeacherApp(page, {
      stateOverrides: {
        teacherSessionSidebarOpen: 'true',
      },
    })

    await page.getByRole('button', { name: '新建' }).click()

    const firstSessionId = (await page.locator('.session-item .session-id').first().textContent())?.trim() || ''
    expect(firstSessionId.startsWith('session_')).toBe(true)
    await expect(page.locator('.session-item.active').first()).toContainText(firstSessionId)
  },

  B003: async ({ page }) => {
    await openTeacherApp(page, {
      stateOverrides: {
        teacherSessionSidebarOpen: 'true',
      },
    })

    await page.getByRole('button', { name: '新建' }).click()
    const targetId = (await page.locator('.session-item .session-id').first().textContent())?.trim() || ''
    expect(targetId.startsWith('session_')).toBe(true)

    page.once('dialog', async (dialog) => {
      await dialog.accept()
    })
    await page.locator('.session-menu-trigger').first().click()
    await page.getByRole('button', { name: '归档', exact: true }).click()

    await expect(page.locator('.session-id', { hasText: targetId })).toHaveCount(0)
    await page.getByRole('button', { name: '查看归档' }).click()
    await expect(page.locator('.session-id', { hasText: targetId })).toBeVisible()
  },

  B007: async ({ page }) => {
    const sourceText = '跨会话隔离'

    await setupTeacherState(page, {
      stateOverrides: {
        teacherSessionSidebarOpen: 'true',
      },
    })
    await setupBasicTeacherApiMocks(page, {
      historyBySession: {
        main: [{ ts: new Date().toISOString(), role: 'assistant', content: 'main 初始化' }],
        s2: [{ ts: new Date().toISOString(), role: 'assistant', content: 's2 初始化' }],
      },
      onChatStatus: ({ jobId, callCount }) =>
        callCount < 3
          ? { job_id: jobId, status: 'processing' }
          : {
              job_id: jobId,
              status: 'done',
              reply: `回执：${sourceText}`,
            },
    })

    await page.goto('/')
    await page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER).fill(sourceText)
    await page.getByRole('button', { name: '发送' }).click()

    const secondSession = page.locator('.session-item').filter({ hasText: 's2' }).first()
    await secondSession.locator('.session-select').click()
    await expect(page.locator('.messages').getByText(`回执：${sourceText}`)).toHaveCount(0)

    const mainSession = page.locator('.session-item').filter({ hasText: 'main' }).first()
    await mainSession.locator('.session-select').click()
    await expect(page.locator('.messages').getByText(`回执：${sourceText}`)).toBeVisible()
  },

  B011: async ({ page }) => {
    await page.addInitScript(() => {
      const FLAG = '__teacher_reload_test_bootstrapped__'
      if (sessionStorage.getItem(FLAG) === '1') return
      sessionStorage.setItem(FLAG, '1')
      localStorage.clear()
      localStorage.setItem('teacherMainView', 'chat')
      localStorage.setItem('teacherSessionSidebarOpen', 'true')
      localStorage.setItem('teacherSkillsOpen', 'true')
      localStorage.setItem('teacherWorkbenchTab', 'skills')
      localStorage.setItem('teacherSkillPinned', 'false')
      localStorage.setItem('teacherActiveSkillId', 'physics-teacher-ops')
      localStorage.setItem('teacherActiveAgentId', 'default')
      localStorage.setItem('apiBaseTeacher', 'http://localhost:8000')
    })

    await page.route('http://localhost:8000/**', async (route) => {
      const request = route.request()
      const url = new URL(request.url())
      const method = request.method().toUpperCase()
      const path = url.pathname

      if (method === 'GET' && path === '/skills') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            skills: [
              {
                id: 'physics-teacher-ops',
                title: '教学运营',
                desc: '老师运营流程',
                prompts: ['请总结班级学习情况'],
                examples: ['查看班级趋势'],
                allowed_roles: ['teacher'],
              },
            ],
          }),
        })
        return
      }

      if (method === 'GET' && path === '/teacher/history/sessions') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ok: true,
            teacher_id: 'T001',
            sessions: [
              { session_id: 'main', updated_at: new Date().toISOString(), message_count: 1, preview: 'main' },
              { session_id: 's2', updated_at: new Date().toISOString(), message_count: 1, preview: 's2' },
            ],
            next_cursor: null,
            total: 2,
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
            messages: [{ ts: new Date().toISOString(), role: 'assistant', content: `history-${sessionId}` }],
            next_cursor: -1,
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

    await page.goto('/')
    await page.getByRole('button', { name: '新建' }).click()

    const draftId = (await page.locator('.session-item .session-id').first().textContent())?.trim() || ''
    expect(draftId.startsWith('session_')).toBe(true)

    await page.reload()
    await expect(page.locator('.session-id', { hasText: draftId })).toBeVisible()
  },
}

registerMatrixCases('Teacher Chat Invocation and Async', chatCases, implementations)
registerMatrixCases('Teacher Session Sidebar and History', sessionCases, implementations)
