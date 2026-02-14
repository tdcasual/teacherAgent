import { useCallback, useRef, useState } from 'react'
import { probeProviderRegistryModels } from './routingApi'

type ProviderModelsEntry = {
  models: string[]
  loading: boolean
  error: string
  fetchedAt: number
}

export function useProviderModels(apiBase: string, teacherId: string) {
  const [map, setMap] = useState<Record<string, ProviderModelsEntry>>({})
  const mapRef = useRef<Record<string, ProviderModelsEntry>>(map)
  const inFlightRef = useRef<Set<string>>(new Set())
  mapRef.current = map

  const fetchModels = useCallback(
    async (providerId: string) => {
      const cached = mapRef.current[providerId]
      if (cached && !cached.error && Date.now() - cached.fetchedAt < 300_000) return
      if (inFlightRef.current.has(providerId)) return
      inFlightRef.current.add(providerId)

      setMap((prev) => {
        const existing = prev[providerId]
        // 5-minute cache: skip if data exists and is fresh
        if (existing && !existing.error && Date.now() - existing.fetchedAt < 300_000) return prev
        return { ...prev, [providerId]: { models: existing?.models || [], loading: true, error: '', fetchedAt: existing?.fetchedAt || 0 } }
      })
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
      } finally {
        inFlightRef.current.delete(providerId)
      }
    },
    [apiBase, teacherId],
  )

  return { modelsMap: map, fetchModels }
}
