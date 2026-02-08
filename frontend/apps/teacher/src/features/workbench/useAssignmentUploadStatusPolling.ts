import { useEffect } from 'react'
import { safeLocalStorageGetItem, safeLocalStorageRemoveItem } from '../../utils/storage'
import type { UploadJobStatus } from '../../appTypes'

type Params = {
  apiBase: string
  uploadJobId: string
  uploadStatusPollNonce: number
  formatUploadJobStatus: (value: UploadJobStatus) => string
  setUploadError: (value: string) => void
  setUploadJobInfo: (
    value:
      | UploadJobStatus
      | null
      | ((prev: UploadJobStatus | null) => UploadJobStatus | null),
  ) => void
  setUploadStatus: (value: string) => void
}

export function useAssignmentUploadStatusPolling({
  apiBase,
  uploadJobId,
  uploadStatusPollNonce,
  formatUploadJobStatus,
  setUploadError,
  setUploadJobInfo,
  setUploadStatus,
}: Params) {
  useEffect(() => {
    if (!uploadJobId) return
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
      // +/- 20%
      const factor = 0.8 + Math.random() * 0.4
      return Math.round(ms * factor)
    }

    const makeFingerprint = (data: UploadJobStatus) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const extra = data as any
      const updatedAt = extra?.updated_at || extra?.updatedAt || ''
      const missing = Array.isArray(data.requirements_missing) ? data.requirements_missing.join(',') : ''
      const warnings = Array.isArray(data.warnings) ? data.warnings.length : 0
      return [
        data.status,
        data.progress ?? '',
        data.step ?? '',
        data.message ?? '',
        data.assignment_id ?? '',
        data.question_count ?? '',
        missing,
        warnings,
        updatedAt,
        data.error ?? '',
      ].join('|')
    }

    const clearActiveUpload = () => {
      try {
        const raw = safeLocalStorageGetItem('teacherActiveUpload')
        if (!raw) return
        const active = JSON.parse(raw)
        if (active?.type === 'assignment' && active?.job_id === uploadJobId) safeLocalStorageRemoveItem('teacherActiveUpload')
      } catch {
        // ignore
      }
    }

    const poll = async () => {
      if (cancelled) return
      if (inFlight) return
      // If tab is hidden, don't keep polling aggressively.
      if (document.visibilityState === 'hidden') {
        scheduleNext(jitter(Math.min(MAX_DELAY_MS, delayMs)))
        return
      }

      inFlight = true
      abortInFlight()
      abortController = new AbortController()
      try {
        const res = await fetch(`${apiBase}/assignment/upload/status?job_id=${encodeURIComponent(uploadJobId)}`, {
          signal: abortController.signal,
        })
        if (!res.ok) {
          const text = await res.text()
          throw new Error(text || `状态码 ${res.status}`)
        }
        const data = (await res.json()) as UploadJobStatus
        if (cancelled) return
        setUploadError('')
        setUploadJobInfo((prev: UploadJobStatus | null) => {
          if (prev && prev.job_id === data.job_id) {
            if ((prev.status === 'confirming' || prev.status === 'confirmed' || prev.status === 'created') && data.status === 'done') {
              setUploadStatus(formatUploadJobStatus(prev))
              return prev
            }
          }
          setUploadStatus(formatUploadJobStatus(data))
          return data
        })

        if (data.status === 'failed' || data.status === 'confirmed' || data.status === 'created') clearActiveUpload()

        // Stop polling once parsing is finished (done/failed) or assignment is confirmed/created.
        if (['done', 'failed', 'confirmed', 'created'].includes(data.status)) return

        const fp = makeFingerprint(data)
        const changed = fp !== lastFingerprint
        lastFingerprint = fp

        if (changed) delayMs = BASE_DELAY_MS
        else delayMs = Math.min(MAX_DELAY_MS, Math.round(delayMs * 1.6))

        scheduleNext(jitter(delayMs))
      } catch (err: any) {
        if (cancelled) return
        if (err?.name === 'AbortError') return
        setUploadError(err.message || String(err))
        // Network/temporary errors: keep polling with backoff (up to cap).
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
  }, [uploadJobId, apiBase, uploadStatusPollNonce, formatUploadJobStatus, setUploadError, setUploadJobInfo, setUploadStatus])
}
