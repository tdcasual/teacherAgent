import { expect, test, type Page } from '@playwright/test'

type ViewStatePayload = {
  title_map: Record<string, string>
  hidden_ids: string[]
  active_session_id: string
  updated_at: string
}

const setupUnifiedApiMocks = async (page: Page, options: { assistantReply: string }) => {
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
        body: JSON.stringify({ ok: true, job_id: 'job_sanitize', status: 'queued', lane_id: 'lane_1', lane_queue_position: 0, lane_queue_size: 1 }),
      })
      return
    }

    if (method === 'GET' && pathname === '/chat/status') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ job_id: url.searchParams.get('job_id') || 'job_sanitize', status: 'done', reply: options.assistantReply }),
      })
      return
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
  })
}

const assertNoXssRedFlags = async (page: Page) => {
  const bubble = page.locator('.message.assistant .text.markdown').last()
  await expect(bubble).toBeVisible()
  await expect(bubble.locator('script')).toHaveCount(0)
  const html = await bubble.evaluate((el) => el.innerHTML)
  expect(html).not.toMatch(/<script\b/i)
  expect(html).not.toMatch(/\son\w+=/i)
  expect(html).not.toMatch(/\bhref\s*=\s*["']\s*javascript:/i)
  expect(html).not.toMatch(/\bhref\s*=\s*["']\s*data:/i)
  expect(html).not.toMatch(/\bsrc\s*=\s*["']\s*javascript:/i)
  expect(html).not.toMatch(/\bsrc\s*=\s*["']\s*data:/i)
}

test('assistant markdown sanitization blocks common XSS payloads', async ({ page }) => {
  let dialogSeen: string | null = null
  page.on('dialog', (dialog) => {
    dialogSeen = dialog.message()
    void dialog.dismiss()
  })

  const payload = [
    'XSS',
    '[x](javascript:alert(1))',
    '[x](data:text/html,<script>alert(1)</script>)',
    '![x](javascript:alert(1))',
    '<img src=x onerror=alert(1)>',
    '<script>alert(1)</script>',
    '<svg><script>alert(1)</script></svg>',
  ].join('\n')

  await setupUnifiedApiMocks(page, { assistantReply: payload })
  await page.addInitScript(() => {
    try {
      window.localStorage.setItem(
        'verifiedStudent',
        JSON.stringify({ student_id: 'S001', student_name: '测试学生', class_name: '测试班级' }),
      )
    } catch {
      // Ignore storage errors: this test focuses on XSS sanitization, not persistence.
    }
  })
  await page.goto('/')

  const composer = page.locator('textarea').first()
  await expect(composer).toBeVisible()
  await composer.fill('trigger')
  await composer.press('Enter')

  await assertNoXssRedFlags(page)
  expect(dialogSeen).toBeNull()
})
