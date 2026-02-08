import { useEffect } from 'react'
import { startVisibilityAwareBackoffPolling } from '../../../../shared/visibilityBackoffPolling'
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
    let abortController: AbortController | null = null
    let lastFingerprint = ''

    const abortInFlight = () => {
      try {
        abortController?.abort()
      } catch {
        // ignore
      }
      abortController = null
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
      if (cancelled) return 'stop' as const
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
        if (cancelled) return 'stop' as const
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

        if (['done', 'failed', 'confirmed', 'created'].includes(data.status)) return 'stop' as const

        const fp = makeFingerprint(data)
        const changed = fp !== lastFingerprint
        lastFingerprint = fp

        if (changed) {
          return { action: 'continue', resetDelay: true } as const
        }
        return 'continue' as const
      } catch (err: any) {
        if (cancelled) return 'stop' as const
        if (err?.name === 'AbortError') return 'stop' as const
        throw err
      }
    }

    const cleanup = startVisibilityAwareBackoffPolling(
      poll,
      (err) => {
        if (cancelled) return
        setUploadError((err as Error)?.message || String(err))
      },
      {
        initialDelayMs: BASE_DELAY_MS,
        maxDelayMs: MAX_DELAY_MS,
        normalBackoffFactor: 1.6,
        errorBackoffFactor: 1.6,
        jitterMin: 0.8,
        jitterMax: 1.2,
      },
    )

    return () => {
      cancelled = true
      cleanup()
      abortInFlight()
    }
  }, [uploadJobId, apiBase, uploadStatusPollNonce, formatUploadJobStatus, setUploadError, setUploadJobInfo, setUploadStatus])
}
