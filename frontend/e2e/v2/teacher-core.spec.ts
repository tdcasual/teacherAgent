import { expect, test } from '@playwright/test'

import { API_BASE, callJson, fulfillJson } from './helpers'

test.describe('v2 teacher core smoke', () => {
  test('@v2-smoke T01 student login success', async ({ page }) => {
    await page.route(`${API_BASE}/api/v2/auth/student/login`, async (route) => {
      await fulfillJson(route, 200, { access_token: 'token-1' })
    })

    const result = await callJson(page, '/api/v2/auth/student/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { student_id: 'stu-1', credential: 'S-123' },
    })

    expect(result.status).toBe(200)
    expect(result.json).toEqual({ access_token: 'token-1' })
  })

  test('@v2-smoke T02 student login invalid credential', async ({ page }) => {
    await page.route(`${API_BASE}/api/v2/auth/student/login`, async (route) => {
      await fulfillJson(route, 401, { error_code: 'AUTH_INVALID_CREDENTIAL', message: 'invalid credential' })
    })

    const result = await callJson(page, '/api/v2/auth/student/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { student_id: 'stu-1', credential: 'wrong' },
    })

    expect(result.status).toBe(401)
    expect(result.json).toEqual({ error_code: 'AUTH_INVALID_CREDENTIAL', message: 'invalid credential' })
  })

  test('@v2-smoke T03 file upload accepted', async ({ page }) => {
    await page.route(`${API_BASE}/api/v2/files/upload`, async (route) => {
      await fulfillJson(route, 200, { resource_id: 'res-1' })
    })

    const result = await callJson(page, '/api/v2/files/upload', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { file_name: 'lesson.pdf', size_bytes: 1024 },
    })

    expect(result.status).toBe(200)
    expect(result.json).toEqual({ resource_id: 'res-1' })
  })

  test('@v2-smoke T04 file upload guardrail rejects oversize', async ({ page }) => {
    await page.route(`${API_BASE}/api/v2/files/upload`, async (route) => {
      await fulfillJson(route, 413, { error_code: 'FILE_TOO_LARGE', message: 'file too large' })
    })

    const result = await callJson(page, '/api/v2/files/upload', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { file_name: 'big.pdf', size_bytes: 70 << 20 },
    })

    expect(result.status).toBe(413)
    expect(result.json).toEqual({ error_code: 'FILE_TOO_LARGE', message: 'file too large' })
  })

  test('@v2-smoke T05 assignment confirm queued', async ({ page }) => {
    await page.route(`${API_BASE}/api/v2/assignment/confirm`, async (route) => {
      await fulfillJson(route, 200, { status: 'queued' })
    })

    const result = await callJson(page, '/api/v2/assignment/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { draft_id: 'draft-1' },
    })

    expect(result.status).toBe(200)
    expect(result.json).toEqual({ status: 'queued' })
  })

  test('@v2-smoke T06 assignment invalid state', async ({ page }) => {
    await page.route(`${API_BASE}/api/v2/assignment/confirm`, async (route) => {
      await fulfillJson(route, 409, { error_code: 'ASSIGNMENT_INVALID_STATE', message: 'invalid draft state' })
    })

    const result = await callJson(page, '/api/v2/assignment/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { draft_id: 'draft-1' },
    })

    expect(result.status).toBe(409)
    expect(result.json).toEqual({ error_code: 'ASSIGNMENT_INVALID_STATE', message: 'invalid draft state' })
  })

  test('@v2-smoke T07 health endpoint returns ok', async ({ page }) => {
    await page.route(`${API_BASE}/healthz`, async (route) => {
      await fulfillJson(route, 200, { status: 'ok' })
    })

    const result = await callJson(page, '/healthz')

    expect(result.status).toBe(200)
    expect(result.json).toEqual({ status: 'ok' })
  })
})
