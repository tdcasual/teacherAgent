import { expect, test } from '@playwright/test'
import { setupStudentState } from './helpers/studentHarness'

test('temporary network failures during pending can recover without duplicate user bubbles', async ({ page }) => {
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

  let statusCalls = 0
  let allowDoneStatus = false

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
        body: JSON.stringify({ ok: true, job_id: 'student_reconnect_job', status: 'queued' }),
      })
      return
    }

    if (method === 'GET' && path === '/chat/status') {
      statusCalls += 1
      if (statusCalls < 3) {
        await route.fulfill({
          status: 500,
          contentType: 'text/plain',
          body: 'temporary network error',
        })
        return
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ job_id: 'student_reconnect_job', status: 'done', reply: '重连恢复成功' }),
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

  const userText = '断网重连测试'
  await page.locator('textarea').fill(userText)
  await page.locator('textarea').press('Enter')

  await expect(page.locator('.composer-hint')).toContainText('正在生成回复，请稍候')
  await expect.poll(() => statusCalls).toBeGreaterThanOrEqual(3)

  await expect(page.locator('.message.assistant .text').filter({ hasText: '重连恢复成功' }).first()).toBeVisible()

  const chatDiag = await page.evaluate((targetText) => {
    const userCount = Array.from(document.querySelectorAll('.message.user .text')).filter(
      (el) => String((el as HTMLElement).innerText || '').trim() === targetText,
    ).length
    const assistantTexts = Array.from(document.querySelectorAll('.message.assistant .text')).map((el) =>
      String((el as HTMLElement).innerText || '').trim(),
    )
    const pendingStorage = Boolean(localStorage.getItem('studentPendingChatJob:S001'))
    return {
      userCount,
      hasPendingStatus: assistantTexts.some((text) => text.includes('正在恢复上一条回复') || text.includes('网络波动，正在重试')),
      pendingStorage,
    }
  }, userText)

  expect(chatDiag.userCount).toBe(1)
  expect(chatDiag.hasPendingStatus).toBe(false)
  expect(chatDiag.pendingStorage).toBe(false)
})

test('pending state syncs across already-open tabs', async ({ page }) => {
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

  const context = page.context()
  let startCalls = 0

  await context.route('http://localhost:8000/**', async (route) => {
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
      startCalls += 1
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, job_id: 'student_multitab_pending', status: 'queued' }),
      })
      return
    }

    if (method === 'GET' && path === '/chat/status') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ job_id: 'student_multitab_pending', status: 'processing' }),
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
  const pageB = await context.newPage()
  await pageB.goto('/')

  await page.locator('textarea').fill('第一页发起pending')
  await page.locator('textarea').press('Enter')

  await expect.poll(() => startCalls).toBe(1)
  await expect(page.locator('.composer-hint')).toContainText('正在生成回复，请稍候')

  await expect.poll(async () => pageB.locator('textarea').isDisabled()).toBe(true)
  await expect(pageB.locator('.composer-hint')).toContainText('正在生成回复，请稍候')

  await pageB.waitForTimeout(260)
  expect(startCalls).toBe(1)

  await pageB.close()
})

test('external localStorage clear in another tab forces re-verification', async ({ page }) => {
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

  const context = page.context()

  await context.route('http://localhost:8000/**', async (route) => {
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
        body: JSON.stringify({ ok: true, job_id: 'noop', status: 'queued' }),
      })
      return
    }

    if (method === 'GET' && path === '/chat/status') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ job_id: 'noop', status: 'done', reply: 'ok' }),
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
  await expect(page.locator('.composer-hint')).toContainText('Enter 发送')

  const pageB = await context.newPage()
  await pageB.goto('/')
  await pageB.evaluate(() => {
    localStorage.clear()
  })

  await expect(page.locator('.composer-hint')).toContainText('请先完成身份验证')
  await expect.poll(async () => page.locator('textarea').isDisabled()).toBe(true)

  await pageB.close()
})

test('near-simultaneous sends across tabs should not start duplicate pending jobs', async ({ page }) => {
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

  const context = page.context()
  const startBodies: Array<{ session_id?: string; request_id?: string }> = []

  await context.route('http://localhost:8000/**', async (route) => {
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
      const body = JSON.parse(request.postData() || '{}')
      startBodies.push({
        session_id: body.session_id,
        request_id: body.request_id,
      })
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, job_id: `student_race_${startBodies.length}`, status: 'queued' }),
      })
      return
    }

    if (method === 'GET' && path === '/chat/status') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ job_id: 'student_race_1', status: 'processing' }),
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
  const pageB = await context.newPage()
  await pageB.goto('/')

  await page.locator('textarea').fill('A页并发发送')
  await pageB.locator('textarea').fill('B页并发发送')

  await Promise.all([page.locator('textarea').press('Enter'), pageB.locator('textarea').press('Enter')])

  await expect.poll(() => startBodies.length).toBeGreaterThan(0)

  expect(startBodies.length).toBe(1)
  const pendingPayloadA = await page.evaluate(() => localStorage.getItem('studentPendingChatJob:S001'))
  const pendingPayloadB = await pageB.evaluate(() => localStorage.getItem('studentPendingChatJob:S001'))
  expect(Boolean(pendingPayloadA)).toBe(true)
  expect(Boolean(pendingPayloadB)).toBe(true)

  await pageB.close()
})

test('near-simultaneous cross-tab sends stay single-shot even without Web Locks API', async ({ page }) => {
  const context = page.context()
  await context.addInitScript(() => {
    try {
      Object.defineProperty(window.navigator, 'locks', {
        configurable: true,
        value: undefined,
      })
    } catch {
      // ignore
    }
  })

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

  const startBodies: Array<{ session_id?: string; request_id?: string }> = []

  await context.route('http://localhost:8000/**', async (route) => {
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
      const body = JSON.parse(request.postData() || '{}')
      startBodies.push({ session_id: body.session_id, request_id: body.request_id })
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, job_id: `student_noweblock_${startBodies.length}`, status: 'queued' }),
      })
      return
    }

    if (method === 'GET' && path === '/chat/status') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ job_id: 'student_noweblock_1', status: 'processing' }),
      })
      return
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
  })

  await page.goto('/')
  const pageB = await context.newPage()
  await pageB.goto('/')

  await page.locator('textarea').fill('A页无锁并发发送')
  await pageB.locator('textarea').fill('B页无锁并发发送')

  await Promise.all([page.locator('textarea').press('Enter'), pageB.locator('textarea').press('Enter')])

  await expect.poll(() => startBodies.length).toBeGreaterThan(0)
  expect(startBodies.length).toBe(1)

  await pageB.close()
})

test('pending completion reply survives hard reload and laggy history during session switches', async ({ page }) => {
  await setupStudentState(page, {
    clearLocalStorage: false,
    stateOverrides: {
      verifiedStudent: JSON.stringify({
        student_id: 'S001',
        student_name: '测试学生',
        class_name: '高二1班',
      }),
    },
  })

  const pendingUserText = '刷新恢复压测'
  const resolvedReply = '延迟写库回复'
  const historyCallsBySession: Record<string, number> = {}
  let statusCalls = 0
  let allowDoneStatus = false

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
          sessions: [
            { session_id: 'main', updated_at: new Date().toISOString(), message_count: 1, preview: 'history-main-old' },
            { session_id: 's2', updated_at: new Date().toISOString(), message_count: 1, preview: 'history-s2' },
          ],
          next_cursor: null,
          total: 2,
        }),
      })
      return
    }

    if (method === 'GET' && path === '/student/history/session') {
      const sessionId = String(url.searchParams.get('session_id') || 'main')
      historyCallsBySession[sessionId] = (historyCallsBySession[sessionId] || 0) + 1

      if (sessionId === 's2') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ok: true,
            student_id: 'S001',
            session_id: 's2',
            messages: [{ ts: new Date().toISOString(), role: 'assistant', content: 'history-s2' }],
            next_cursor: -1,
          }),
        })
        return
      }

      const includeResolved = (historyCallsBySession.main || 0) >= 3
      const mainMessages = includeResolved
        ? [
            { ts: new Date().toISOString(), role: 'assistant', content: 'history-main-old' },
            { ts: new Date().toISOString(), role: 'user', content: pendingUserText },
            { ts: new Date().toISOString(), role: 'assistant', content: resolvedReply },
          ]
        : [{ ts: new Date().toISOString(), role: 'assistant', content: 'history-main-old' }]

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          student_id: 'S001',
          session_id: 'main',
          messages: mainMessages,
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
        body: JSON.stringify({ ok: true, job_id: 'student_reload_pending', status: 'queued' }),
      })
      return
    }

    if (method === 'GET' && path === '/chat/status') {
      statusCalls += 1
      const done = allowDoneStatus && statusCalls >= 5
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(
          done
            ? { job_id: 'student_reload_pending', status: 'done', reply: resolvedReply }
            : { job_id: 'student_reload_pending', status: 'processing' },
        ),
      })
      return
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
  })

  await page.goto('/')
  await expect(page.locator('.message.assistant .text').filter({ hasText: 'history-main-old' }).first()).toBeVisible()

  await page.locator('textarea').fill(pendingUserText)
  await page.locator('textarea').press('Enter')

  await expect.poll(async () =>
    page.evaluate(() => Boolean(localStorage.getItem('studentPendingChatJob:S001'))),
  ).toBe(true)

  await page.reload()
  await expect(page.locator('.composer-hint')).toContainText('正在生成回复，请稍候')

  allowDoneStatus = true
  await expect.poll(() => statusCalls).toBeGreaterThanOrEqual(5)
  await expect(page.locator('.message.assistant .text').filter({ hasText: resolvedReply }).first()).toBeVisible()

  const openSidebarIfNeeded = async () => {
    const expandSidebarButton = page.getByRole('button', { name: '展开会话' })
    if (await expandSidebarButton.isVisible()) {
      await expandSidebarButton.click()
    }
  }

  await openSidebarIfNeeded()
  const sessionS2 = page.locator('.session-item .session-select').filter({ hasText: 's2' }).first()
  await sessionS2.click()
  await expect(page.locator('.message.assistant .text').filter({ hasText: 'history-s2' }).first()).toBeVisible()

  await openSidebarIfNeeded()
  const sessionMain = page.locator('.session-item .session-select').filter({ hasText: 'main' }).first()
  await sessionMain.click()

  await expect.poll(() => historyCallsBySession.main || 0).toBeGreaterThanOrEqual(2)
  await expect(page.locator('.message.assistant .text').filter({ hasText: resolvedReply }).first()).toBeVisible()
})


test('multiple recent completions survive reload before history catches up', async ({ page }) => {
  await setupStudentState(page, {
    clearLocalStorage: false,
    stateOverrides: {
      verifiedStudent: JSON.stringify({
        student_id: 'S001',
        student_name: '测试学生',
        class_name: '高二1班',
      }),
    },
  })

  const firstQuestion = '第一问'
  const firstReply = '第一问回复'
  const secondQuestion = '第二问'
  const secondReply = '第二问回复'
  let startCount = 0

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
          sessions: [{ session_id: 'main', updated_at: new Date().toISOString(), message_count: 1, preview: 'history-main-old' }],
          next_cursor: null,
          total: 1,
        }),
      })
      return
    }

    if (method === 'GET' && path === '/student/history/session') {
      const sessionId = String(url.searchParams.get('session_id') || 'main')
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          student_id: 'S001',
          session_id: sessionId,
          messages: [{ ts: new Date().toISOString(), role: 'assistant', content: 'history-main-old' }],
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
      startCount += 1
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, job_id: `student_multi_done_${startCount}`, status: 'queued' }),
      })
      return
    }

    if (method === 'GET' && path === '/chat/status') {
      const jobId = String(url.searchParams.get('job_id') || '')
      const reply = jobId === 'student_multi_done_1' ? firstReply : secondReply
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ job_id: jobId || 'student_multi_done_2', status: 'done', reply }),
      })
      return
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
  })

  await page.goto('/')
  await expect(page.locator('.message.assistant .text').filter({ hasText: 'history-main-old' }).first()).toBeVisible()

  await page.locator('textarea').fill(firstQuestion)
  await page.locator('textarea').press('Enter')
  await expect(page.locator('.message.assistant .text').filter({ hasText: firstReply }).first()).toBeVisible()

  await page.locator('textarea').fill(secondQuestion)
  await page.locator('textarea').press('Enter')
  await expect(page.locator('.message.assistant .text').filter({ hasText: secondReply }).first()).toBeVisible()

  await page.reload()

  await expect(page.locator('.message.assistant .text').filter({ hasText: firstReply }).first()).toBeVisible()
  await expect(page.locator('.message.assistant .text').filter({ hasText: secondReply }).first()).toBeVisible()
})


test('duplicate same-content completions should survive reload before history catches up', async ({ page }) => {
  await setupStudentState(page, {
    clearLocalStorage: false,
    stateOverrides: {
      verifiedStudent: JSON.stringify({
        student_id: 'S001',
        student_name: '测试学生',
        class_name: '高二1班',
      }),
    },
  })

  const repeatedQuestion = '重复提问'
  const repeatedReply = '重复回复'
  let startCount = 0

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
          sessions: [{ session_id: 'main', updated_at: new Date().toISOString(), message_count: 1, preview: 'history-main-old' }],
          next_cursor: null,
          total: 1,
        }),
      })
      return
    }

    if (method === 'GET' && path === '/student/history/session') {
      const sessionId = String(url.searchParams.get('session_id') || 'main')
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          student_id: 'S001',
          session_id: sessionId,
          messages: [{ ts: new Date().toISOString(), role: 'assistant', content: 'history-main-old' }],
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
      startCount += 1
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ok: true, job_id: `student_duplicate_done_${startCount}`, status: 'queued' }),
      })
      return
    }

    if (method === 'GET' && path === '/chat/status') {
      const jobId = String(url.searchParams.get('job_id') || '')
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ job_id: jobId || 'student_duplicate_done_1', status: 'done', reply: repeatedReply }),
      })
      return
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
  })

  await page.goto('/')
  await expect(page.locator('.message.assistant .text').filter({ hasText: 'history-main-old' }).first()).toBeVisible()

  await page.locator('textarea').fill(repeatedQuestion)
  await page.locator('textarea').press('Enter')
  await expect(page.locator('.message.assistant .text').filter({ hasText: repeatedReply }).first()).toBeVisible()

  await page.locator('textarea').fill(repeatedQuestion)
  await page.locator('textarea').press('Enter')

  await expect.poll(async () => {
    const count = await page.locator('.message.assistant .text').filter({ hasText: repeatedReply }).count()
    return count
  }).toBeGreaterThanOrEqual(2)

  await page.reload()

  await expect.poll(async () => {
    const count = await page.locator('.message.assistant .text').filter({ hasText: repeatedReply }).count()
    return count
  }).toBeGreaterThanOrEqual(2)
})


test('recent completion should not duplicate when history reply has no ts', async ({ page }) => {
  await setupStudentState(page, {
    clearLocalStorage: false,
    stateOverrides: {
      verifiedStudent: JSON.stringify({
        student_id: 'S001',
        student_name: '测试学生',
        class_name: '高二1班',
      }),
    },
  })

  const pendingUserText = '缺失时间戳恢复'
  const resolvedReply = '无ts历史回复'
  const historyCallsBySession: Record<string, number> = {}

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
          sessions: [
            { session_id: 'main', updated_at: new Date().toISOString(), message_count: 1, preview: 'history-main-old' },
            { session_id: 's2', updated_at: new Date().toISOString(), message_count: 1, preview: 'history-s2' },
          ],
          next_cursor: null,
          total: 2,
        }),
      })
      return
    }

    if (method === 'GET' && path === '/student/history/session') {
      const sessionId = String(url.searchParams.get('session_id') || 'main')
      historyCallsBySession[sessionId] = (historyCallsBySession[sessionId] || 0) + 1

      if (sessionId === 's2') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            ok: true,
            student_id: 'S001',
            session_id: 's2',
            messages: [{ ts: new Date().toISOString(), role: 'assistant', content: 'history-s2' }],
            next_cursor: -1,
          }),
        })
        return
      }

      const includeResolved = (historyCallsBySession.main || 0) >= 2
      const mainMessages = includeResolved
        ? [
            { ts: new Date().toISOString(), role: 'assistant', content: 'history-main-old' },
            { ts: new Date().toISOString(), role: 'user', content: pendingUserText },
            { role: 'assistant', content: resolvedReply },
          ]
        : [{ ts: new Date().toISOString(), role: 'assistant', content: 'history-main-old' }]

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: true,
          student_id: 'S001',
          session_id: 'main',
          messages: mainMessages,
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
        body: JSON.stringify({ ok: true, job_id: 'student_missing_ts_pending', status: 'queued' }),
      })
      return
    }

    if (method === 'GET' && path === '/chat/status') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ job_id: 'student_missing_ts_pending', status: 'done', reply: resolvedReply }),
      })
      return
    }

    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true }) })
  })

  await page.goto('/')
  await expect(page.locator('.message.assistant .text').filter({ hasText: 'history-main-old' }).first()).toBeVisible()

  await page.locator('textarea').fill(pendingUserText)
  await page.locator('textarea').press('Enter')
  await expect(page.locator('.message.assistant .text').filter({ hasText: resolvedReply }).first()).toBeVisible()

  const openSidebarIfNeeded = async () => {
    const expandSidebarButton = page.getByRole('button', { name: '展开会话' })
    if (await expandSidebarButton.isVisible()) {
      await expandSidebarButton.click()
    }
  }

  await openSidebarIfNeeded()
  const sessionS2 = page.locator('.session-item .session-select').filter({ hasText: 's2' }).first()
  await sessionS2.click()
  await expect(page.locator('.message.assistant .text').filter({ hasText: 'history-s2' }).first()).toBeVisible()

  await openSidebarIfNeeded()
  const sessionMain = page.locator('.session-item .session-select').filter({ hasText: 'main' }).first()
  await sessionMain.click()

  await expect.poll(() => historyCallsBySession.main || 0).toBeGreaterThanOrEqual(2)
  await expect.poll(async () => {
    const count = await page.locator('.message.assistant .text').filter({ hasText: resolvedReply }).count()
    return count
  }).toBe(1)
})
