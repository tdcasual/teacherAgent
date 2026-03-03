import { isApiErrorV2, type ApiErrorV2 } from './types'

export class ApiV2Error extends Error {
  code: string
  status: number

  constructor(payload: ApiErrorV2, status: number) {
    super(payload.message)
    this.name = 'ApiV2Error'
    this.code = payload.error_code
    this.status = status
  }
}

export const parseApiError = (value: unknown): ApiErrorV2 | null =>
  isApiErrorV2(value) ? value : null

export const normalizeApiBase = (raw: string): string =>
  String(raw || '').trim().replace(/\/+$/, '')

export async function fetchJsonV2<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const res = await fetch(input, init)

  if (!res.ok) {
    let payload: unknown = null
    try {
      payload = await res.json()
    } catch {
      payload = null
    }

    const parsed = parseApiError(payload)
    if (parsed) throw new ApiV2Error(parsed, res.status)
    throw new Error(`request failed with status ${res.status}`)
  }

  return (await res.json()) as T
}
