import { expect, test } from '@playwright/test'
import { openStudentApp } from './helpers/studentHarness'

test('desktop sidebar stays collapsed after manual toggle', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await openStudentApp(page, {
    stateOverrides: {
      studentSidebarOpen: 'true',
      verifiedStudent: JSON.stringify({
        student_id: 'S001',
        student_name: '测试学生',
        class_name: '高二1班',
      }),
    },
    apiMocks: {
      historyBySession: {
        main: [{ ts: new Date().toISOString(), role: 'assistant', content: 'main' }],
      },
    },
  })

  await page.getByRole('button', { name: '收起会话' }).click()
  await page.waitForTimeout(300)

  await expect(page.getByRole('button', { name: '展开会话' })).toBeVisible()
  await expect.poll(async () =>
    page.evaluate(() => {
      const layout = document.querySelector('.student-layout')
      return Boolean(layout?.classList.contains('sidebar-collapsed'))
    }),
  ).toBe(true)

  await expect.poll(async () =>
    page.evaluate(() => localStorage.getItem('studentSidebarOpen')),
  ).toBe('false')
})

test('desktop sidebar collapsed state persists after reload', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.addInitScript(() => {
    if (!localStorage.getItem('apiBaseStudent')) localStorage.setItem('apiBaseStudent', 'http://localhost:8000')
    if (!localStorage.getItem('studentSidebarOpen')) localStorage.setItem('studentSidebarOpen', 'true')
    if (!localStorage.getItem('verifiedStudent')) {
      localStorage.setItem(
        'verifiedStudent',
        JSON.stringify({ student_id: 'S001', student_name: '测试学生', class_name: '高二1班' }),
      )
    }
  })
  await page.route('http://localhost:8000/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const method = request.method().toUpperCase()
    const path = url.pathname

    if (method === 'GET' && path === '/assignment/today') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, assignment: null }) })
      return
    }
    if (method === 'GET' && path === '/student/history/sessions') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          student_id: 'S001',
          sessions: [{ session_id: 'main', updated_at: new Date().toISOString(), message_count: 1, preview: 'main-preview' }],
          next_cursor: null,
          total: 1,
        }),
      })
      return
    }
    if (method === 'GET' && path === '/student/history/session') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          student_id: 'S001',
          session_id: 'main',
          messages: [{ ts: new Date().toISOString(), role: 'assistant', content: 'hello' }],
          next_cursor: -1,
        }),
      })
      return
    }
    if (path === '/student/session/view-state' && method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          student_id: 'S001',
          state: { title_map: {}, hidden_ids: [], active_session_id: 'main', updated_at: new Date().toISOString() },
        }),
      })
      return
    }
    if (path === '/student/session/view-state' && (method === 'POST' || method === 'PUT')) {
      const body = JSON.parse(request.postData() || '{}')
      const state = body?.state || {}
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          student_id: 'S001',
          state: {
            title_map: state.title_map || {},
            hidden_ids: Array.isArray(state.hidden_ids) ? state.hidden_ids : [],
            active_session_id: state.active_session_id || 'main',
            updated_at: new Date().toISOString(),
          },
        }),
      })
      return
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
  })
  await page.goto('/')
  await expect(page.getByRole('button', { name: '发送' })).toBeVisible()

  await page.getByRole('button', { name: '收起会话' }).click()
  await page.waitForTimeout(240)
  await expect(page.getByRole('button', { name: '展开会话' })).toBeVisible()
  await page.reload()

  await expect(page.getByRole('button', { name: '展开会话' })).toBeVisible()
  await expect.poll(async () =>
    page.evaluate(() => {
      const layout = document.querySelector('.student-layout')
      return Boolean(layout?.classList.contains('sidebar-collapsed'))
    }),
  ).toBe(true)
  await expect.poll(async () => page.evaluate(() => localStorage.getItem('studentSidebarOpen'))).toBe('false')
})

test('sidebar state write contract has no false->true rebound without second toggle', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await openStudentApp(page, {
    stateOverrides: {
      studentSidebarOpen: 'true',
      verifiedStudent: JSON.stringify({
        student_id: 'S001',
        student_name: '测试学生',
        class_name: '高二1班',
      }),
    },
    apiMocks: {
      historyBySession: {
        main: [{ ts: new Date().toISOString(), role: 'assistant', content: 'main' }],
      },
    },
  })

  await page.evaluate(() => {
    const writes: string[] = []
    const originalSetItem = window.localStorage.setItem.bind(window.localStorage)
    window.localStorage.setItem = (key: string, value: string) => {
      if (key === 'studentSidebarOpen') writes.push(String(value))
      originalSetItem(key, value)
    }
    ;(window as Window & { __sidebarOpenWrites?: string[] }).__sidebarOpenWrites = writes
  })

  await page.getByRole('button', { name: '收起会话' }).click()
  await page.waitForTimeout(450)

  const writes = await page.evaluate(() =>
    (window as Window & { __sidebarOpenWrites?: string[] }).__sidebarOpenWrites || [],
  )
  const firstFalse = writes.indexOf('false')
  expect(firstFalse).toBeGreaterThanOrEqual(0)
  expect(writes.slice(firstFalse + 1)).not.toContain('true')
  expect(writes[writes.length - 1]).toBe('false')
})

test('pending and active-session transitions remain isolated after switching sessions', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.addInitScript(() => {
    localStorage.clear()
    localStorage.setItem('apiBaseStudent', 'http://localhost:8000')
    localStorage.setItem('studentSidebarOpen', 'false')
    localStorage.setItem(
      'verifiedStudent',
      JSON.stringify({ student_id: 'S001', student_name: '测试学生', class_name: '高二1班' }),
    )
  })

  await page.route('http://localhost:8000/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const method = request.method().toUpperCase()
    const path = url.pathname

    if (method === 'GET' && path === '/assignment/today') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, assignment: null }),
      })
      return
    }

    if (method === 'GET' && path === '/student/history/sessions') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          student_id: 'S001',
          sessions: [
            { session_id: 'main', updated_at: new Date().toISOString(), message_count: 1, preview: 'history-main' },
            { session_id: 's2', updated_at: new Date().toISOString(), message_count: 1, preview: 'history-s2' },
          ],
          next_cursor: null,
          total: 2,
        }),
      })
      return
    }

    if (method === 'GET' && path === '/student/history/session') {
      const sessionId = url.searchParams.get('session_id') || 'main'
      const content = sessionId === 's2' ? 'history-s2' : 'history-main'
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          student_id: 'S001',
          session_id: sessionId,
          messages: [{ ts: new Date().toISOString(), role: 'assistant', content }],
          next_cursor: -1,
        }),
      })
      return
    }

    if (path === '/student/session/view-state') {
      if (method === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ok: true,
            student_id: 'S001',
            state: {
              title_map: {},
              hidden_ids: [],
              active_session_id: 'main',
              updated_at: new Date().toISOString(),
            },
          }),
        })
        return
      }

      if (method === 'PUT') {
        const body = JSON.parse(request.postData() || '{}')
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ok: true,
            student_id: 'S001',
            state: body.state || {
              title_map: {},
              hidden_ids: [],
              active_session_id: '',
              updated_at: new Date().toISOString(),
            },
          }),
        })
        return
      }
    }

    if (method === 'POST' && path === '/chat/start') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, job_id: 'student_pending_contract', status: 'queued' }),
      })
      return
    }

    if (method === 'GET' && path === '/chat/status') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ job_id: 'student_pending_contract', status: 'processing' }),
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
  await expect(page.locator('.message.assistant .text').filter({ hasText: 'history-main' }).first()).toBeVisible()
  await expect(page.getByRole('button', { name: '展开会话' })).toBeVisible()

  await page.locator('textarea').fill('待处理问题')
  await page.locator('textarea').press('Enter')
  await expect(page.locator('.composer-hint')).toContainText('正在生成回复，请稍候')

  await page.getByRole('button', { name: '展开会话' }).click()
  const sessionS2 = page.locator('.session-item .session-select').filter({ hasText: 's2' }).first()
  await sessionS2.click()

  await expect(page.locator('.message.assistant .text').filter({ hasText: 'history-s2' }).first()).toBeVisible()
  await expect(page.locator('.message.assistant .text').filter({ hasText: '正在回复中…' })).toHaveCount(0)
  await expect.poll(async () =>
    page.evaluate(() => localStorage.getItem('studentActiveSession:S001')),
  ).toBe('s2')

  const pendingStorage = await page.evaluate(() => {
    const raw = localStorage.getItem('studentPendingChatJob:S001')
    if (!raw) return null
    const parsed = JSON.parse(raw) as { session_id?: string; job_id?: string }
    return {
      session_id: String(parsed.session_id || ''),
      job_id: String(parsed.job_id || ''),
    }
  })
  expect(pendingStorage).toEqual({
    session_id: 'main',
    job_id: 'student_pending_contract',
  })
})
