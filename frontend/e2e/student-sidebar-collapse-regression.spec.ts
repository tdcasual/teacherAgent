import { expect, test } from '@playwright/test'
import { openStudentApp } from './helpers/studentHarness'

test('desktop sidebar stays collapsed after manual toggle', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 })
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
      },
    },
  })

  await page.getByRole('button', { name: '收起会话' }).click()
  await page.waitForTimeout(300)

  await expect(page.getByRole('button', { name: '展开会话' })).toBeVisible()
  await expect.poll(async () =>
    page.evaluate(() => {
      const layout = document.querySelector('.student-layout')
      return Boolean(layout?.classList.contains('sidebar-collapsed'))
    }),
  ).toBe(true)

  await expect.poll(async () =>
    page.evaluate(() => localStorage.getItem('studentSidebarOpen')),
  ).toBe('false')
})
