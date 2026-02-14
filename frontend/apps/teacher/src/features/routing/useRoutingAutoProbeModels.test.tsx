import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useRoutingAutoProbeModels } from './useRoutingAutoProbeModels'

describe('useRoutingAutoProbeModels', () => {
  it('probes unique configured providers when channels tab is active', async () => {
    const fetchModels = vi.fn(async () => undefined)

    renderHook(() =>
      useRoutingAutoProbeModels({
        activeTab: 'channels',
        providerOverview: {
          providers: [{ provider: 'openai' }, { provider: 'azure' }],
        } as never,
        channels: [
          { target: { provider: 'openai' } },
          { target: { provider: 'openai' } },
          { target: { provider: 'anthropic' } },
        ] as never,
        fetchModels,
      }),
    )

    await waitFor(() => {
      expect(fetchModels).toHaveBeenCalledTimes(1)
      expect(fetchModels).toHaveBeenCalledWith('openai')
    })
  })

  it('does not probe when active tab is not channels', async () => {
    const fetchModels = vi.fn(async () => undefined)

    renderHook(() =>
      useRoutingAutoProbeModels({
        activeTab: 'general',
        providerOverview: {
          providers: [{ provider: 'openai' }],
        } as never,
        channels: [{ target: { provider: 'openai' } }] as never,
        fetchModels,
      }),
    )

    await waitFor(() => {
      expect(fetchModels).not.toHaveBeenCalled()
    })
  })
})
