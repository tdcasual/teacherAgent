export type VisibilityBackoffPollingOptions = {
  initialDelayMs?: number;
  maxDelayMs?: number;
  normalBackoffFactor?: number;
  errorBackoffFactor?: number;
  jitterMin?: number;
  jitterMax?: number;
  hiddenMinDelayMs?: number;
  pollTimeoutMs?: number;
  inFlightTimeoutMs?: number;
  kickMode?: 'direct' | 'timeout0';
};

export type VisibilityBackoffPollContext = {
  signal: AbortSignal;
  pollTimeoutMs: number;
};

export type VisibilityBackoffPollOutcome =
  | 'continue'
  | 'stop'
  | {
      action: 'continue';
      resetDelay?: boolean;
      nextDelayMs?: number;
    };

export function startVisibilityAwareBackoffPolling(
  poll: (ctx: VisibilityBackoffPollContext) => Promise<VisibilityBackoffPollOutcome>,
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
    hiddenMinDelayMs,
    pollTimeoutMs = 15000,
    inFlightTimeoutMs = 20000,
    kickMode = 'timeout0',
  } = options;

  let cancelled = false;
  let timeoutId: number | null = null;
  let inFlight = false;
  let inFlightStartedAt = 0;
  let abortController: AbortController | null = null;
  let delayMs = initialDelayMs;

  const clearTimer = () => {
    if (timeoutId != null) window.clearTimeout(timeoutId);
    timeoutId = null;
  };

  const abortInFlight = () => {
    try {
      abortController?.abort();
    } catch {
      // ignore abort errors
    }
    abortController = null;
  };

  const jitter = (ms: number) =>
    Math.round(ms * (jitterMin + Math.random() * (jitterMax - jitterMin)));

  const schedule = (ms: number) => {
    clearTimer();
    timeoutId = window.setTimeout(() => {
      void run();
    }, ms);
  };

  const scheduleHidden = () => {
    const hiddenMin = typeof hiddenMinDelayMs === 'number' ? hiddenMinDelayMs : 0;
    schedule(jitter(Math.min(maxDelayMs, Math.max(delayMs, hiddenMin))));
  };

  const kick = () => {
    clearTimer();
    if (kickMode === 'direct') {
      void run();
      return;
    }
    schedule(0);
  };

  const run = async () => {
    if (cancelled) return;
    if (inFlight) {
      const inflightAge = Date.now() - inFlightStartedAt;
      if (inFlightTimeoutMs > 0 && inFlightStartedAt > 0 && inflightAge > inFlightTimeoutMs) {
        abortInFlight();
        inFlight = false;
        inFlightStartedAt = 0;
      } else {
        return;
      }
    }
    if (typeof document !== 'undefined' && document.visibilityState === 'hidden') {
      scheduleHidden();
      return;
    }
    inFlight = true;
    inFlightStartedAt = Date.now();
    abortInFlight();
    abortController = new AbortController();
    let pollTimeoutId: number | null = null;
    if (pollTimeoutMs > 0) {
      pollTimeoutId = window.setTimeout(() => {
        abortInFlight();
      }, pollTimeoutMs);
    }
    try {
      const outcome = await poll({ signal: abortController.signal, pollTimeoutMs });
      if (cancelled) return;
      if (outcome === 'stop') return;
      if (typeof outcome === 'object' && outcome.action === 'continue') {
        if (typeof outcome.nextDelayMs === 'number') {
          delayMs = Math.min(maxDelayMs, Math.round(outcome.nextDelayMs));
          schedule(jitter(delayMs));
          return;
        }
        if (outcome.resetDelay) {
          delayMs = initialDelayMs;
          schedule(jitter(delayMs));
          return;
        }
      }
      delayMs = Math.min(maxDelayMs, Math.round(delayMs * normalBackoffFactor));
      schedule(jitter(delayMs));
    } catch (err) {
      if (cancelled) return;
      onError(err);
      delayMs = Math.min(maxDelayMs, Math.round(delayMs * errorBackoffFactor));
      schedule(jitter(delayMs));
    } finally {
      if (pollTimeoutId != null) window.clearTimeout(pollTimeoutId);
      abortController = null;
      inFlight = false;
      inFlightStartedAt = 0;
    }
  };

  const onVisibilityChange = () => {
    if (cancelled) return;
    if (typeof document === 'undefined') return;
    if (document.visibilityState !== 'visible') return;
    delayMs = initialDelayMs;
    kick();
  };

  document.addEventListener('visibilitychange', onVisibilityChange);
  kick();

  return () => {
    cancelled = true;
    document.removeEventListener('visibilitychange', onVisibilityChange);
    clearTimer();
    abortInFlight();
  };
}
