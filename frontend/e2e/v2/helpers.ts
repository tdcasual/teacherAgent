import type { Page, Route } from '@playwright/test'

export const API_BASE = 'http://localhost:8000'

export type JsonCallResult = {
  status: number
  text: string
  json: unknown
}

export const fulfillJson = async (route: Route, status: number, payload: unknown) => {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  })
}

export const callJson = async (
  page: Page,
  path: string,
  options?: {
    method?: string
    headers?: Record<string, string>
    body?: unknown
  },
): Promise<JsonCallResult> =>
  page.evaluate(
    async ({ url, method, headers, body }) => {
      const init: RequestInit = {
        method,
        headers,
      }
      if (body !== undefined) {
        if (typeof body === 'string') init.body = body
        else init.body = JSON.stringify(body)
      }

      const res = await fetch(url, init)
      const text = await res.text()
      let json: unknown = null
      try {
        json = text ? JSON.parse(text) : null
      } catch {
        json = null
      }
      return {
        status: res.status,
        text,
        json,
      }
    },
    {
      url: `${API_BASE}${path}`,
      method: options?.method || 'GET',
      headers: options?.headers || {},
      body: options?.body,
    },
  )

export const callText = async (
  page: Page,
  path: string,
  options?: {
    method?: string
    headers?: Record<string, string>
    body?: unknown
  },
): Promise<{ status: number; text: string }> =>
  page.evaluate(
    async ({ url, method, headers, body }) => {
      const init: RequestInit = {
        method,
        headers,
      }
      if (body !== undefined) {
        if (typeof body === 'string') init.body = body
        else init.body = JSON.stringify(body)
      }
      const res = await fetch(url, init)
      return {
        status: res.status,
        text: await res.text(),
      }
    },
    {
      url: `${API_BASE}${path}`,
      method: options?.method || 'GET',
      headers: options?.headers || {},
      body: options?.body,
    },
  )
