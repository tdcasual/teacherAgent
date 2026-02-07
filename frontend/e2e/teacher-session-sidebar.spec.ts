import { expect, test } from '@playwright/test'
import { openTeacherApp } from './helpers/teacherHarness'

test('session search filters by title and preview text', async ({ page }) => {
  await openTeacherApp(page, {
    stateOverrides: {
      teacherSessionSidebarOpen: 'true',
    },
    apiMocks: {
      historyBySession: {
        main: [{ ts: new Date().toISOString(), role: 'assistant', content: '欢迎' }],
        s_alpha: [{ ts: new Date().toISOString(), role: 'assistant', content: '静电场错题回看' }],
        s_beta: [{ ts: new Date().toISOString(), role: 'assistant', content: '牛顿定律梳理' }],
      },
    },
  })

  await expect(page.locator('.session-item')).toHaveCount(3)

  await page.getByPlaceholder('搜索会话').fill('静电场')
  await expect(page.locator('.session-item', { hasText: 's_alpha' })).toHaveCount(1)
  await expect(page.locator('.session-item', { hasText: 's_beta' })).toHaveCount(0)

  await page.getByPlaceholder('搜索会话').fill('牛顿')
  await expect(page.locator('.session-item', { hasText: 's_beta' })).toHaveCount(1)
  await expect(page.locator('.session-item', { hasText: 's_alpha' })).toHaveCount(0)
})

test('archived toggle switches between active and archived sessions', async ({ page }) => {
  await openTeacherApp(page, {
    stateOverrides: {
      teacherSessionSidebarOpen: 'true',
      teacherSessionViewState: JSON.stringify({
        title_map: {
          s_archived: '已归档会话',
          s_live: '进行中会话',
        },
        hidden_ids: ['s_archived'],
        active_session_id: 'main',
        updated_at: '2099-01-01T00:00:00.000Z',
      }),
    },
    apiMocks: {
      historyBySession: {
        main: [{ ts: new Date().toISOString(), role: 'assistant', content: 'main' }],
        s_archived: [{ ts: new Date().toISOString(), role: 'assistant', content: 'archived' }],
        s_live: [{ ts: new Date().toISOString(), role: 'assistant', content: 'live' }],
      },
    },
  })

  const initialSessionIds = (await page.locator('.session-item .session-id').allTextContents()).join('|')
  expect(initialSessionIds).toMatch(/s_live|进行中会话/)
  expect(initialSessionIds).not.toMatch(/s_archived|已归档会话/)

  await page.getByRole('button', { name: '查看归档' }).click()
  const archivedSessionIds = (await page.locator('.session-item .session-id').allTextContents()).join('|')
  expect(archivedSessionIds).toMatch(/s_archived|已归档会话/)
  expect(archivedSessionIds).not.toMatch(/s_live|进行中会话/)

  await page.getByRole('button', { name: '查看会话' }).click()
  const restoredSessionIds = (await page.locator('.session-item .session-id').allTextContents()).join('|')
  expect(restoredSessionIds).toMatch(/s_live|进行中会话/)
})

test('session menu trigger updates aria-expanded and closes on Escape', async ({ page }) => {
  await openTeacherApp(page, {
    stateOverrides: {
      teacherSessionSidebarOpen: 'true',
      teacherSkillsOpen: 'false',
    },
    apiMocks: {
      historyBySession: {
        main: [{ ts: new Date().toISOString(), role: 'assistant', content: 'main' }],
        s2: [{ ts: new Date().toISOString(), role: 'assistant', content: 's2' }],
      },
    },
  })

  const trigger = page.locator('.session-menu-trigger').first()
  await expect(trigger).toHaveAttribute('aria-expanded', 'false')

  await trigger.click()
  await expect(trigger).toHaveAttribute('aria-expanded', 'true')
  await expect(page.locator('.session-menu')).toBeVisible()

  await page.keyboard.press('Escape')
  await expect(trigger).toHaveAttribute('aria-expanded', 'false')
  await expect(page.locator('.session-menu')).toBeHidden()
})

test('history and older-message load buttons are disabled when no more data', async ({ page }) => {
  await openTeacherApp(page, {
    stateOverrides: {
      teacherSessionSidebarOpen: 'true',
    },
    apiMocks: {
      historyBySession: {
        main: [{ ts: new Date().toISOString(), role: 'assistant', content: 'main' }],
      },
    },
  })

  const loadSessionsBtn = page.getByRole('button', { name: '已显示全部会话' })
  const loadOlderBtn = page.getByRole('button', { name: '没有更早消息' })
  await expect(loadSessionsBtn).toBeDisabled()
  await expect(loadOlderBtn).toBeDisabled()
})

test('mobile selecting a session collapses sidebar', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openTeacherApp(page, {
    stateOverrides: {
      teacherSessionSidebarOpen: 'true',
    },
    apiMocks: {
      historyBySession: {
        main: [{ ts: new Date().toISOString(), role: 'assistant', content: 'main' }],
        s2: [{ ts: new Date().toISOString(), role: 'assistant', content: 's2' }],
      },
    },
  })

  await expect(page.getByRole('button', { name: '收起会话' })).toBeVisible()
  const collapseWorkbench = page.getByRole('button', { name: '收起工作台' })
  if (await collapseWorkbench.isVisible()) {
    await collapseWorkbench.evaluate((node) => {
      ;(node as HTMLButtonElement).click()
    })
  }

  await page
    .locator('.session-item', { hasText: 's2' })
    .first()
    .locator('.session-select')
    .evaluate((node) => {
      ;(node as HTMLButtonElement).click()
    })

  await expect(page.getByRole('button', { name: '展开会话' })).toBeVisible()
})

test('mobile session menu supports keyboard navigation and escape focus return', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openTeacherApp(page, {
    stateOverrides: {
      teacherSessionSidebarOpen: 'true',
      teacherSkillsOpen: 'false',
    },
    apiMocks: {
      historyBySession: {
        main: [{ ts: new Date().toISOString(), role: 'assistant', content: 'main' }],
        s2: [{ ts: new Date().toISOString(), role: 'assistant', content: 's2' }],
      },
    },
  })

  const trigger = page.locator('.session-menu-trigger').first()
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

test('new session is created with session_* id and becomes active', async ({ page }) => {
  await openTeacherApp(page, {
    stateOverrides: {
      teacherSessionSidebarOpen: 'true',
    },
  })

  await page.getByRole('button', { name: '新建' }).click()

  const firstSessionId = (await page.locator('.session-item .session-id').first().textContent())?.trim() || ''
  expect(firstSessionId.startsWith('session_')).toBe(true)
  await expect(page.locator('.session-item.active').first()).toContainText(firstSessionId)
})
