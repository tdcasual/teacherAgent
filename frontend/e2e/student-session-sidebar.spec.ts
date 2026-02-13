import { expect, test } from '@playwright/test'
import { openStudentApp, setupStudentState } from './helpers/studentHarness'

test('mobile session menu supports keyboard navigation and escape focus return', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
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
        s2: [{ ts: new Date().toISOString(), role: 'assistant', content: 's2' }],
      },
    },
  })

  let trigger = page.locator('.session-menu-trigger').first()
  if ((await trigger.count()) === 0) {
    await page.getByRole('button', { name: '新会话' }).click()
    trigger = page.locator('.session-menu-trigger').first()
    await expect(trigger).toBeVisible()
  }
  await trigger.focus()
  await expect(trigger).toBeFocused()

  await page.keyboard.press('ArrowDown')
  const menu = page.locator('.session-menu').first()
  await expect(menu).toBeVisible()
  const items = menu.locator('.session-menu-item')
  await expect(items).toHaveCount(2)
  await expect(items.nth(0)).toBeFocused()

  await page.keyboard.press('ArrowDown')
  await expect(items.nth(1)).toBeFocused()

  await page.keyboard.press('Home')
  await expect(items.nth(0)).toBeFocused()

  await page.keyboard.press('End')
  await expect(items.nth(1)).toBeFocused()

  await page.keyboard.press('Escape')
  await expect(menu).toBeHidden()
  await expect(trigger).toBeFocused()
})

test('rename dialog escape restores focus to session menu trigger', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
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
        s2: [{ ts: new Date().toISOString(), role: 'assistant', content: 's2' }],
      },
    },
  })

  let trigger = page.locator('.session-menu-trigger').first()
  if ((await trigger.count()) === 0) {
    await page.getByRole('button', { name: '新会话' }).click()
    trigger = page.locator('.session-menu-trigger').first()
  }
  await trigger.click()
  await page.getByRole('menuitem', { name: '重命名', exact: true }).click()

  const dialog = page.getByRole('dialog', { name: '重命名会话' })
  await expect(dialog).toBeVisible()
  await expect(dialog.getByLabel('会话名称')).toBeFocused()

  await page.keyboard.press('Escape')
  await expect(dialog).toBeHidden()
  await expect(trigger).toBeFocused()
})

test('sidebar toggle exposes aria contract and verification inputs are label-associated', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
  await openStudentApp(page, {
    stateOverrides: {
      verifiedStudent: null,
      studentSidebarOpen: 'true',
    },
    apiMocks: {
      historyBySession: {
        main: [{ ts: new Date().toISOString(), role: 'assistant', content: 'main' }],
      },
    },
  })

  const collapseToggle = page.getByRole('button', { name: '收起会话' })
  await expect(collapseToggle).toHaveAttribute('aria-controls', 'student-session-sidebar')
  await expect(collapseToggle).toHaveAttribute('aria-expanded', 'true')

  await collapseToggle.click()
  const expandToggle = page.getByRole('button', { name: '展开会话' })
  await expect(expandToggle).toHaveAttribute('aria-controls', 'student-session-sidebar')
  await expect(expandToggle).toHaveAttribute('aria-expanded', 'false')

  await expect(page.getByLabel('姓名')).toBeVisible()
  await expect(page.getByLabel('班级（重名时必填）')).toBeVisible()
})

test('restoring pending job keeps only one pending status bubble', async ({ page }) => {
  await setupStudentState(page, {
    stateOverrides: {
      verifiedStudent: JSON.stringify({
        student_id: 'S001',
        student_name: '测试学生',
        class_name: '高二1班',
      }),
    },
  })
  await page.addInitScript(() => {
    const sid = 'S001'
    const sessionId = 'general_pending_001'
    localStorage.setItem(
      `studentPendingChatJob:${sid}`,
      JSON.stringify({
        job_id: 'student_restore_pending',
        request_id: 'req_student_restore_pending',
        placeholder_id: 'asst_student_restore_pending_1',
        user_text: '描述 武熙语 学生',
        session_id: sessionId,
        created_at: Date.now(),
      }),
    )
    localStorage.setItem(
      `studentSessionViewState:${sid}`,
      JSON.stringify({
        title_map: {},
        hidden_ids: [],
        active_session_id: sessionId,
        updated_at: new Date().toISOString(),
      }),
    )
    localStorage.setItem(`studentActiveSession:${sid}`, sessionId)
  })

  let chatStatusCalls = 0

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
          sessions: [{ session_id: 'general_pending_001', updated_at: new Date().toISOString(), message_count: 0, preview: '' }],
          next_cursor: null,
          total: 1,
        }),
      })
      return
    }

    if (method === 'GET' && path === '/student/history/session') {
      await page.waitForTimeout(300)
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          student_id: 'S001',
          session_id: 'general_pending_001',
          messages: [],
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
              active_session_id: 'general_pending_001',
              updated_at: new Date().toISOString(),
            },
          }),
        })
        return
      }
      if (method === 'PUT') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ok: true,
            student_id: 'S001',
            state: {
              title_map: {},
              hidden_ids: [],
              active_session_id: 'general_pending_001',
              updated_at: new Date().toISOString(),
            },
          }),
        })
        return
      }
    }

    if (method === 'GET' && path === '/chat/status') {
      chatStatusCalls += 1
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: 'student_restore_pending',
          status: 'processing',
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

  const pendingStatusCount = async () =>
    page.evaluate(() => {
      const targets = new Set(['正在生成…', '正在回复中…', '正在恢复上一条回复…'])
      return Array.from(document.querySelectorAll('.message.assistant .text')).filter((el) =>
        targets.has(String((el as HTMLElement).innerText || '').trim()),
      ).length
    })

  const hasPendingStorage = async () =>
    page.evaluate(() => Boolean(localStorage.getItem('studentPendingChatJob:S001')))

  await page.goto('/')
  await expect(page.getByRole('button', { name: '发送' })).toBeVisible()
  await expect(page.locator('.message.assistant .text').filter({ hasText: '正在回复中' }).first()).toBeVisible()

  let maxPendingStatusCount = 0
  for (let i = 0; i < 16; i += 1) {
    const current = await pendingStatusCount()
    maxPendingStatusCount = Math.max(maxPendingStatusCount, current)
    await page.waitForTimeout(120)
  }

  expect(chatStatusCalls).toBeGreaterThan(0)
  expect(await hasPendingStorage()).toBe(true)
  expect(maxPendingStatusCount).toBeGreaterThan(0)
  expect(maxPendingStatusCount).toBeLessThanOrEqual(1)
})

test('switching sessions while pending loads target session history', async ({ page }) => {
  await setupStudentState(page, {
    stateOverrides: {
      studentSidebarOpen: 'false',
      verifiedStudent: JSON.stringify({
        student_id: 'S001',
        student_name: '测试学生',
        class_name: '高二1班',
      }),
    },
  })

  let startSessionId = ''
  let historySessionBySession: Record<string, number> = {}

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
      historySessionBySession[sessionId] = (historySessionBySession[sessionId] || 0) + 1
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
      const body = JSON.parse(request.postData() || '{}') as { session_id?: string }
      startSessionId = String(body.session_id || '')
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, job_id: 'student_pending_switch', status: 'queued' }),
      })
      return
    }

    if (method === 'GET' && path === '/chat/status') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ job_id: 'student_pending_switch', status: 'processing' }),
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

  await page.locator('textarea').fill('待处理问题')
  await page.locator('textarea').press('Enter')
  await expect(page.locator('.message.user .text').filter({ hasText: '待处理问题' }).first()).toBeVisible()
  await expect.poll(() => startSessionId).toBe('main')

  const sessionS2 = page.locator('.session-item .session-select').filter({ hasText: 's2' }).first()
  await expect(sessionS2).toBeVisible()
  await sessionS2.focus()
  await page.keyboard.press('Enter')

  await expect.poll(() => historySessionBySession.s2 || 0).toBeGreaterThan(0)

  await expect(page.locator('.message.assistant .text').filter({ hasText: 'history-s2' }).first()).toBeVisible()

  await expect
    .poll(async () => {
      const chatDiag = await page.evaluate(() => {
        const activeIds = Array.from(document.querySelectorAll('.session-item.active .session-id')).map((el) =>
          String((el as HTMLElement).innerText || '').trim(),
        )
        const userTexts = Array.from(document.querySelectorAll('.message.user .text')).map((el) =>
          String((el as HTMLElement).innerText || '').trim(),
        )
        const assistantTexts = Array.from(document.querySelectorAll('.message.assistant .text')).map((el) =>
          String((el as HTMLElement).innerText || '').trim(),
        )
        return {
          activeIds,
          hasHistoryS2: assistantTexts.some((text) => text.includes('history-s2')),
          hasHistoryMain: assistantTexts.some((text) => text.includes('history-main')),
          hasPendingRecover: assistantTexts.some((text) => text.includes('正在恢复上一条回复')),
          hasPendingUserText: userTexts.some((text) => text.includes('待处理问题')),
        }
      })
      return chatDiag
    })
    .toEqual({
      activeIds: ['s2'],
      hasHistoryS2: true,
      hasHistoryMain: false,
      hasPendingRecover: false,
      hasPendingUserText: false,
    })
})

test('sending one pending request keeps only one user bubble', async ({ page }) => {
  await setupStudentState(page, {
    stateOverrides: {
      studentSidebarOpen: 'false',
      verifiedStudent: JSON.stringify({
        student_id: 'S001',
        student_name: '测试学生',
        class_name: '高二1班',
      }),
    },
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
          sessions: [{ session_id: 'main', updated_at: new Date().toISOString(), message_count: 1, preview: 'history-main' }],
          next_cursor: null,
          total: 1,
        }),
      })
      return
    }

    if (method === 'GET' && path === '/student/history/session') {
      const sessionId = url.searchParams.get('session_id') || 'main'
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          student_id: 'S001',
          session_id: sessionId,
          messages: [{ ts: new Date().toISOString(), role: 'assistant', content: 'history-main' }],
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
        body: JSON.stringify({ ok: true, job_id: 'student_pending_dup_user', status: 'queued' }),
      })
      return
    }

    if (method === 'GET' && path === '/chat/status') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ job_id: 'student_pending_dup_user', status: 'processing' }),
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

  const userText = '待处理问题-去重'
  await page.locator('textarea').fill(userText)
  await page.locator('textarea').press('Enter')

  await expect(page.locator('.composer-hint')).toContainText('正在生成回复，请稍候')

  const countUserBubble = async () =>
    page.evaluate((targetText) => {
      return Array.from(document.querySelectorAll('.message.user .text')).filter(
        (el) => String((el as HTMLElement).innerText || '').trim() === targetText,
      ).length
    }, userText)

  let maxCount = 0
  for (let i = 0; i < 18; i += 1) {
    const current = await countUserBubble()
    maxCount = Math.max(maxCount, current)
    await page.waitForTimeout(100)
  }

  expect(maxCount).toBeGreaterThan(0)
  expect(maxCount).toBe(1)
})

test('malformed local view-state should recover remote active session', async ({ page }) => {
  await setupStudentState(page, {
    stateOverrides: {
      studentSidebarOpen: 'false',
      verifiedStudent: JSON.stringify({
        student_id: 'S001',
        student_name: '测试学生',
        class_name: '高二1班',
      }),
      'studentSessionViewState:S001': '{broken-json',
      'studentActiveSession:S001': null,
    },
  })

  const historyCalls: string[] = []

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
            { session_id: 'legacy_session', updated_at: new Date().toISOString(), message_count: 1, preview: 'legacy-preview' },
            { session_id: 's2', updated_at: new Date().toISOString(), message_count: 1, preview: 'history-s2' },
          ],
          next_cursor: null,
          total: 2,
        }),
      })
      return
    }

    if (method === 'GET' && path === '/student/history/session') {
      const sessionId = String(url.searchParams.get('session_id') || '')
      historyCalls.push(sessionId)
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          student_id: 'S001',
          session_id: sessionId,
          messages: [
            {
              ts: new Date().toISOString(),
              role: 'assistant',
              content: sessionId === 'legacy_session' ? 'legacy-history' : `unexpected-history-${sessionId}`,
            },
          ],
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
              active_session_id: 'legacy_session',
              updated_at: '2026-01-01T08:00:00.000Z',
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

    if (method === 'GET' && path === '/chat/status') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ job_id: 'noop', status: 'done', reply: 'ok' }),
      })
      return
    }

    if (method === 'POST' && path === '/chat/start') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, job_id: 'noop', status: 'queued' }),
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

  await expect.poll(() => historyCalls.filter((sid) => sid === 'legacy_session').length).toBeGreaterThan(0)
  await expect(page.locator('.message.assistant .text').filter({ hasText: 'legacy-history' }).first()).toBeVisible()

  const activeSessionId = await page.evaluate(() => {
    const active = document.querySelector('.session-item.active .session-id')
    return String((active as HTMLElement | null)?.innerText || '').trim()
  })

  expect(activeSessionId).toBe('legacy_session')
})

test('switching history sessions keeps chat shell anchored and composer at bottom', async ({ page }) => {
  await page.setViewportSize({ width: 1292, height: 1169 })

  const longHistory = Array.from({ length: 36 }, (_, i) => ({
    ts: new Date(Date.now() - (36 - i) * 60_000).toISOString(),
    role: i % 2 === 0 ? 'assistant' : 'user',
    content: `MAIN-LONG-${i} ` + '内容'.repeat(48),
  }))
  const shortHistory = [
    { ts: new Date().toISOString(), role: 'assistant', content: 'S2-SHORT-0' },
  ]

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
        main: longHistory,
        s2: shortHistory,
      },
    },
  })

  const readLayout = async () =>
    page.evaluate(() => {
      const shell = document.querySelector('[data-testid="student-chat-panel"]') as HTMLElement | null
      const messages = document.querySelector('.messages') as HTMLElement | null
      const composer = document.querySelector('.composer') as HTMLElement | null
      if (!shell || !messages || !composer) return null
      const shellRect = shell.getBoundingClientRect()
      const messagesRect = messages.getBoundingClientRect()
      const composerRect = composer.getBoundingClientRect()
      return {
        shellScrollTop: shell.scrollTop,
        messagesTopOffset: messagesRect.top - shellRect.top,
        composerBottomGap: window.innerHeight - composerRect.bottom,
      }
    })

  const expectAnchored = async () => {
    await expect.poll(async () => (await readLayout())?.shellScrollTop ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(1)
    await expect.poll(async () => Math.abs((await readLayout())?.messagesTopOffset ?? Number.POSITIVE_INFINITY)).toBeLessThanOrEqual(1.5)
    await expect.poll(async () => (await readLayout())?.composerBottomGap ?? Number.POSITIVE_INFINITY).toBeLessThanOrEqual(2)
  }

  await expect(page.locator('.message .text').filter({ hasText: 'MAIN-LONG-0' }).first()).toBeVisible()
  await expectAnchored()

  const s2Session = page.locator('.session-item', { hasText: 's2' }).locator('.session-select').first()
  const mainSession = page.locator('.session-item', { hasText: 'main' }).locator('.session-select').first()

  await s2Session.click()
  await expect(page.locator('.message .text').filter({ hasText: 'S2-SHORT-0' }).first()).toBeVisible()
  await expectAnchored()

  await mainSession.click()
  await expect(page.locator('.message .text').filter({ hasText: 'MAIN-LONG-0' }).first()).toBeVisible()
  await expectAnchored()
})
