import { useCallback, useEffect, useRef } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import { fetchProviderRegistry, fetchRoutingOverview } from './routingApi'
import { emptyRoutingConfig } from './routingTypes'
import type { RoutingConfig, RoutingOverview, TeacherProviderRegistryOverview } from './routingTypes'

type ProviderEditMap = Record<
  string,
  { display_name: string; base_url: string; enabled: boolean; api_key: string; default_model: string }
>

type LoadOverviewOptions = {
  silent?: boolean
  forceReplaceDraft?: boolean
}

type Props = {
  apiBase: string
  teacherId: string
  hasLocalEdits: boolean
  providerOverview: TeacherProviderRegistryOverview | null
  cloneConfig: (config: RoutingConfig) => RoutingConfig
  setLoading: Dispatch<SetStateAction<boolean>>
  setError: Dispatch<SetStateAction<string>>
  setOverview: Dispatch<SetStateAction<RoutingOverview | null>>
  setDraft: Dispatch<SetStateAction<RoutingConfig>>
  setHasLocalEdits: Dispatch<SetStateAction<boolean>>
  setProviderOverview: Dispatch<SetStateAction<TeacherProviderRegistryOverview | null>>
  setProviderEditMap: Dispatch<SetStateAction<ProviderEditMap>>
}

export function useRoutingOverviewSync({
  apiBase,
  teacherId,
  hasLocalEdits,
  providerOverview,
  cloneConfig,
  setLoading,
  setError,
  setOverview,
  setDraft,
  setHasLocalEdits,
  setProviderOverview,
  setProviderEditMap,
}: Props) {
  const hasLocalEditsRef = useRef(hasLocalEdits)

  useEffect(() => {
    hasLocalEditsRef.current = hasLocalEdits
  }, [hasLocalEdits])

  const loadOverview = useCallback(
    async (options?: LoadOverviewOptions) => {
      const silent = Boolean(options?.silent)
      const forceReplaceDraft = Boolean(options?.forceReplaceDraft)
      if (!silent) setLoading(true)
      setError('')
      try {
        let nextError = ''

        try {
          const data = await fetchRoutingOverview(apiBase, {
            teacher_id: teacherId || undefined,
            history_limit: 40,
            proposal_limit: 40,
          })
          setOverview(data)
          if (forceReplaceDraft || !hasLocalEditsRef.current) {
            setDraft(cloneConfig(data.routing || emptyRoutingConfig()))
            setHasLocalEdits(false)
          }
        } catch (err) {
          nextError = (err as Error).message || '加载模型路由失败'
        }

        try {
          const providerData = await fetchProviderRegistry(apiBase, { teacher_id: teacherId || undefined })
          setProviderOverview(providerData)
        } catch (err) {
          const providerError = (err as Error).message || '加载 Provider 配置失败'
          nextError = nextError ? `${nextError}；${providerError}` : providerError
        }

        if (nextError) setError(nextError)
      } catch (err) {
        setError((err as Error).message || '加载模型路由失败')
      } finally {
        if (!silent) setLoading(false)
      }
    },
    [
      apiBase,
      cloneConfig,
      setDraft,
      setError,
      setHasLocalEdits,
      setLoading,
      setOverview,
      setProviderOverview,
      teacherId,
    ],
  )

  useEffect(() => {
    void loadOverview({ forceReplaceDraft: true })
  }, [loadOverview])

  useEffect(() => {
    const timer = window.setInterval(() => {
      void loadOverview({ silent: true })
    }, 30000)
    return () => window.clearInterval(timer)
  }, [loadOverview])

  useEffect(() => {
    const next: ProviderEditMap = {}
    ;(providerOverview?.providers || []).forEach((item) => {
      next[item.provider] = {
        display_name: item.display_name || '',
        base_url: item.base_url || '',
        enabled: item.enabled !== false,
        api_key: '',
        default_model: item.default_model || '',
      }
    })
    setProviderEditMap(next)
  }, [providerOverview?.providers, setProviderEditMap])

  return { loadOverview }
}
