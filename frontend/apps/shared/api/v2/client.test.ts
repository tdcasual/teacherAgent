import { describe, expect, it, vi } from 'vitest'

import { ApiV2Error, fetchJsonV2, parseApiError } from './client'

describe('api v2 client', () => {
  it('parses v2 error envelope', () => {
    expect(parseApiError({ error_code: 'AUTH_INVALID_TOKEN', message: 'invalid token' })).toEqual({
      error_code: 'AUTH_INVALID_TOKEN',
      message: 'invalid token',
    })
    expect(parseApiError({ code: 'x' })).toBeNull()
  })

  it('returns json payload when request succeeds', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )

    const out = await fetchJsonV2<{ ok: boolean }>('/api/v2/ping')
    expect(out.ok).toBe(true)
  })

  it('throws ApiV2Error for structured error response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error_code: 'AUTH_INVALID_TOKEN', message: 'invalid token' }), {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )

    await expect(fetchJsonV2('/api/v2/auth/student/login')).rejects.toMatchObject({
      name: 'ApiV2Error',
      code: 'AUTH_INVALID_TOKEN',
      status: 401,
    })
  })
})
