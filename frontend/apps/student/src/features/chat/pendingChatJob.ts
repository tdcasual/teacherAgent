import type { PendingChatJob } from '../../appTypes'

export const PENDING_CHAT_MAX_AGE_MS = 15 * 60 * 1000

export const normalizePendingChatJob = (
  value: unknown,
  nowMs: number = Date.now(),
): PendingChatJob | null => {
  if (!value || typeof value !== 'object') return null
  const candidate = value as Partial<PendingChatJob>
  const jobId = String(candidate.job_id || '').trim()
  if (!jobId) return null
  const createdAt = Number(candidate.created_at || 0)
  if (!Number.isFinite(createdAt) || createdAt <= 0) return null
  if (nowMs - createdAt > PENDING_CHAT_MAX_AGE_MS) return null

  const requestId = String(candidate.request_id || '').trim()
  const placeholderId = String(candidate.placeholder_id || '').trim() || `asst_recover_${jobId}`
  const userText = typeof candidate.user_text === 'string' ? candidate.user_text : ''
  const sessionId = String(candidate.session_id || '').trim()

  return {
    job_id: jobId,
    request_id: requestId,
    placeholder_id: placeholderId,
    user_text: userText,
    session_id: sessionId,
    created_at: createdAt,
  }
}

export const parsePendingChatJobFromStorage = (
  raw: string | null,
  nowMs: number = Date.now(),
): PendingChatJob | null => {
  if (!raw) return null
  try {
    return normalizePendingChatJob(JSON.parse(raw), nowMs)
  } catch {
    return null
  }
}
