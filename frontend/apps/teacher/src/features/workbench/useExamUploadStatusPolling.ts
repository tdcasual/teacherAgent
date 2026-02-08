import { useEffect } from 'react'
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
    let timeoutId: number | null = null
    let abortController: AbortController | null = null
    let inFlight = false
    let delayMs = BASE_DELAY_MS
    let lastFingerprint = ''

    const clearTimer = () => {
      if (timeoutId) window.clearTimeout(timeoutId)
      timeoutId = null
    }

    const abortInFlight = () => {
      try {
        abortController?.abort()
      } catch {
        // ignore
      }
      abortController = null
    }

    const scheduleNext = (ms: number) => {
      if (cancelled) return
      clearTimer()
      timeoutId = window.setTimeout(() => void poll(), ms)
    }

    const jitter = (ms: number) => {
      const factor = 0.8 + Math.random() * 0.4
      return Math.round(ms * factor)
    }

    const makeFingerprint = (data: ExamUploadJobStatus) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const extra = data as any
      const updatedAt = extra?.updated_at || extra?.updatedAt || ''
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
      if (cancelled) return
      if (inFlight) return
      if (document.visibilityState === 'hidden') {
        scheduleNext(jitter(Math.min(MAX_DELAY_MS, Math.max(delayMs, 12000))))
        return
      }
      inFlight = true
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
        if (cancelled) return
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

        if (data.status === 'done' || data.status === 'failed' || data.status === 'confirmed') {
          scheduleNext(jitter(Math.min(MAX_DELAY_MS, Math.max(delayMs, 9000))))
        } else {
          scheduleNext(jitter(delayMs))
        }
      } catch (err: any) {
        if (cancelled) return
        if (err?.name === 'AbortError') return
        setExamUploadError(err.message || String(err))
        delayMs = Math.min(MAX_DELAY_MS, Math.round(delayMs * 1.6))
        scheduleNext(jitter(delayMs))
      } finally {
        inFlight = false
      }
    }

    const onVisibilityChange = () => {
      if (cancelled) return
      if (document.visibilityState === 'visible') {
        delayMs = BASE_DELAY_MS
        if (inFlight) return
        scheduleNext(0)
      }
    }
    document.addEventListener('visibilitychange', onVisibilityChange)
    void poll()

    return () => {
      cancelled = true
      document.removeEventListener('visibilitychange', onVisibilityChange)
      clearTimer()
      abortInFlight()
    }
  }, [examJobId, apiBase, examStatusPollNonce, formatExamJobStatus, setExamJobInfo, setExamUploadError, setExamUploadStatus])
}
