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
      const targets = new Set(['正在生成…', '正在恢复上一条回复…'])
      return Array.from(document.querySelectorAll('.message.assistant .text')).filter((el) =>
        targets.has(String((el as HTMLElement).innerText || '').trim()),
      ).length
    })

  await page.goto('/')
  await expect(page.getByRole('button', { name: '发送' })).toBeVisible()

  let maxPendingStatusCount = 0
  for (let i = 0; i < 16; i += 1) {
    const current = await pendingStatusCount()
    maxPendingStatusCount = Math.max(maxPendingStatusCount, current)
    await page.waitForTimeout(120)
  }
  expect(maxPendingStatusCount).toBeLessThanOrEqual(1)
})
