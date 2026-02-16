export const CHAT_STREAM_EVENT_VERSION = 1

export type ChatStreamEnvelope = {
  eventId?: number
  eventVersion: number
  eventType?: string
  payload: Record<string, unknown>
}

export const parseChatStreamEnvelope = (rawData: string): ChatStreamEnvelope | null => {
  let parsed: unknown
  try {
    parsed = JSON.parse(rawData)
  } catch {
    return null
  }
  if (!parsed || typeof parsed !== 'object') return null
  const record = parsed as Record<string, unknown>
  const hasEventId = record.event_id != null
  const eventIdRaw = hasEventId ? Number(record.event_id) : NaN
  const eventType = String(record.type || '').trim()
  const payloadRaw = record.payload
  const eventVersionRaw = record.event_version
  const eventVersion = eventVersionRaw == null
    ? CHAT_STREAM_EVENT_VERSION
    : Number(eventVersionRaw)
  if (hasEventId && (!Number.isFinite(eventIdRaw) || eventIdRaw <= 0)) return null
  if (!Number.isFinite(eventVersion) || eventVersion <= 0) return null
  const payload = payloadRaw && typeof payloadRaw === 'object'
    ? payloadRaw as Record<string, unknown>
    : {}
  return {
    eventId: hasEventId ? Math.trunc(eventIdRaw) : undefined,
    eventVersion: Math.trunc(eventVersion),
    eventType: eventType || undefined,
    payload,
  }
}
