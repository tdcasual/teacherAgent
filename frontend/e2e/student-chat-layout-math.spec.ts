import { expect, test, type Page } from '@playwright/test'
import { setupStudentState } from './helpers/studentHarness'

const setupStudentApiMocksWithReply = async (page: Page, assistantReply: string) => {
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
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          student_id: 'S001',
          sessions: [
            {
              session_id: 'main',
              updated_at: new Date().toISOString(),
              preview: '欢迎使用学生端',
              message_count: 1,
            },
          ],
          next_cursor: null,
          total: 1,
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
          messages: [],
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
          job_id: 'student_math_job',
          status: 'done',
          reply: assistantReply,
        }),
      })
      return
    }

    if (pathname === '/chat/status' && method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: 'student_math_job',
          status: 'done',
          reply: assistantReply,
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

test.describe('student chat layout and markdown math', () => {
  test.use({ viewport: { width: 1440, height: 900 } })

  test('root app shell keeps fallback class for stable full-height layout', async ({ page }) => {
    await setupStudentState(page)
    await setupStudentApiMocksWithReply(page, '你好')
    await page.goto('/')

    const rootShell = page.locator('#root > div').first()
    await expect(rootShell).toBeVisible()
    await expect(rootShell).toHaveClass(/app/)
  })

  test('composer stays close to viewport bottom on desktop', async ({ page }) => {
    await setupStudentState(page)
    await setupStudentApiMocksWithReply(page, '你好')
    await page.goto('/')

    const composer = page.locator('.composer')
    await expect(composer).toBeVisible()

    const composerRect = await composer.boundingBox()
    const viewport = page.viewportSize()
    expect(composerRect).not.toBeNull()
    expect(viewport).not.toBeNull()
    expect(composerRect!.y + composerRect!.height).toBeGreaterThan(viewport!.height - 120)

    const overflow = await page.evaluate(() => ({
      html: window.getComputedStyle(document.documentElement).overflowY,
      body: window.getComputedStyle(document.body).overflowY,
    }))
    expect(overflow.html).toBe('hidden')
    expect(overflow.body).toBe('hidden')
  })

  test('composer remains anchored after messages become scrollable', async ({ page }) => {
    const longReply = '用于触发滚动的回复内容。'.repeat(80)

    await setupStudentState(page)
    await setupStudentApiMocksWithReply(page, longReply)
    await page.goto('/')

    const composerInput = page.locator('textarea').first()
    await expect(composerInput).toBeVisible()

    for (let i = 1; i <= 8; i += 1) {
      await composerInput.fill(`滚动稳定性验证 ${i}`)
      await composerInput.press('Enter')
      await expect.poll(async () => composerInput.isDisabled()).toBe(false)
    }

    const layout = await page.evaluate(() => {
      const messages = document.querySelector('.messages')
      const composer = document.querySelector('.composer')
      const rect = composer?.getBoundingClientRect()
      const m = messages instanceof HTMLElement ? messages : null
      return {
        hasScrollbar: Boolean(m && m.scrollHeight > m.clientHeight),
        composerBottomGap: rect ? window.innerHeight - rect.bottom : null,
        composerHeight: rect?.height ?? null,
      }
    })

    expect(layout.hasScrollbar).toBe(true)
    expect(layout.composerBottomGap).not.toBeNull()
    expect(layout.composerBottomGap!).toBeLessThanOrEqual(2)
    expect(layout.composerHeight).not.toBeNull()
    expect(layout.composerHeight!).toBeLessThan(260)
  })

  test('renders inline and block math in markdown replies', async ({ page }) => {
    const reply = [
      '行内公式：\\(a^2 + b^2 = c^2\\)',
      '',
      '块级公式：',
      '\\[\\int_0^1 x^2\\,dx = \\frac{1}{3}\\]',
    ].join('\n')

    await setupStudentState(page)
    await setupStudentApiMocksWithReply(page, reply)
    await page.goto('/')

    const composerInput = page.locator('textarea').first()
    await expect(composerInput).toBeVisible()
    await composerInput.fill('请展示公式')
    await composerInput.press('Enter')

    const assistantBubble = page.locator('.message.assistant .text.markdown').last()
    await expect(assistantBubble).toBeVisible()
    await expect(assistantBubble.locator('.katex')).toHaveCount(2)
    await expect(assistantBubble.locator('.katex-display')).toHaveCount(1)
  })
})

test.describe('student narrow layout stability', () => {
  test.use({ viewport: { width: 900, height: 1708 } })

  test('chat panel keeps primary viewport space at 900px width', async ({ page }) => {
    await setupStudentState(page)
    await setupStudentApiMocksWithReply(page, '你好')
    await page.goto('/')

    const shell = page.locator('.chat-shell')
    await expect(shell).toBeVisible()

    const box = await shell.boundingBox()
    const viewport = page.viewportSize()
    expect(box).not.toBeNull()
    expect(viewport).not.toBeNull()
    expect(box!.height).toBeGreaterThan(viewport!.height * 0.6)
  })

  test('desktop layout keeps session sidebar on the left and chat panel on the right', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 })
    await setupStudentState(page)
    await setupStudentApiMocksWithReply(page, '你好')
    await page.goto('/')

    const sidebar = page.locator('.session-sidebar')
    const chat = page.getByTestId('student-chat-panel')
    await expect(sidebar).toBeVisible()
    await expect(chat).toBeVisible()

    const sidebarRect = await sidebar.boundingBox()
    const chatRect = await chat.boundingBox()
    expect(sidebarRect).not.toBeNull()
    expect(chatRect).not.toBeNull()
    expect(sidebarRect!.x).toBeLessThan(chatRect!.x)
    expect(sidebarRect!.width).toBeLessThan(chatRect!.width)
  })

  test('wheel scrolling messages does not collapse chat panel layout', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 })
    const longReply = '用于触发滚动与布局稳定性验证的回复内容。'.repeat(120)
    await setupStudentState(page)
    await setupStudentApiMocksWithReply(page, longReply)
    await page.goto('/')

    const composerInput = page.locator('textarea').first()
    await expect(composerInput).toBeVisible()
    for (let i = 1; i <= 6; i += 1) {
      await composerInput.fill(`滚轮布局稳定性校验 ${i}`)
      await composerInput.press('Enter')
      await expect.poll(async () => composerInput.isDisabled()).toBe(false)
    }

    const chat = page.getByTestId('student-chat-panel')
    const messages = page.locator('.messages')
    await expect(chat).toBeVisible()
    await expect(messages).toBeVisible()

    const before = await chat.boundingBox()
    expect(before).not.toBeNull()

    const messagesBox = await messages.boundingBox()
    expect(messagesBox).not.toBeNull()
    await page.mouse.move(messagesBox!.x + messagesBox!.width / 2, messagesBox!.y + messagesBox!.height / 2)
    for (let i = 0; i < 12; i += 1) {
      await page.mouse.wheel(0, 220)
      await page.waitForTimeout(16)
    }
    await page.waitForTimeout(120)

    const after = await chat.boundingBox()
    expect(after).not.toBeNull()
    expect(Math.abs(after!.width - before!.width)).toBeLessThanOrEqual(2)
    expect(Math.abs(after!.height - before!.height)).toBeLessThanOrEqual(2)

    const composerBottomGap = await page.evaluate(() => {
      const composer = document.querySelector('.composer')
      const rect = composer?.getBoundingClientRect()
      return rect ? window.innerHeight - rect.bottom : null
    })
    expect(composerBottomGap).not.toBeNull()
    expect(composerBottomGap!).toBeLessThanOrEqual(2)
  })
})
