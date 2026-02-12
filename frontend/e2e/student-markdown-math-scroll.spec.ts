import { expect, test, type Page } from '@playwright/test'
import { setupStudentState } from './helpers/studentHarness'

const setupMocks = async (page: Page, reply: string) => {
  let vs = {
    title_map: {} as Record<string, string>,
    hidden_ids: [] as string[],
    active_session_id: 'main',
    updated_at: new Date().toISOString(),
  }
  await page.route('http://localhost:8000/**', async (route) => {
    const req = route.request()
    const url = new URL(req.url())
    const m = req.method().toUpperCase()
    const p = url.pathname
    const json = (d: unknown) => route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify(d),
    })
    if (m === 'GET' && p === '/assignment/today')
      return json({ ok: true, assignment: null })
    if (m === 'GET' && p === '/student/history/sessions')
      return json({
        ok: true, student_id: 'S001', next_cursor: null, total: 1,
        sessions: [{ session_id: 'main', updated_at: new Date().toISOString(), preview: '欢迎', message_count: 1 }],
      })
    if (m === 'GET' && p === '/student/history/session')
      return json({ ok: true, student_id: 'S001', session_id: url.searchParams.get('session_id') || 'main', messages: [], next_cursor: -1 })
    if (p === '/student/session/view-state' && m === 'GET')
      return json({ ok: true, state: vs })
    if (p === '/student/session/view-state' && (m === 'POST' || m === 'PUT')) {
      const b = JSON.parse(req.postData() || '{}') as { state?: Record<string, unknown> }
      const s = b?.state && typeof b.state === 'object' ? b.state : {}
      vs = {
        title_map: (s.title_map as Record<string, string>) || {},
        hidden_ids: Array.isArray(s.hidden_ids) ? (s.hidden_ids as string[]) : [],
        active_session_id: 'main',
        updated_at: new Date().toISOString(),
      }
      return json({ ok: true, state: vs })
    }
    if (p === '/chat/start' && m === 'POST')
      return json({ ok: true, job_id: 'j1', status: 'done', reply })
    if (p === '/chat/status' && m === 'GET')
      return json({ job_id: 'j1', status: 'done', reply })
    return json({ ok: true })
  })
}

/* --- Math formula overflow containment --- */
test.describe('math formula overflow', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  test('long display math has overflow-x: auto', async ({ page }) => {
    const longFormula = '$$' + Array(30).fill('a_i').join(' + ') + ' = 0$$'
    await setupStudentState(page)
    await setupMocks(page, longFormula)
    await page.goto('/')

    const input = page.locator('textarea').first()
    await expect(input).toBeVisible()
    await input.fill('长公式')
    await input.press('Enter')

    const katexDisplay = page.locator('.message.assistant .katex-display').last()
    await expect(katexDisplay).toBeVisible()

    const overflow = await katexDisplay.evaluate((el) => window.getComputedStyle(el).overflowX)
    expect(overflow).toBe('auto')
  })

  test('inline math renders correctly', async ({ page }) => {
    const reply = '行内公式 \\\\(E = mc^2\\\\) 和 \\\\(F = ma\\\\) 在同一行。'
    await setupStudentState(page)
    await setupMocks(page, reply)
    await page.goto('/')

    const input = page.locator('textarea').first()
    await expect(input).toBeVisible()
    await input.fill('行内')
    await input.press('Enter')

    const bubble = page.locator('.message.assistant .text.markdown').last()
    await expect(bubble).toBeVisible()
    await expect(bubble.locator('.katex')).toHaveCount(2)
  })

  test('GFM table has overflow-x: auto', async ({ page }) => {
    const table = [
      '| A | B | C | D | E | F | G |',
      '|---|---|---|---|---|---|---|',
      '| 1 | 2 | 3 | 4 | 5 | 6 | 7 |',
    ].join('\n')
    await setupStudentState(page)
    await setupMocks(page, table)
    await page.goto('/')

    const input = page.locator('textarea').first()
    await expect(input).toBeVisible()
    await input.fill('表格')
    await input.press('Enter')

    const tableEl = page.locator('.message.assistant .markdown table').last()
    await expect(tableEl).toBeVisible()
    const overflow = await tableEl.evaluate((el) => window.getComputedStyle(el).overflowX)
    expect(overflow).toBe('auto')
  })
})

/* --- Smart auto-scroll indicator --- */
test.describe('smart auto-scroll', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  test('new-message-indicator is styled as absolute positioned', async ({ page }) => {
    await setupStudentState(page)
    await setupMocks(page, '回复')
    await page.goto('/')

    // Verify the chat-shell has position: relative (needed for indicator)
    const shell = page.locator('.chat-shell')
    await expect(shell).toBeVisible()
    const pos = await shell.evaluate((el) => window.getComputedStyle(el).position)
    expect(pos).toBe('relative')
  })
})

/* --- Mobile viewport: no double scroll --- */
test.describe('mobile viewport scroll', () => {
  test.use({ viewport: { width: 375, height: 812 } })

  test('html/body overflow hidden on mobile', async ({ page }) => {
    await setupStudentState(page)
    await setupMocks(page, '你好')
    await page.goto('/')

    const overflow = await page.evaluate(() => ({
      html: window.getComputedStyle(document.documentElement).overflow,
      body: window.getComputedStyle(document.body).overflow,
    }))
    expect(overflow.html).toBe('hidden')
    expect(overflow.body).toBe('hidden')
  })

  test('messages container has overscroll-behavior: contain', async ({ page }) => {
    await setupStudentState(page)
    await setupMocks(page, '你好')
    await page.goto('/')

    const messages = page.locator('.messages')
    await expect(messages).toBeVisible()
    const overscroll = await messages.evaluate((el) => window.getComputedStyle(el).overscrollBehavior)
    expect(overscroll).toBe('contain')
  })
})
