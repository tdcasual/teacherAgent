import { expect, test } from '@playwright/test'
import { TEACHER_COMPOSER_PLACEHOLDER, openTeacherApp } from './helpers/teacherHarness'

const sseEvent = (eventId: number, eventType: string, payload: Record<string, unknown>) =>
  `id:${eventId}\nevent:${eventType}\ndata:${JSON.stringify({ type: eventType, event_id: eventId, event_version: 1, payload })}\n\n`

test('teacher mutating tool confirm dialog posts /teacher/tools/confirm', async ({ page }) => {
  const confirmPosts: Array<{ confirm_id?: string; confirmed?: boolean }> = []
  const { chatStartCalls } = await openTeacherApp(page)

  await page.route('**/chat/stream**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: [
        sseEvent(1, 'job.processing', {}),
        sseEvent(2, 'tool.confirm_required', {
          confirm_id: 'e2e-confirm',
          tool: 'student.profile.update',
          preview: '{"student_id":"S1"}',
        }),
      ].join(''),
    })
  })
  await page.route('**/teacher/tools/confirm', async (route) => {
    const body = JSON.parse(route.request().postData() || '{}') as { confirm_id?: string; confirmed?: boolean }
    confirmPosts.push(body)
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, job_id: 'job_1', executed: true }),
    })
  })
  await page.route('**/chat/status**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ job_id: 'job_1', status: confirmPosts.length ? 'done' : 'processing', reply: '已更新' }),
    })
  })

  const composer = page.getByPlaceholder(TEACHER_COMPOSER_PLACEHOLDER)
  await composer.fill('更新学生画像')
  await page.getByRole('button', { name: '发送' }).click()
  await expect.poll(() => chatStartCalls.length).toBe(1)
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByText('确认执行写操作？')).toBeVisible()
  await page.getByRole('button', { name: '确认执行' }).click()
  await expect.poll(() => confirmPosts.length).toBe(1)
  expect(confirmPosts[0]).toEqual({ confirm_id: 'e2e-confirm', confirmed: true })
})
