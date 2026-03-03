import { expect, test } from '@playwright/test'

import { API_BASE, callJson, fulfillJson } from './helpers'

test.describe('v2 admin core smoke', () => {
  test('@v2-smoke A01 reset teacher token success', async ({ page }) => {
    await page.route(`${API_BASE}/api/v2/admin/teacher/reset-token`, async (route) => {
      await fulfillJson(route, 200, { token: 'T-NEW-1' })
    })

    const result = await callJson(page, '/api/v2/admin/teacher/reset-token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { teacher_id: 't1' },
    })
    expect(result.status).toBe(200)
    expect(result.json).toEqual({ token: 'T-NEW-1' })
  })

  test('@v2-smoke A02 reset teacher token validation', async ({ page }) => {
    await page.route(`${API_BASE}/api/v2/admin/teacher/reset-token`, async (route) => {
      await fulfillJson(route, 400, { error_code: 'ADMIN_TEACHER_REQUIRED', message: 'teacher is required' })
    })

    const result = await callJson(page, '/api/v2/admin/teacher/reset-token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { teacher_id: '' },
    })
    expect(result.status).toBe(400)
    expect(result.json).toEqual({ error_code: 'ADMIN_TEACHER_REQUIRED', message: 'teacher is required' })
  })

  test('@v2-smoke A03 reset teacher token server failure', async ({ page }) => {
    await page.route(`${API_BASE}/api/v2/admin/teacher/reset-token`, async (route) => {
      await fulfillJson(route, 500, { error_code: 'ADMIN_RESET_TOKEN_FAILED', message: 'reset token failed' })
    })

    const result = await callJson(page, '/api/v2/admin/teacher/reset-token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { teacher_id: 't1' },
    })
    expect(result.status).toBe(500)
    expect(result.json).toEqual({ error_code: 'ADMIN_RESET_TOKEN_FAILED', message: 'reset token failed' })
  })

  test('@v2-smoke A04 common error envelope shape', async ({ page }) => {
    await page.route(`${API_BASE}/api/v2/admin/teacher/reset-token`, async (route) => {
      await fulfillJson(route, 403, { error_code: 'AUTH_FORBIDDEN', message: 'forbidden' })
    })

    const result = await callJson(page, '/api/v2/admin/teacher/reset-token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { teacher_id: 't1' },
    })
    expect(result.status).toBe(403)
    expect(result.json).toMatchObject({ error_code: 'AUTH_FORBIDDEN', message: 'forbidden' })
  })
})
