import { expect, test } from '@playwright/test'
import { openStudentApp } from './helpers/studentHarness'

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
