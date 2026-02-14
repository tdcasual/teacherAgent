import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { probeProviderRegistryModels } from './routingApi'
import { useProviderModels } from './useProviderModels'

vi.mock('./routingApi', () => ({
  probeProviderRegistryModels: vi.fn(),
}))

const probeProviderRegistryModelsMock = vi.mocked(probeProviderRegistryModels)

describe('useProviderModels', () => {
  it('keeps fetchModels callback stable across state updates', async () => {
    probeProviderRegistryModelsMock.mockResolvedValue({ ok: true, models: ['gpt-4.1-mini'] })

    const { result } = renderHook(() => useProviderModels('http://localhost:8000', 'teacher-1'))
    const firstFetchModels = result.current.fetchModels

    await act(async () => {
      await result.current.fetchModels('openai')
    })

    await waitFor(() => {
      expect(result.current.modelsMap.openai?.models).toEqual(['gpt-4.1-mini'])
    })

    expect(result.current.fetchModels).toBe(firstFetchModels)
  })

  it('skips probe request when cache is still fresh', async () => {
    probeProviderRegistryModelsMock.mockResolvedValue({ ok: true, models: ['gpt-4.1-mini'] })

    const { result } = renderHook(() => useProviderModels('http://localhost:8000', 'teacher-1'))

    await act(async () => {
      await result.current.fetchModels('openai')
    })
    await act(async () => {
      await result.current.fetchModels('openai')
    })

    expect(probeProviderRegistryModelsMock).toHaveBeenCalledTimes(1)
  })
})
