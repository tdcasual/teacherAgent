import { expect, test } from '@playwright/test'

import { API_BASE, callJson, callText, fulfillJson } from './helpers'

test.describe('v2 chat and job smoke', () => {
  test('@v2-smoke C01 chat send enqueues job', async ({ page }) => {
    await page.route(`${API_BASE}/api/v2/chat/send`, async (route) => {
      await fulfillJson(route, 200, { job_id: 'chat-job-1', status: 'queued' })
    })

    const result = await callJson(page, '/api/v2/chat/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { session_id: 's1', message: 'hello' },
    })

    expect(result.status).toBe(200)
    expect(result.json).toEqual({ job_id: 'chat-job-1', status: 'queued' })
  })

  test('@v2-smoke C02 chat send validation error', async ({ page }) => {
    await page.route(`${API_BASE}/api/v2/chat/send`, async (route) => {
      await fulfillJson(route, 400, { error_code: 'CHAT_MESSAGE_REQUIRED', message: 'message is required' })
    })

    const result = await callJson(page, '/api/v2/chat/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { session_id: 's1', message: '' },
    })

    expect(result.status).toBe(400)
    expect(result.json).toEqual({ error_code: 'CHAT_MESSAGE_REQUIRED', message: 'message is required' })
  })

  test('@v2-smoke C03 chat event stream returns sse frames', async ({ page }) => {
    await page.route(`${API_BASE}/api/v2/chat/events?job_id=chat-job-1`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: `event: progress\ndata: 50%\n\nevent: done\ndata: ok\n\n`,
      })
    })

    const result = await callText(page, '/api/v2/chat/events?job_id=chat-job-1')
    expect(result.status).toBe(200)
    expect(result.text).toContain('event: progress')
    expect(result.text).toContain('event: done')
  })

  test('@v2-smoke C04 job status endpoint shows terminal state', async ({ page }) => {
    await page.route(`${API_BASE}/api/v2/jobs/chat-job-1`, async (route) => {
      await fulfillJson(route, 200, {
        job_id: 'chat-job-1',
        state: 'done',
      })
    })

    const result = await callJson(page, '/api/v2/jobs/chat-job-1')
    expect(result.status).toBe(200)
    expect(result.json).toMatchObject({ job_id: 'chat-job-1', state: 'done' })
  })
})
