import { expect, test, type Route } from '@playwright/test'
import { openStudentApp } from './helpers/studentHarness'

type ChatStartPayload = {
  attachments?: Array<{ attachment_id?: string }>
  messages?: Array<{ role?: string; content?: string }>
}

test('student composer supports attachment-only send with attachment refs', async ({ page }) => {
  await openStudentApp(page, {
    stateOverrides: { studentSidebarOpen: 'false' },
  })

  let uploadCallCount = 0
  let chatStartPayload: ChatStartPayload | null = null

  const attachmentRoute = async (route: Route) => {
    uploadCallCount += 1
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        attachments: [
          {
            attachment_id: 'att_e2e_student_1',
            file_name: 'review.md',
            size_bytes: 64,
            status: 'ready',
          },
        ],
      }),
    })
  }

  await page.route('http://localhost:8000/chat/attachments', attachmentRoute)
  await page.route('http://127.0.0.1:8000/chat/attachments', attachmentRoute)

  const chatStartRoute = async (route: Route) => {
    chatStartPayload = JSON.parse(route.request().postData() || '{}') as ChatStartPayload
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        job_id: 'student_job_1',
        status: 'queued',
      }),
    })
  }
  await page.route('http://localhost:8000/chat/start', chatStartRoute)
  await page.route('http://127.0.0.1:8000/chat/start', chatStartRoute)

  const panel = page.getByTestId('student-chat-panel')
  const fileInput = panel.locator('input[type="file"]').first()
  await fileInput.setInputFiles([
    {
      name: 'review.md',
      mimeType: 'text/markdown',
      buffer: Buffer.from('## 错题复盘\n1. 受力分析', 'utf-8'),
    },
  ])

  await expect.poll(() => uploadCallCount).toBe(1)
  await expect(panel.getByText('review.md')).toBeVisible()
  await expect(panel.getByText('已就绪').first()).toBeVisible()

  const sendButton = panel.getByRole('button', { name: '发送' })
  await expect(sendButton).toBeEnabled()
  await sendButton.click()

  await expect.poll(() => (chatStartPayload ? 1 : 0)).toBe(1)
  expect(Array.isArray(chatStartPayload?.attachments)).toBe(true)
  expect(chatStartPayload?.attachments?.[0]?.attachment_id).toBe('att_e2e_student_1')
  expect((chatStartPayload?.messages || []).some((item) =>
    String(item?.content || '').includes('请阅读我上传的附件并回答。'),
  )).toBe(true)
})
