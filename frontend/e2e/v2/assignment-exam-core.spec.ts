import { expect, test } from '@playwright/test'

import { API_BASE, callJson, fulfillJson } from './helpers'

test.describe('v2 assignment and exam smoke', () => {
  test('@v2-smoke E01 assignment confirm queued', async ({ page }) => {
    await page.route(`${API_BASE}/api/v2/assignment/confirm`, async (route) => {
      await fulfillJson(route, 200, { status: 'queued' })
    })

    const result = await callJson(page, '/api/v2/assignment/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { draft_id: 'd1' },
    })
    expect(result.status).toBe(200)
    expect(result.json).toEqual({ status: 'queued' })
  })

  test('@v2-smoke E02 exam parse creates queued job', async ({ page }) => {
    await page.route(`${API_BASE}/api/v2/exam/parse`, async (route) => {
      await fulfillJson(route, 200, { job_id: 'job-1', status: 'queued' })
    })

    const result = await callJson(page, '/api/v2/exam/parse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { resource_id: 'res-1' },
    })
    expect(result.status).toBe(200)
    expect(result.json).toEqual({ job_id: 'job-1', status: 'queued' })
  })

  test('@v2-smoke E03 exam parse rejects missing resource', async ({ page }) => {
    await page.route(`${API_BASE}/api/v2/exam/parse`, async (route) => {
      await fulfillJson(route, 400, { error_code: 'EXAM_RESOURCE_REQUIRED', message: 'resource is required' })
    })

    const result = await callJson(page, '/api/v2/exam/parse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { resource_id: '' },
    })
    expect(result.status).toBe(400)
    expect(result.json).toEqual({ error_code: 'EXAM_RESOURCE_REQUIRED', message: 'resource is required' })
  })
})
