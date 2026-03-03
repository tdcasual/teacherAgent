export type ApiErrorV2 = {
  error_code: string
  message: string
}

export const isApiErrorV2 = (value: unknown): value is ApiErrorV2 => {
  if (!value || typeof value !== 'object') return false
  const record = value as Record<string, unknown>
  return typeof record.error_code === 'string' && typeof record.message === 'string'
}
