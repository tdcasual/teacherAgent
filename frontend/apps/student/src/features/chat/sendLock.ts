import { safeLocalStorageGetItem, safeLocalStorageRemoveItem, safeLocalStorageSetItem } from '../../../../shared/storage'

const SEND_LOCK_KEY_PREFIX = 'studentSendLock:'
const FALLBACK_SEND_LOCK_TTL_MS = 5000
const FALLBACK_SEND_LOCK_SETTLE_MS = 120
const FALLBACK_SEND_LOCK_RENEW_INTERVAL_MS = 1000

type FallbackLockPayload = {
  owner: string
  expires_at: number
}

const parseFallbackLock = (raw: string | null): FallbackLockPayload | null => {
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as { owner?: string; expires_at?: number }
    const parsedOwner = String(parsed?.owner || '').trim()
    const parsedExpiresAt = Number(parsed?.expires_at || 0)
    if (!parsedOwner || !Number.isFinite(parsedExpiresAt)) return null
    return { owner: parsedOwner, expires_at: parsedExpiresAt }
  } catch {
    return null
  }
}

export async function withStudentSendLock(studentId: string, task: () => Promise<void>) {
  const sid = String(studentId || '').trim()
  if (!sid) return false
  const lockManager = typeof navigator !== 'undefined' ? (navigator as any).locks : null
  if (lockManager?.request) {
    const acquired = await lockManager.request(
      `student-send-lock:${sid}`,
      { ifAvailable: true, mode: 'exclusive' },
      async (lock: any) => {
        if (!lock) return false
        await task()
        return true
      },
    )
    return Boolean(acquired)
  }

  if (typeof window === 'undefined') return false

  const lockKey = `${SEND_LOCK_KEY_PREFIX}${sid}`
  const owner = `slock_${Date.now()}_${Math.random().toString(16).slice(2)}`

  const now = Date.now()
  const existing = parseFallbackLock(safeLocalStorageGetItem(lockKey))
  if (existing && existing.expires_at > now) {
    return false
  }
  if (existing && existing.expires_at <= now) {
    safeLocalStorageRemoveItem(lockKey)
  }

  const wrote = safeLocalStorageSetItem(
    lockKey,
    JSON.stringify({
      owner,
      expires_at: now + FALLBACK_SEND_LOCK_TTL_MS,
    }),
  )
  if (!wrote) return false

  const settleStartedAt = Date.now()
  while (Date.now() - settleStartedAt < FALLBACK_SEND_LOCK_SETTLE_MS) {
    await new Promise((resolve) => window.setTimeout(resolve, 24))
    const observed = parseFallbackLock(safeLocalStorageGetItem(lockKey))
    if (!observed || observed.owner !== owner || observed.expires_at <= Date.now()) {
      return false
    }
  }

  const latest = parseFallbackLock(safeLocalStorageGetItem(lockKey))
  if (!latest || latest.owner !== owner || latest.expires_at <= Date.now()) {
    return false
  }

  const extendFallbackLock = () => {
    const current = parseFallbackLock(safeLocalStorageGetItem(lockKey))
    if (!current || current.owner !== owner) return false
    const renewed = safeLocalStorageSetItem(
      lockKey,
      JSON.stringify({
        owner,
        expires_at: Date.now() + FALLBACK_SEND_LOCK_TTL_MS,
      }),
    )
    if (!renewed) return false
    const observed = parseFallbackLock(safeLocalStorageGetItem(lockKey))
    return Boolean(observed && observed.owner === owner && observed.expires_at > Date.now())
  }

  if (!extendFallbackLock()) {
    return false
  }

  let renewTimer: number | null = window.setInterval(() => {
    if (extendFallbackLock()) return
    if (renewTimer !== null) {
      window.clearInterval(renewTimer)
      renewTimer = null
    }
  }, FALLBACK_SEND_LOCK_RENEW_INTERVAL_MS)

  try {
    await task()
    return true
  } finally {
    if (renewTimer !== null) {
      window.clearInterval(renewTimer)
      renewTimer = null
    }
    const current = parseFallbackLock(safeLocalStorageGetItem(lockKey))
    if (current?.owner === owner) {
      safeLocalStorageRemoveItem(lockKey)
    }
  }
}
