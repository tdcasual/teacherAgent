import { useState } from 'react'
import type { TeacherProviderRegistryOverview } from './routingTypes'

export type RoutingProviderCreateForm = {
  provider_id: string
  display_name: string
  base_url: string
  api_key: string
  default_model: string
  enabled: boolean
}

export type RoutingProviderEditMap = Record<
  string,
  { display_name: string; base_url: string; enabled: boolean; api_key: string; default_model: string }
>

export function useRoutingProviderUiState() {
  const [providerOverview, setProviderOverview] = useState<TeacherProviderRegistryOverview | null>(null)
  const [providerBusy, setProviderBusy] = useState(false)
  const [providerProbeMap, setProviderProbeMap] = useState<Record<string, string>>({})
  const [providerCreateForm, setProviderCreateForm] = useState<RoutingProviderCreateForm>({
    provider_id: '',
    display_name: '',
    base_url: '',
    api_key: '',
    default_model: '',
    enabled: true,
  })
  const [providerEditMap, setProviderEditMap] = useState<RoutingProviderEditMap>({})
  const [providerAddMode, setProviderAddMode] = useState<'' | 'preset' | 'custom'>('')
  const [providerAddPreset, setProviderAddPreset] = useState('')

  return {
    providerOverview,
    setProviderOverview,
    providerBusy,
    setProviderBusy,
    providerProbeMap,
    setProviderProbeMap,
    providerCreateForm,
    setProviderCreateForm,
    providerEditMap,
    setProviderEditMap,
    providerAddMode,
    setProviderAddMode,
    providerAddPreset,
    setProviderAddPreset,
  }
}
