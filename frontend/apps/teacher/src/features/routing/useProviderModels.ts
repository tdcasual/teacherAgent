import { useCallback, useState } from 'react'
import { probeProviderRegistryModels } from './routingApi'

type ProviderModelsEntry = {
  models: string[]
  loading: boolean
  error: string
  fetchedAt: number
}

export function useProviderModels(apiBase: string, teacherId: string) {
  const [map, setMap] = useState<Record<string, ProviderModelsEntry>>({})

  const fetchModels = useCallback(
    async (providerId: string) => {
      setMap((prev) => {
        const existing = prev[providerId]
        // 5-minute cache: skip if data exists and is fresh
        if (existing && !existing.error && Date.now() - existing.fetchedAt < 300_000) return prev
        return { ...prev, [providerId]: { models: existing?.models || [], loading: true, error: '', fetchedAt: existing?.fetchedAt || 0 } }
      })
      // Check cache outside setState to decide whether to actually fetch
      const cached = map[providerId]
      if (cached && !cached.error && Date.now() - cached.fetchedAt < 300_000) return
      try {
        const result = await probeProviderRegistryModels(apiBase, providerId, { teacher_id: teacherId || undefined })
        setMap((prev) => ({
          ...prev,
          [providerId]: { models: result.models || [], loading: false, error: '', fetchedAt: Date.now() },
        }))
      } catch (err) {
        setMap((prev) => ({
          ...prev,
          [providerId]: { models: prev[providerId]?.models || [], loading: false, error: (err as Error).message, fetchedAt: Date.now() },
        }))
      }
    },
    [apiBase, teacherId, map],
  )

  return { modelsMap: map, fetchModels }
}
