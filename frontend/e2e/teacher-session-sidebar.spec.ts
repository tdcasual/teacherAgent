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
      teacherMobileShellV2: '0',
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
      teacherMobileShellV2: '0',
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

test('mobile session menu closes on pointerdown outside', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openTeacherApp(page, {
    stateOverrides: {
      teacherMobileShellV2: '0',
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

  await page.locator('.session-menu-trigger').first().click()
  const menu = page.locator('.session-menu').first()
  await expect(menu).toBeVisible()

  await page.evaluate(() => {
    document.body.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, pointerType: 'touch' }))
  })

  await expect(menu).toBeHidden()
})

test('mobile shell v2 starts in chat without auto-opening sheets', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openTeacherApp(page, {
    stateOverrides: {
      teacherMobileShellV2: '1',
    },
  })

  const activeLabel = page.locator('.mobile-tabbar-button.active .mobile-tabbar-label')
  await expect(activeLabel).toBeVisible()
  await expect(activeLabel).toHaveText('聊天')
  await expect(page.locator('.mobile-sheet-layer')).toHaveCount(0)
})

test('mobile shell v2 closing workbench sheet returns to chat without chaining session sheet', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openTeacherApp(page, {
    stateOverrides: {
      teacherMobileShellV2: '1',
    },
  })

  await page.locator('.mobile-tabbar-button', { hasText: '工作台' }).click()
  await expect(page.locator('.mobile-sheet-title')).toHaveText('工作台')
  await page.locator('.mobile-sheet-close').click()

  const activeLabel = page.locator('.mobile-tabbar-button.active .mobile-tabbar-label')
  await expect(activeLabel).toHaveText('聊天')
  await expect(page.locator('.mobile-sheet-layer')).toHaveCount(0)
  await page.waitForTimeout(300)
  await expect(page.getByRole('dialog', { name: '历史会话' })).toHaveCount(0)
})

test('mobile shell v2 tab switching does not trigger runtime errors', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  const runtimeErrors: string[] = []
  page.on('console', (message) => {
    if (message.type() !== 'error') return
    const text = message.text()
    if (!/(Maximum update depth exceeded|TypeError|ReferenceError|Cannot read)/i.test(text)) return
    runtimeErrors.push(text)
  })
  page.on('pageerror', (error) => runtimeErrors.push(error.message))

  await openTeacherApp(page, {
    stateOverrides: {
      teacherMobileShellV2: '1',
    },
  })

  const sessionsTab = page.locator('.mobile-tabbar-button', { hasText: '会话' })
  const workbenchTab = page.locator('.mobile-tabbar-button', { hasText: '工作台' })
  const chatTab = page.locator('.mobile-tabbar-button', { hasText: '聊天' })

  await sessionsTab.click()
  await expect(page.locator('.mobile-sheet-title')).toHaveText('历史会话')
  await workbenchTab.click()
  await expect(page.locator('.mobile-sheet-title')).toHaveText('工作台')
  await chatTab.click()
  await expect(page.locator('.mobile-sheet-layer')).toHaveCount(0)
  await page.waitForTimeout(300)

  expect(runtimeErrors).toHaveLength(0)
})

test('mobile auth panel stays within viewport on narrow width', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 568 })
  await openTeacherApp(page, {
    stateOverrides: {
      teacherMobileShellV2: '1',
    },
  })

  await page.getByRole('button', { name: '认证' }).click()
  const panel = page.getByText('教师认证').locator('..').first()
  await expect(panel).toBeVisible()

  const box = await panel.boundingBox()
  expect(box).not.toBeNull()
  if (!box) return

  expect(box.x).toBeGreaterThanOrEqual(0)
  expect(box.x + box.width).toBeLessThanOrEqual(320)
})

test('mobile more menu closes when tapping outside', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 667 })
  await openTeacherApp(page, {
    stateOverrides: {
      teacherMobileShellV2: '1',
    },
  })

  await page.getByRole('button', { name: '更多' }).click()
  const menuItem = page.getByRole('button', { name: '模型路由' }).first()
  await expect(menuItem).toBeVisible()

  await page.mouse.click(8, 220)
  await expect(menuItem).toBeHidden()
})

test('mobile auth panel closes on Escape', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openTeacherApp(page, {
    stateOverrides: {
      teacherMobileShellV2: '1',
    },
  })

  await page.getByRole('button', { name: '认证' }).click()
  const panel = page.getByText('教师认证').first()
  await expect(panel).toBeVisible()

  await page.keyboard.press('Escape')
  await expect(panel).toBeHidden()
})

test('mobile auth panel closes when tapping outside', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openTeacherApp(page, {
    stateOverrides: {
      teacherMobileShellV2: '1',
    },
  })

  await page.getByRole('button', { name: '认证' }).click()
  const panel = page.getByText('教师认证').first()
  await expect(panel).toBeVisible()

  await page.mouse.click(8, 220)
  await expect(panel).toBeHidden()
})

test('mobile auth panel closes when switching tabs', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openTeacherApp(page, {
    stateOverrides: {
      teacherMobileShellV2: '1',
    },
  })

  await page.getByRole('button', { name: '认证' }).click()
  const panel = page.getByText('教师认证').first()
  await expect(panel).toBeVisible()

  await page.getByRole('tab', { name: '会话' }).click()
  await expect(page.locator('.mobile-sheet-title')).toHaveText('历史会话')
  await expect(panel).toBeHidden()
})

test('mobile session dialog renders above session sheet layer', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openTeacherApp(page, {
    stateOverrides: {
      teacherMobileShellV2: '1',
    },
    apiMocks: {
      historyBySession: {
        main: [{ ts: new Date().toISOString(), role: 'assistant', content: 'main' }],
        s2: [{ ts: new Date().toISOString(), role: 'assistant', content: 's2' }],
      },
    },
  })

  await page.getByRole('tab', { name: '会话' }).click()
  await expect(page.locator('.mobile-sheet-title')).toHaveText('历史会话')

  await page.locator('.session-menu-trigger').first().click()
  await page.getByRole('menuitem', { name: '重命名', exact: true }).click()

  const dialog = page.getByRole('dialog', { name: '重命名会话' })
  await expect(dialog).toBeVisible()

  const topHitIsDialog = await page.evaluate(() => {
    const panel = document.querySelector('.app-dialog') as HTMLElement | null
    if (!panel) return false
    const rect = panel.getBoundingClientRect()
    const x = Math.round(rect.left + rect.width / 2)
    const y = Math.round(rect.top + rect.height / 2)
    const hit = document.elementFromPoint(x, y)
    return Boolean(hit && panel.contains(hit))
  })

  expect(topHitIsDialog).toBe(true)
})

test('mobile settings modal overlays tabbar hit target', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openTeacherApp(page, {
    stateOverrides: {
      teacherMobileShellV2: '1',
    },
  })

  await page.getByRole('button', { name: '更多' }).click()
  await page.getByRole('button', { name: '打开设置' }).click()
  await expect(page.getByRole('dialog', { name: '设置' })).toBeVisible()

  const bottomHitIsSettingsOverlay = await page.evaluate(() => {
    const overlay = document.querySelector('.settings-overlay') as HTMLElement | null
    if (!overlay) return false
    const x = Math.round(window.innerWidth / 2)
    const y = Math.round(window.innerHeight - 12)
    const hit = document.elementFromPoint(x, y)
    return Boolean(hit && overlay.contains(hit))
  })

  expect(bottomHitIsSettingsOverlay).toBe(true)
})

test('mobile persona manager overlays tabbar hit target', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await openTeacherApp(page, {
    stateOverrides: {
      teacherMobileShellV2: '1',
    },
  })

  await page.getByRole('button', { name: '更多' }).click()
  await page.getByRole('button', { name: '角色管理' }).click()
  await expect(page.getByRole('dialog', { name: '角色管理' })).toBeVisible()

  const bottomHitIsPersonaOverlay = await page.evaluate(() => {
    const overlay = document.querySelector('[role=\"dialog\"][aria-label=\"角色管理\"]') as HTMLElement | null
    if (!overlay) return false
    const x = Math.round(window.innerWidth / 2)
    const y = Math.round(window.innerHeight - 12)
    const hit = document.elementFromPoint(x, y)
    return Boolean(hit && overlay.contains(hit))
  })

  expect(bottomHitIsPersonaOverlay).toBe(true)
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
