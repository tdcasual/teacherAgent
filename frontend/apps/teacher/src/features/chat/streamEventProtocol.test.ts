import { describe, expect, it } from 'vitest'
import { CHAT_STREAM_EVENT_VERSION, parseChatStreamEnvelope } from './streamEventProtocol'

describe('streamEventProtocol', () => {
  it('parses valid envelope and defaults version', () => {
    const parsed = parseChatStreamEnvelope(
      JSON.stringify({ event_id: 3, type: 'assistant.delta', payload: { delta: 'A' } }),
    )
    expect(parsed).toEqual({
      eventId: 3,
      eventType: 'assistant.delta',
      payload: { delta: 'A' },
      eventVersion: CHAT_STREAM_EVENT_VERSION,
    })
  })

  it('rejects envelopes with invalid fields', () => {
    const parsed = parseChatStreamEnvelope(JSON.stringify({ event_id: 0, type: '', payload: [] }))
    expect(parsed).toBeNull()
  })

  it('keeps explicit version when present', () => {
    const parsed = parseChatStreamEnvelope(
      JSON.stringify({ event_id: 8, type: 'job.done', payload: { reply: 'ok' }, event_version: 1 }),
    )
    expect(parsed?.eventVersion).toBe(1)
  })

  it('accepts envelope when type and event_id are absent', () => {
    const parsed = parseChatStreamEnvelope(
      JSON.stringify({ payload: { delta: 'A' }, event_version: CHAT_STREAM_EVENT_VERSION }),
    )
    expect(parsed).toEqual({
      eventId: undefined,
      eventType: undefined,
      payload: { delta: 'A' },
      eventVersion: CHAT_STREAM_EVENT_VERSION,
    })
  })

  it('rejects envelopes with invalid version', () => {
    const parsed = parseChatStreamEnvelope(
      JSON.stringify({ event_id: 9, type: 'assistant.delta', payload: { delta: 'A' }, event_version: -2 }),
    )
    expect(parsed).toBeNull()
  })
})
