import { useEffect } from 'react'
import { startVisibilityAwareBackoffPolling } from '../../../../shared/visibilityBackoffPolling'
import { toUserFacingErrorMessage } from '../../../../shared/errorMessage'
import { safeLocalStorageGetItem, safeLocalStorageRemoveItem } from '../../utils/storage'
import type { ExamUploadJobStatus } from '../../appTypes'

type Params = {
  apiBase: string
  examJobId: string
  examStatusPollNonce: number
  formatExamJobStatus: (value: ExamUploadJobStatus) => string
  setExamJobInfo: (
    value:
      | ExamUploadJobStatus
      | null
      | ((prev: ExamUploadJobStatus | null) => ExamUploadJobStatus | null),
  ) => void
  setExamUploadError: (value: string) => void
  setExamUploadStatus: (value: string) => void
}

const isAbortError = (error: unknown): boolean => {
  if (error instanceof DOMException) return error.name === 'AbortError'
  if (!error || typeof error !== 'object') return false
  return (error as { name?: unknown }).name === 'AbortError'
}

const toErrorMessage = (error: unknown, fallback = '请求失败') => {
  return toUserFacingErrorMessage(error, fallback)
}

export function useExamUploadStatusPolling({
  apiBase,
  examJobId,
  examStatusPollNonce,
  formatExamJobStatus,
  setExamJobInfo,
  setExamUploadError,
  setExamUploadStatus,
}: Params) {
  useEffect(() => {
    if (!examJobId) return
    const BASE_DELAY_MS = 4000
    const MAX_DELAY_MS = 30000

    let cancelled = false
    let abortController: AbortController | null = null
    let delayMs = BASE_DELAY_MS
    let lastFingerprint = ''

    const abortInFlight = () => {
      try {
        abortController?.abort()
      } catch {
        // ignore
      }
      abortController = null
    }

    const makeFingerprint = (data: ExamUploadJobStatus) => {
      const updatedAt = data.updated_at || data.updatedAt || ''
      const counts = data.counts ? JSON.stringify(data.counts) : ''
      const warnings = Array.isArray(data.warnings) ? data.warnings.length : 0
      return [data.status, data.progress ?? '', data.step ?? '', data.exam_id ?? '', counts, warnings, updatedAt, data.error ?? ''].join('|')
    }

    const clearActiveUpload = () => {
      try {
        const raw = safeLocalStorageGetItem('teacherActiveUpload')
        if (!raw) return
        const active = JSON.parse(raw)
        if (active?.type === 'exam' && active?.job_id === examJobId) safeLocalStorageRemoveItem('teacherActiveUpload')
      } catch {
        // ignore
      }
    }

    const poll = async () => {
      if (cancelled) return 'stop' as const
      abortInFlight()
      abortController = new AbortController()
      try {
        const res = await fetch(`${apiBase}/exam/upload/status?job_id=${encodeURIComponent(examJobId)}`, {
          signal: abortController.signal,
          headers: { Accept: 'application/json' },
        })
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `状态码 ${res.status}`)
        }
        const data = (await res.json()) as ExamUploadJobStatus
        if (cancelled) return 'stop' as const
        setExamJobInfo((prev: ExamUploadJobStatus | null) => {
          if (prev && prev.job_id === data.job_id) {
            if ((prev.status === 'confirming' || prev.status === 'confirmed') && data.status === 'done') {
              setExamUploadStatus(formatExamJobStatus(prev))
              return prev
            }
          }
          setExamUploadStatus(formatExamJobStatus(data))
          return data
        })
        if (data.status === 'failed') {
          setExamUploadError(formatExamJobStatus(data))
          clearActiveUpload()
        }
        if (data.status === 'confirmed') {
          clearActiveUpload()
        }

        const fingerprint = makeFingerprint(data)
        if (fingerprint !== lastFingerprint) {
          lastFingerprint = fingerprint
          delayMs = BASE_DELAY_MS
        } else {
          delayMs = Math.min(MAX_DELAY_MS, Math.round(delayMs * 1.25))
        }

        const nextDelay =
          data.status === 'done' || data.status === 'failed' || data.status === 'confirmed'
            ? Math.min(MAX_DELAY_MS, Math.max(delayMs, 9000))
            : delayMs
        return { action: 'continue', nextDelayMs: nextDelay } as const
      } catch (err: unknown) {
        if (cancelled) return 'stop' as const
        if (isAbortError(err)) return 'stop' as const
        setExamUploadError(toErrorMessage(err))
        delayMs = Math.min(MAX_DELAY_MS, Math.round(delayMs * 1.6))
        return { action: 'continue', nextDelayMs: delayMs } as const
      }
    }

    const cleanup = startVisibilityAwareBackoffPolling(
      poll,
      () => {},
      {
        initialDelayMs: BASE_DELAY_MS,
        maxDelayMs: MAX_DELAY_MS,
        normalBackoffFactor: 1.25,
        errorBackoffFactor: 1.6,
        jitterMin: 0.8,
        jitterMax: 1.2,
        hiddenMinDelayMs: 12000,
      },
    )

    return () => {
      cancelled = true
      cleanup()
      abortInFlight()
    }
  }, [examJobId, apiBase, examStatusPollNonce, formatExamJobStatus, setExamJobInfo, setExamUploadError, setExamUploadStatus])
}
