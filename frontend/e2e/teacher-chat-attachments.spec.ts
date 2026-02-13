import { expect, test, type Route } from '@playwright/test'
import { openTeacherApp, TEACHER_COMPOSER_PLACEHOLDER, type ChatStartPayload } from './helpers/teacherHarness'

type ChatStartWithAttachments = ChatStartPayload & {
  attachments?: Array<{ attachment_id?: string }>
}

test('teacher composer uploads attachment then sends attachment refs', async ({ page }) => {
  const mocks = await openTeacherApp(page)
  let uploadCallCount = 0

  const attachmentRoute = async (route: Route) => {
    uploadCallCount += 1
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        attachments: [
          {
            attachment_id: 'att_e2e_teacher_1',
            file_name: 'lesson.md',
            size_bytes: 128,
            status: 'ready',
          },
        ],
      }),
    })
  }

  await page.route('http://localhost:8000/chat/attachments', attachmentRoute)
  await page.route('http://127.0.0.1:8000/chat/attachments', attachmentRoute)

  const composer = page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER)
  const fileInput = page
    .locator('form')
    .filter({ has: page.getByRole('button', { name: '发送' }) })
    .locator('input[type="file"]')
    .first()

  await fileInput.setInputFiles([
    {
      name: 'lesson.md',
      mimeType: 'text/markdown',
      buffer: Buffer.from('# 课堂笔记\n牛顿第二定律 F=ma', 'utf-8'),
    },
  ])

  await expect.poll(() => uploadCallCount).toBe(1)
  await expect(page.getByText('lesson.md')).toBeVisible()
  await expect(page.getByText('已就绪').first()).toBeVisible()

  await composer.fill('请基于附件总结关键知识点')
  await page.getByRole('button', { name: '发送' }).click()

  await expect.poll(() => mocks.chatStartCalls.length).toBe(1)
  const payload = (mocks.chatStartCalls[0] || {}) as ChatStartWithAttachments
  expect(Array.isArray(payload.attachments)).toBe(true)
  expect(payload.attachments?.[0]?.attachment_id).toBe('att_e2e_teacher_1')
})
