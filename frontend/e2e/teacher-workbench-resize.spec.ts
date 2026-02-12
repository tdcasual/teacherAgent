import { expect, test } from '@playwright/test'
import { openTeacherApp } from './helpers/teacherHarness'

test('desktop dragging workbench separator changes workbench width', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  await openTeacherApp(page)

  const separator = page.locator('[data-separator]').first()
  const workbenchPanel = page.locator('[data-panel]').filter({ has: page.getByRole('heading', { name: '工作台' }) }).first()

  await expect(separator).toBeVisible()
  await expect(workbenchPanel).toBeVisible()

  const separatorBox = await separator.boundingBox()
  const beforeBox = await workbenchPanel.boundingBox()
  expect(separatorBox).not.toBeNull()
  expect(beforeBox).not.toBeNull()

  const startX = separatorBox!.x + separatorBox!.width / 2
  const startY = separatorBox!.y + separatorBox!.height / 2

  await page.mouse.move(startX, startY)
  await page.mouse.down()
  await page.mouse.move(startX - 140, startY, { steps: 8 })
  await page.mouse.up()

  await expect
    .poll(async () => {
      const box = await workbenchPanel.boundingBox()
      return box?.width ?? 0
    })
    .toBeGreaterThan((beforeBox?.width ?? 0) + 80)
})
