import { act, renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { useRoutingProviderUiState } from './useRoutingProviderUiState'

describe('useRoutingProviderUiState', () => {
  it('provides provider panel default state', () => {
    const { result } = renderHook(() => useRoutingProviderUiState())

    expect(result.current.providerOverview).toBeNull()
    expect(result.current.providerBusy).toBe(false)
    expect(result.current.providerProbeMap).toEqual({})
    expect(result.current.providerAddMode).toBe('')
    expect(result.current.providerAddPreset).toBe('')
    expect(result.current.providerCreateForm).toEqual({
      provider_id: '',
      display_name: '',
      base_url: '',
      api_key: '',
      default_model: '',
      enabled: true,
    })
    expect(result.current.providerEditMap).toEqual({})
  })

  it('allows updating provider draft state', () => {
    const { result } = renderHook(() => useRoutingProviderUiState())

    act(() => {
      result.current.setProviderAddMode('custom')
      result.current.setProviderAddPreset('openai')
      result.current.setProviderCreateForm((prev) => ({ ...prev, provider_id: 'openai', display_name: 'OpenAI' }))
    })

    expect(result.current.providerAddMode).toBe('custom')
    expect(result.current.providerAddPreset).toBe('openai')
    expect(result.current.providerCreateForm.provider_id).toBe('openai')
    expect(result.current.providerCreateForm.display_name).toBe('OpenAI')
  })
})
