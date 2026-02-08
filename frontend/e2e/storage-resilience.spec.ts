import { expect, test, type Page } from '@playwright/test'

type ViewStatePayload = {
  title_map: Record<string, string>
  hidden_ids: string[]
  active_session_id: string
  updated_at: string
}

const setupUnifiedApiMocks = async (page: Page, options: { chatReply?: string } = {}) => {
  const now = new Date().toISOString()
  let teacherViewState: ViewStatePayload = { title_map: {}, hidden_ids: [], active_session_id: 'main', updated_at: now }
  let studentViewState: ViewStatePayload = { title_map: {}, hidden_ids: [], active_session_id: 'main', updated_at: now }

  await page.route('http://localhost:8000/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const method = request.method().toUpperCase()
    const pathname = url.pathname

    if (method === 'GET' && pathname === '/skills') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ skills: [] }) })
      return
    }

    if (method === 'GET' && pathname === '/assignment/today') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, assignment: null }) })
      return
    }

    if (method === 'GET' && pathname === '/teacher/history/sessions') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, teacher_id: 'T001', sessions: [], next_cursor: null, total: 0 }),
      })
      return
    }

    if (method === 'GET' && pathname === '/teacher/history/session') {
      const sessionId = url.searchParams.get('session_id') || 'main'
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, teacher_id: 'T001', session_id: sessionId, messages: [], next_cursor: -1 }),
      })
      return
    }

    if (pathname === '/teacher/session/view-state' && method === 'GET') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, state: teacherViewState }) })
      return
    }

    if (pathname === '/teacher/session/view-state' && method === 'PUT') {
      const body = JSON.parse(request.postData() || '{}') as { state?: Partial<ViewStatePayload> }
      teacherViewState = {
        title_map: (body?.state?.title_map as Record<string, string>) || {},
        hidden_ids: Array.isArray(body?.state?.hidden_ids) ? (body.state?.hidden_ids as string[]) : [],
        active_session_id: 'main',
        updated_at: new Date().toISOString(),
      }
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, state: teacherViewState }) })
      return
    }

    if (method === 'GET' && pathname === '/student/history/sessions') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, student_id: 'S001', sessions: [], next_cursor: null, total: 0 }),
      })
      return
    }

    if (method === 'GET' && pathname === '/student/history/session') {
      const sessionId = url.searchParams.get('session_id') || 'main'
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, student_id: 'S001', session_id: sessionId, messages: [], next_cursor: -1 }),
      })
      return
    }

    if (pathname === '/student/session/view-state' && method === 'GET') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, state: studentViewState }) })
      return
    }

    if (pathname === '/student/session/view-state' && (method === 'POST' || method === 'PUT')) {
      const body = JSON.parse(request.postData() || '{}') as { state?: Partial<ViewStatePayload> }
      studentViewState = {
        title_map: (body?.state?.title_map as Record<string, string>) || {},
        hidden_ids: Array.isArray(body?.state?.hidden_ids) ? (body.state?.hidden_ids as string[]) : [],
        active_session_id: 'main',
        updated_at: new Date().toISOString(),
      }
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, state: studentViewState }) })
      return
    }

    if (method === 'POST' && pathname === '/chat/start') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, job_id: 'job_storage_resilience', status: 'queued', lane_id: 'lane_1', lane_queue_position: 0, lane_queue_size: 1 }),
      })
      return
    }

    if (method === 'GET' && pathname === '/chat/status') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ job_id: url.searchParams.get('job_id') || 'job_storage_resilience', status: 'done', reply: options.chatReply || '已收到。' }),
      })
      return
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
  })
}

test('app does not throw when localStorage.setItem throws (quota exceeded simulation)', async ({ page }) => {
  const pageErrors: string[] = []
  page.on('pageerror', (err) => pageErrors.push(String(err)))

  await page.addInitScript(() => {
    const original = localStorage.setItem.bind(localStorage)
    localStorage.setItem = (...args: any[]) => {
      // allow a small number of writes during bootstrap if needed, then simulate quota exceeded forever
      ;(window as any).__lsWrites = ((window as any).__lsWrites || 0) + 1
      if ((window as any).__lsWrites <= 8) return original(...args)
      throw new DOMException('QuotaExceededError', 'QuotaExceededError')
    }
  })

  await setupUnifiedApiMocks(page)
  await page.goto('/')

  await expect(page.getByRole('button', { name: '发送' })).toBeVisible()
  await page.waitForTimeout(600)

  expect(pageErrors.join('\n')).not.toMatch(/QuotaExceededError/i)
})
