export type VisibilityBackoffPollingOptions = {
  initialDelayMs?: number
  maxDelayMs?: number
  normalBackoffFactor?: number
  errorBackoffFactor?: number
  jitterMin?: number
  jitterMax?: number
  kickMode?: 'direct' | 'timeout0'
}

export function startVisibilityAwareBackoffPolling(
  poll: () => Promise<'continue' | 'stop'>,
  onError: (err: unknown) => void,
  options: VisibilityBackoffPollingOptions = {},
): () => void {
  const {
    initialDelayMs = 800,
    maxDelayMs = 8000,
    normalBackoffFactor = 1.4,
    errorBackoffFactor = 1.6,
    jitterMin = 0.85,
    jitterMax = 1.15,
    kickMode = 'timeout0',
  } = options

  let cancelled = false
  let timeoutId: number | null = null
  let inFlight = false
  let delayMs = initialDelayMs

  const clearTimer = () => {
    if (timeoutId != null) window.clearTimeout(timeoutId)
    timeoutId = null
  }

  const jitter = (ms: number) => Math.round(ms * (jitterMin + Math.random() * (jitterMax - jitterMin)))

  const schedule = (ms: number) => {
    clearTimer()
    timeoutId = window.setTimeout(() => {
      void run()
    }, ms)
  }

  const scheduleHidden = () => {
    schedule(jitter(Math.min(maxDelayMs, delayMs)))
  }

  const kick = () => {
    clearTimer()
    if (kickMode === 'direct') {
      void run()
      return
    }
    schedule(0)
  }

  const run = async () => {
    if (cancelled || inFlight) return
    if (typeof document !== 'undefined' && document.visibilityState === 'hidden') {
      scheduleHidden()
      return
    }
    inFlight = true
    try {
      const outcome = await poll()
      if (cancelled) return
      if (outcome === 'stop') return
      delayMs = Math.min(maxDelayMs, Math.round(delayMs * normalBackoffFactor))
      schedule(jitter(delayMs))
    } catch (err) {
      if (cancelled) return
      onError(err)
      delayMs = Math.min(maxDelayMs, Math.round(delayMs * errorBackoffFactor))
      schedule(jitter(delayMs))
    } finally {
      inFlight = false
    }
  }

  const onVisibilityChange = () => {
    if (cancelled) return
    if (typeof document === 'undefined') return
    if (document.visibilityState !== 'visible') return
    delayMs = initialDelayMs
    kick()
  }

  document.addEventListener('visibilitychange', onVisibilityChange)
  kick()

  return () => {
    cancelled = true
    document.removeEventListener('visibilitychange', onVisibilityChange)
    clearTimer()
  }
}

