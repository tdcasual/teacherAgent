import { useEffect } from 'react'
import type { RoutingConfig, TeacherProviderRegistryOverview } from './routingTypes'

type Props = {
  activeTab: string
  providerOverview: TeacherProviderRegistryOverview | null
  channels: RoutingConfig['channels']
  fetchModels: (providerId: string) => Promise<unknown>
}

export function useRoutingAutoProbeModels({ activeTab, providerOverview, channels, fetchModels }: Props) {
  useEffect(() => {
    if (activeTab !== 'channels') return
    const configuredProviders = new Set((providerOverview?.providers || []).map((provider) => provider.provider))
    const seen = new Set<string>()
    for (const channel of channels) {
      const provider = channel.target?.provider
      if (provider && !seen.has(provider) && configuredProviders.has(provider)) {
        seen.add(provider)
        void fetchModels(provider)
      }
    }
  }, [activeTab]) // eslint-disable-line react-hooks/exhaustive-deps
}
