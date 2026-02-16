import type { PendingChatJob } from '../../appTypes'

export const parsePendingChatJob = (raw: string | null): PendingChatJob | null => {
  if (!raw) return null
  try {
    const parsed: unknown = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return null
    const record = parsed as Record<string, unknown>
    const jobId = String(record.job_id || '').trim()
    const requestId = String(record.request_id || '').trim()
    const placeholderId = String(record.placeholder_id || '').trim()
    const userText = String(record.user_text || '').trim()
    const sessionId = String(record.session_id || '').trim()
    const createdAt = Number(record.created_at)
    if (!jobId || !requestId || !placeholderId || !userText || !sessionId) return null
    if (!Number.isFinite(createdAt)) return null
    const laneId = String(record.lane_id || '').trim()
    return {
      job_id: jobId,
      request_id: requestId,
      placeholder_id: placeholderId,
      user_text: userText,
      session_id: sessionId,
      created_at: createdAt,
      ...(laneId ? { lane_id: laneId } : {}),
    }
  } catch {
    return null
  }
}
