export const CHAT_STREAM_EVENT_VERSION = 1

type ChatStreamEnvelope = {
  eventId?: number
  eventVersion: number
  eventType?: string
  payload: Record<string, unknown>
}

export type StudentChatStreamEvent = {
  eventType: string
  eventId: number
  payload: Record<string, unknown>
}

export type StudentChatStreamResult = {
  cursor: number
  protocolMismatch: boolean
  needsFallback: boolean
}

type RunStudentChatStreamParams = {
  apiBase: string
  jobId: string
  signal: AbortSignal
  onEvent: (event: StudentChatStreamEvent) => void
  shouldStop: () => boolean
  initialCursor?: number
  maxReconnects?: number
  fetchImpl?: typeof fetch
  sleep?: (ms: number) => Promise<void>
}

const parseChatStreamEnvelope = (rawData: string): ChatStreamEnvelope | null => {
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
  const eventVersion = eventVersionRaw == null ? CHAT_STREAM_EVENT_VERSION : Number(eventVersionRaw)
  if (hasEventId && (!Number.isFinite(eventIdRaw) || eventIdRaw <= 0)) return null
  if (!Number.isFinite(eventVersion) || eventVersion <= 0) return null
  const payload = payloadRaw && typeof payloadRaw === 'object' ? (payloadRaw as Record<string, unknown>) : {}
  return {
    eventId: hasEventId ? Math.trunc(eventIdRaw) : undefined,
    eventVersion: Math.trunc(eventVersion),
    eventType: eventType || undefined,
    payload,
  }
}

export const runStudentChatStream = async ({
  apiBase,
  jobId,
  signal,
  onEvent,
  shouldStop,
  initialCursor = 0,
  maxReconnects = 4,
  fetchImpl = fetch,
  sleep = async (ms: number) =>
    await new Promise<void>((resolve) => {
      window.setTimeout(resolve, ms)
    }),
}: RunStudentChatStreamParams): Promise<StudentChatStreamResult> => {
  let cursor = Math.max(0, Number(initialCursor) || 0)
  let reconnectAttempts = 0
  const reconnectCap = Math.max(1, Number(maxReconnects) || 4)
  const noEventReconnectCap = Math.min(2, reconnectCap)

  while (!signal.aborted && !shouldStop()) {
    try {
      const url = new URL(`${apiBase}/chat/stream`)
      url.searchParams.set('job_id', jobId)
      if (cursor > 0) url.searchParams.set('last_event_id', String(cursor))
      const res = await fetchImpl(url.toString(), {
        signal,
        headers: { Accept: 'text/event-stream' },
      })
      if (!res.ok || !res.body) {
        const text = await res.text()
        throw new Error(text || `状态码 ${res.status}`)
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''
      let sawEventInCurrentStream = false

      while (!signal.aborted && !shouldStop()) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const normalized = buffer.replace(/\r/g, '')
        const parts = normalized.split('\n\n')
        buffer = parts.pop() || ''
        for (const raw of parts) {
          const block = raw.trim()
          if (!block || block.startsWith(':')) continue
          let eventType = ''
          let eventId = 0
          const dataLines: string[] = []
          for (const line of block.split('\n')) {
            if (line.startsWith('event:')) {
              eventType = line.slice(6).trim()
            } else if (line.startsWith('id:')) {
              const parsed = Number(line.slice(3).trim())
              if (Number.isFinite(parsed) && parsed > 0) eventId = parsed
            } else if (line.startsWith('data:')) {
              dataLines.push(line.slice(5).trim())
            }
          }
          if (!dataLines.length) continue
          const envelope = parseChatStreamEnvelope(dataLines.join('\n'))
          if (!envelope) continue
          if (envelope.eventVersion !== CHAT_STREAM_EVENT_VERSION) {
            return { cursor, protocolMismatch: true, needsFallback: true }
          }
          const finalType = String(eventType || envelope.eventType || '').trim()
          if (!finalType) continue
          const finalEventId = Number(envelope.eventId ?? eventId ?? 0)
          if (!Number.isFinite(finalEventId) || finalEventId <= cursor) continue
          sawEventInCurrentStream = true
          cursor = finalEventId
          onEvent({
            eventType: finalType,
            eventId: finalEventId,
            payload: envelope.payload,
          })
          if (shouldStop()) break
        }
      }

      if (signal.aborted || shouldStop()) {
        return { cursor, protocolMismatch: false, needsFallback: false }
      }
      if (sawEventInCurrentStream) reconnectAttempts = 0
      reconnectAttempts += 1
      const usingNoEventCap = cursor <= initialCursor
      const activeReconnectCap = usingNoEventCap ? noEventReconnectCap : reconnectCap
      if (reconnectAttempts >= activeReconnectCap) {
        return { cursor, protocolMismatch: false, needsFallback: true }
      }
      const backoffMs = usingNoEventCap
        ? Math.min(1000, reconnectAttempts * 300)
        : Math.min(3000, reconnectAttempts * 800)
      await sleep(backoffMs)
    } catch {
      if (signal.aborted || shouldStop()) {
        return { cursor, protocolMismatch: false, needsFallback: false }
      }
      reconnectAttempts += 1
      const usingNoEventCap = cursor <= initialCursor
      const activeReconnectCap = usingNoEventCap ? noEventReconnectCap : reconnectCap
      if (reconnectAttempts >= activeReconnectCap) {
        return { cursor, protocolMismatch: false, needsFallback: true }
      }
      const backoffMs = usingNoEventCap
        ? Math.min(1000, reconnectAttempts * 300)
        : Math.min(3000, reconnectAttempts * 800)
      await sleep(backoffMs)
    }
  }

  return { cursor, protocolMismatch: false, needsFallback: false }
}
