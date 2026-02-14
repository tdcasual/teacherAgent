import { useCallback } from 'react'
import type { Dispatch, SetStateAction } from 'react'
import {
  createProviderRegistryItem,
  deleteProviderRegistryItem,
  probeProviderRegistryModels,
  updateProviderRegistryItem,
} from './routingApi'
import type { TeacherProviderRegistryOverview } from './routingTypes'

type ProviderEditForm = {
  display_name: string
  base_url: string
  enabled: boolean
  api_key: string
  default_model: string
}

type ProviderCreateForm = {
  provider_id: string
  display_name: string
  base_url: string
  api_key: string
  default_model: string
  enabled: boolean
}

type LoadOverviewFn = (options?: { silent?: boolean; forceReplaceDraft?: boolean }) => Promise<void>

type Props = {
  apiBase: string
  teacherId: string
  providerOverview: TeacherProviderRegistryOverview | null
  providerCreateForm: ProviderCreateForm
  providerEditMap: Record<string, ProviderEditForm>
  loadOverview: LoadOverviewFn
  setProviderBusy: Dispatch<SetStateAction<boolean>>
  setError: Dispatch<SetStateAction<string>>
  setStatus: Dispatch<SetStateAction<string>>
  setProviderCreateForm: Dispatch<SetStateAction<ProviderCreateForm>>
  setProviderAddMode: Dispatch<SetStateAction<'' | 'preset' | 'custom'>>
  setProviderAddPreset: Dispatch<SetStateAction<string>>
  setProviderProbeMap: Dispatch<SetStateAction<Record<string, string>>>
}

export function useRoutingProviderMutations({
  apiBase,
  teacherId,
  providerOverview,
  providerCreateForm,
  providerEditMap,
  loadOverview,
  setProviderBusy,
  setError,
  setStatus,
  setProviderCreateForm,
  setProviderAddMode,
  setProviderAddPreset,
  setProviderProbeMap,
}: Props) {
  const handleCreateProvider = useCallback(async () => {
    const formBaseUrl = providerCreateForm.base_url.trim()
    const formApiKey = providerCreateForm.api_key.trim()
    // For preset providers, base_url is optional (use catalog default)
    const catalogProvider = (providerOverview?.shared_catalog?.providers || []).find(
      (provider) => provider.provider === providerCreateForm.provider_id.trim(),
    )
    const effectiveBaseUrl = formBaseUrl || catalogProvider?.base_url || ''
    if (!effectiveBaseUrl || !formApiKey) {
      setError('新增 Provider 需要填写 base_url 和 api_key')
      return
    }
    setProviderBusy(true)
    setError('')
    setStatus('')
    try {
      const result = await createProviderRegistryItem(apiBase, {
        teacher_id: teacherId || undefined,
        provider_id: providerCreateForm.provider_id.trim() || undefined,
        display_name: providerCreateForm.display_name.trim() || undefined,
        base_url: effectiveBaseUrl,
        api_key: formApiKey,
        default_model: providerCreateForm.default_model.trim() || undefined,
        enabled: providerCreateForm.enabled,
      })
      if (!result.ok) throw new Error(result.error ? String(result.error) : '新增失败')
      setProviderCreateForm({
        provider_id: '',
        display_name: '',
        base_url: '',
        api_key: '',
        default_model: '',
        enabled: true,
      })
      setProviderAddMode('')
      setProviderAddPreset('')
      setStatus('Provider 已新增并即时生效。')
      await loadOverview({ silent: true })
    } catch (err) {
      setError((err as Error).message || '新增 Provider 失败')
    } finally {
      setProviderBusy(false)
    }
  }, [
    apiBase,
    loadOverview,
    providerCreateForm,
    providerOverview?.shared_catalog?.providers,
    setError,
    setProviderAddMode,
    setProviderAddPreset,
    setProviderBusy,
    setProviderCreateForm,
    setStatus,
    teacherId,
  ])

  const handleUpdateProvider = useCallback(async (providerId: string) => {
    const draftForm = providerEditMap[providerId]
    if (!draftForm) return
    setProviderBusy(true)
    setError('')
    setStatus('')
    try {
      const payload: {
        teacher_id?: string
        display_name?: string
        base_url?: string
        enabled?: boolean
        api_key?: string
        default_model?: string
      } = {
        teacher_id: teacherId || undefined,
        display_name: draftForm.display_name.trim() || undefined,
        enabled: Boolean(draftForm.enabled),
      }
      payload.base_url = draftForm.base_url.trim()
      payload.default_model = draftForm.default_model.trim() || undefined
      if (draftForm.api_key.trim()) payload.api_key = draftForm.api_key.trim()
      const result = await updateProviderRegistryItem(apiBase, providerId, payload)
      if (!result.ok) throw new Error(result.error ? String(result.error) : '更新失败')
      setStatus(`Provider ${providerId} 已更新。`)
      await loadOverview({ silent: true })
    } catch (err) {
      setError((err as Error).message || '更新 Provider 失败')
    } finally {
      setProviderBusy(false)
    }
  }, [apiBase, loadOverview, providerEditMap, setError, setProviderBusy, setStatus, teacherId])

  const handleDisableProvider = useCallback(async (providerId: string) => {
    setProviderBusy(true)
    setError('')
    setStatus('')
    try {
      const result = await deleteProviderRegistryItem(apiBase, providerId, { teacher_id: teacherId || undefined })
      if (!result.ok) throw new Error(result.error ? String(result.error) : '禁用失败')
      setStatus(`Provider ${providerId} 已禁用。`)
      await loadOverview({ silent: true })
    } catch (err) {
      setError((err as Error).message || '禁用 Provider 失败')
    } finally {
      setProviderBusy(false)
    }
  }, [apiBase, loadOverview, setError, setProviderBusy, setStatus, teacherId])

  const handleProbeProviderModels = useCallback(async (providerId: string) => {
    setProviderBusy(true)
    setError('')
    setStatus('')
    try {
      const result = await probeProviderRegistryModels(apiBase, providerId, { teacher_id: teacherId || undefined })
      if (!result.ok) throw new Error(result.detail || result.error || '探测失败')
      const models = (result.models || []).slice(0, 12)
      setProviderProbeMap((prev) => ({ ...prev, [providerId]: models.join('，') || '未返回模型列表' }))
      setStatus(`Provider ${providerId} 探测完成。`)
    } catch (err) {
      setError((err as Error).message || '探测模型失败')
    } finally {
      setProviderBusy(false)
    }
  }, [apiBase, setError, setProviderBusy, setProviderProbeMap, setStatus, teacherId])

  return {
    handleCreateProvider,
    handleUpdateProvider,
    handleDisableProvider,
    handleProbeProviderModels,
  }
}
