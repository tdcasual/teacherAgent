import { describe, expect, it, vi } from 'vitest'

import {
  CHAT_STREAM_EVENT_VERSION,
  runStudentChatStream,
  type StudentChatStreamEvent,
} from './chatStreamClient'

const toSseEvent = (eventId: number, eventType: string, payload: Record<string, unknown>, eventVersion = CHAT_STREAM_EVENT_VERSION): string =>
  `id:${eventId}\nevent:${eventType}\ndata:${JSON.stringify({ type: eventType, event_id: eventId, event_version: eventVersion, payload })}\n\n`

const sseResponse = (body: string): Response => {
  const encoder = new TextEncoder()
  return new Response(
    new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(body))
        controller.close()
      },
    }),
    {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
    },
  )
}

describe('runStudentChatStream', () => {
  it('reconnects with last_event_id and continues stream cursor', async () => {
    const first = [toSseEvent(1, 'assistant.delta', { delta: 'A' })].join('')
    const second = [toSseEvent(2, 'job.done', { reply: 'AB' })].join('')
    const urls: string[] = []
    let calls = 0
    let stop = false
    const events: StudentChatStreamEvent[] = []

    const fetchImpl = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
      urls.push(url)
      calls += 1
      return calls === 1 ? sseResponse(first) : sseResponse(second)
    })

    const result = await runStudentChatStream({
      apiBase: 'http://localhost:8000',
      jobId: 'job-1',
      signal: new AbortController().signal,
      fetchImpl,
      sleep: async () => undefined,
      shouldStop: () => stop,
      onEvent: (event) => {
        events.push(event)
        if (event.eventType === 'job.done') stop = true
      },
    })

    expect(events.map((item) => item.eventType)).toEqual(['assistant.delta', 'job.done'])
    expect(result.cursor).toBe(2)
    expect(urls[0] || '').not.toContain('last_event_id=')
    expect(urls[1] || '').toContain('last_event_id=1')
  })

  it('marks protocol mismatch on unsupported stream version', async () => {
    const unsupported = toSseEvent(1, 'assistant.delta', { delta: 'A' }, CHAT_STREAM_EVENT_VERSION + 1)
    const fetchImpl = vi.fn(async () => sseResponse(unsupported))

    const result = await runStudentChatStream({
      apiBase: 'http://localhost:8000',
      jobId: 'job-2',
      signal: new AbortController().signal,
      fetchImpl,
      sleep: async () => undefined,
      shouldStop: () => false,
      onEvent: () => undefined,
    })

    expect(result.protocolMismatch).toBe(true)
    expect(result.needsFallback).toBe(true)
  })

  it('falls back after reconnect failures reach cap', async () => {
    const fetchImpl = vi.fn(async () => {
      throw new Error('stream unavailable')
    })

    const result = await runStudentChatStream({
      apiBase: 'http://localhost:8000',
      jobId: 'job-3',
      signal: new AbortController().signal,
      fetchImpl,
      sleep: async () => undefined,
      shouldStop: () => false,
      onEvent: () => undefined,
      maxReconnects: 3,
    })

    expect(fetchImpl).toHaveBeenCalledTimes(3)
    expect(result.needsFallback).toBe(true)
    expect(result.protocolMismatch).toBe(false)
  })
})

