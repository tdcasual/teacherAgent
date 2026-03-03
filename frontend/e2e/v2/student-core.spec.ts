import { expect, test } from '@playwright/test'

import { API_BASE, callJson, fulfillJson } from './helpers'

test.describe('v2 student core smoke', () => {
  test('@v2-smoke S01 list personas', async ({ page }) => {
    await page.route(`${API_BASE}/student/personas?student_id=S001`, async (route) => {
      await fulfillJson(route, 200, {
        ok: true,
        assigned: [{ persona_id: 'p1', title: 'Teacher Card' }],
        custom: [{ persona_id: 'p2', title: 'My Card', review_status: 'approved' }],
        active_persona_id: 'p1',
      })
    })

    const result = await callJson(page, '/student/personas?student_id=S001')
    expect(result.status).toBe(200)
    expect(result.json).toMatchObject({ ok: true, active_persona_id: 'p1' })
  })

  test('@v2-smoke S02 activate persona', async ({ page }) => {
    await page.route(`${API_BASE}/student/personas/activate`, async (route) => {
      await fulfillJson(route, 200, { ok: true })
    })

    const result = await callJson(page, '/student/personas/activate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: { student_id: 'S001', persona_id: 'p2' },
    })
    expect(result.status).toBe(200)
    expect(result.json).toEqual({ ok: true })
  })

  test('@v2-smoke S03 create custom persona approved', async ({ page }) => {
    await page.route(`${API_BASE}/student/personas/custom`, async (route) => {
      await fulfillJson(route, 200, {
        persona: { review_status: 'approved', review_reason: '' },
      })
    })

    const result = await callJson(page, '/student/personas/custom', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: {
        student_id: 'S001',
        name: 'My Persona',
        summary: 'summary',
        style_rules: ['rule'],
        few_shot_examples: ['example'],
      },
    })
    expect(result.status).toBe(200)
    expect(result.json).toMatchObject({ persona: { review_status: 'approved' } })
  })

  test('@v2-smoke S04 create custom persona rejected', async ({ page }) => {
    await page.route(`${API_BASE}/student/personas/custom`, async (route) => {
      await fulfillJson(route, 200, {
        persona: { review_status: 'rejected', review_reason: 'contains_unsafe_instruction' },
      })
    })

    const result = await callJson(page, '/student/personas/custom', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: {
        student_id: 'S001',
        name: 'Unsafe Persona',
        summary: 'unsafe',
        style_rules: ['unsafe'],
        few_shot_examples: ['unsafe'],
      },
    })
    expect(result.status).toBe(200)
    expect(result.json).toMatchObject({ persona: { review_status: 'rejected' } })
  })

  test('@v2-smoke S05 load session list', async ({ page }) => {
    await page.route(`${API_BASE}/student/history/sessions?student_id=S001&limit=40&cursor=0`, async (route) => {
      await fulfillJson(route, 200, {
        ok: true,
        sessions: [{ session_id: 'main', preview: 'hello', message_count: 1, updated_at: new Date().toISOString() }],
        next_cursor: 0,
      })
    })

    const result = await callJson(page, '/student/history/sessions?student_id=S001&limit=40&cursor=0')
    expect(result.status).toBe(200)
    expect(result.json).toMatchObject({ ok: true })
  })

  test('@v2-smoke S06 save session view state', async ({ page }) => {
    await page.route(`${API_BASE}/student/session/view-state`, async (route) => {
      await fulfillJson(route, 200, { ok: true })
    })

    const result = await callJson(page, '/student/session/view-state', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: {
        student_id: 'S001',
        active_session_id: 'main',
        sidebar_open: true,
      },
    })
    expect(result.status).toBe(200)
    expect(result.json).toEqual({ ok: true })
  })
})
