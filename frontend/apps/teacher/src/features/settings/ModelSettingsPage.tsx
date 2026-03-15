import { useCallback, useEffect, useMemo, useState } from 'react'

type PurposeKey = 'conversation' | 'embedding' | 'ocr' | 'image_generation'

type PurposeModelConfig = {
  provider: string
  mode: string
  model: string
}

type CatalogMode = {
  mode: string
  default_model?: string
}

type CatalogProvider = {
  provider: string
  source?: string
  base_url?: string
  modes?: CatalogMode[]
}

type ModelConfigResponse = {
  ok: boolean
  config?: {
    models?: Partial<Record<PurposeKey, PurposeModelConfig>>
  }
  catalog?: {
    providers?: CatalogProvider[]
  }
}

type PrivateProvider = {
  id?: string
  provider?: string
  display_name?: string
  base_url?: string
  api_key_masked?: string
  default_model?: string
  enabled?: boolean
}

type ProviderRegistryResponse = {
  ok: boolean
  providers?: PrivateProvider[]
}

type CreateProviderPayload = {
  provider_id?: string
  display_name: string
  base_url: string
  api_key: string
  default_model?: string
  enabled: boolean
}

type Props = {
  apiBase: string
  onApiBaseChange: (value: string) => void
}

const PURPOSES: Array<{ key: PurposeKey; label: string; description: string }> = [
  { key: 'conversation', label: '对话模型', description: '用于主聊天推理与工具调用。' },
  { key: 'embedding', label: 'Embedding 模型', description: '用于向量化与检索。' },
  { key: 'ocr', label: 'OCR 模型', description: '用于图片/文档文字识别。' },
  { key: 'image_generation', label: '绘图模型', description: '用于图像生成能力。' },
]

const emptyModels = (): Record<PurposeKey, PurposeModelConfig> => ({
  conversation: { provider: '', mode: '', model: '' },
  embedding: { provider: '', mode: '', model: '' },
  ocr: { provider: '', mode: '', model: '' },
  image_generation: { provider: '', mode: '', model: '' },
})

const readResponseError = async (res: Response): Promise<string> => {
  const text = (await res.text()).trim()
  if (text) return text
  return `状态码 ${res.status}`
}

const normalizeCatalogProviders = (value: unknown): CatalogProvider[] => {
  if (!Array.isArray(value)) return []
  return value
    .filter((item) => item && typeof item === 'object')
    .map((item) => {
      const raw = item as Record<string, unknown>
      const rawModes = Array.isArray(raw.modes) ? raw.modes : []
      const modes: CatalogMode[] = rawModes
        .filter((mode) => mode && typeof mode === 'object')
        .map((mode) => {
          const entry = mode as Record<string, unknown>
          return {
            mode: String(entry.mode || ''),
            default_model: String(entry.default_model || ''),
          }
        })
        .filter((mode) => mode.mode)
      return {
        provider: String(raw.provider || ''),
        source: String(raw.source || ''),
        base_url: String(raw.base_url || ''),
        modes,
      }
    })
    .filter((item) => item.provider)
}

const normalizePrivateProviders = (value: unknown): PrivateProvider[] => {
  if (!Array.isArray(value)) return []
  return value
    .filter((item) => item && typeof item === 'object')
    .map((item) => item as PrivateProvider)
    .filter((item) => String(item.id || item.provider || '').trim())
}

const normalizeModels = (value: unknown): Record<PurposeKey, PurposeModelConfig> => {
  const defaults = emptyModels()
  if (!value || typeof value !== 'object') return defaults
  const source = value as Record<string, unknown>
  for (const purpose of PURPOSES) {
    const entry = source[purpose.key]
    if (!entry || typeof entry !== 'object') continue
    const data = entry as Record<string, unknown>
    defaults[purpose.key] = {
      provider: String(data.provider || ''),
      mode: String(data.mode || ''),
      model: String(data.model || ''),
    }
  }
  return defaults
}

export default function ModelSettingsPage({ apiBase, onApiBaseChange }: Props) {
  const [models, setModels] = useState<Record<PurposeKey, PurposeModelConfig>>(emptyModels)
  const [catalogProviders, setCatalogProviders] = useState<CatalogProvider[]>([])
  const [privateProviders, setPrivateProviders] = useState<PrivateProvider[]>([])
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [providerBusy, setProviderBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [newProviderId, setNewProviderId] = useState('')
  const [newProviderName, setNewProviderName] = useState('')
  const [newProviderBaseUrl, setNewProviderBaseUrl] = useState('')
  const [newProviderApiKey, setNewProviderApiKey] = useState('')
  const [newProviderDefaultModel, setNewProviderDefaultModel] = useState('')

  const catalogMap = useMemo(() => {
    const map = new Map<string, CatalogProvider>()
    for (const provider of catalogProviders) map.set(provider.provider, provider)
    return map
  }, [catalogProviders])

  const loadData = useCallback(async () => {
    setLoading(true)
    setError('')
    setMessage('')
    try {
      const [configRes, registryRes] = await Promise.all([
        fetch(`${apiBase}/teacher/model-config`),
        fetch(`${apiBase}/teacher/provider-registry`),
      ])
      if (!configRes.ok) throw new Error(await readResponseError(configRes))
      if (!registryRes.ok) throw new Error(await readResponseError(registryRes))

      const configData = (await configRes.json()) as ModelConfigResponse
      const registryData = (await registryRes.json()) as ProviderRegistryResponse
      if (!configData.ok) throw new Error('模型配置返回失败')
      if (!registryData.ok) throw new Error('模型商配置返回失败')

      const nextProviders = normalizeCatalogProviders(configData.catalog?.providers)
      const nextModels = normalizeModels(configData.config?.models)
      setCatalogProviders(nextProviders)
      setModels(nextModels)
      setPrivateProviders(normalizePrivateProviders(registryData.providers))
    } catch (err) {
      const text = err instanceof Error ? err.message : String(err || '加载失败')
      setError(text)
    } finally {
      setLoading(false)
    }
  }, [apiBase])

  useEffect(() => {
    void loadData()
  }, [loadData])

  const getProviderModes = useCallback(
    (provider: string): CatalogMode[] => {
      const item = catalogMap.get(provider)
      return Array.isArray(item?.modes) ? item.modes : []
    },
    [catalogMap],
  )

  const updatePurposeModel = useCallback(
    (purpose: PurposeKey, patch: Partial<PurposeModelConfig>) => {
      setModels((prev) => ({ ...prev, [purpose]: { ...prev[purpose], ...patch } }))
    },
    [],
  )

  const handleProviderChange = useCallback(
    (purpose: PurposeKey, provider: string) => {
      const modes = getProviderModes(provider)
      const firstMode = modes[0]?.mode || ''
      const firstModel = modes[0]?.default_model || ''
      updatePurposeModel(purpose, { provider, mode: firstMode, model: firstModel })
    },
    [getProviderModes, updatePurposeModel],
  )

  const handleModeChange = useCallback(
    (purpose: PurposeKey, mode: string) => {
      const provider = models[purpose].provider
      const modes = getProviderModes(provider)
      const selected = modes.find((item) => item.mode === mode)
      updatePurposeModel(purpose, { mode, model: selected?.default_model || models[purpose].model })
    },
    [getProviderModes, models, updatePurposeModel],
  )

  const saveModelConfig = useCallback(async () => {
    setSaving(true)
    setError('')
    setMessage('')
    try {
      const res = await fetch(`${apiBase}/teacher/model-config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ models }),
      })
      if (!res.ok) throw new Error(await readResponseError(res))
      const data = (await res.json()) as ModelConfigResponse
      if (!data.ok) throw new Error('保存失败')
      setModels(normalizeModels(data.config?.models))
      setCatalogProviders(normalizeCatalogProviders(data.catalog?.providers))
      setMessage('模型配置已保存。')
    } catch (err) {
      const text = err instanceof Error ? err.message : String(err || '保存失败')
      setError(text)
    } finally {
      setSaving(false)
    }
  }, [apiBase, models])

  const createProvider = useCallback(async () => {
    const payload: CreateProviderPayload = {
      display_name: newProviderName.trim(),
      base_url: newProviderBaseUrl.trim(),
      api_key: newProviderApiKey.trim(),
      default_model: newProviderDefaultModel.trim() || undefined,
      enabled: true,
    }
    if (newProviderId.trim()) payload.provider_id = newProviderId.trim()
    if (!payload.display_name || !payload.base_url || !payload.api_key) {
      setError('请至少填写显示名称、Base URL、API Key。')
      return
    }

    setProviderBusy(true)
    setError('')
    setMessage('')
    try {
      const res = await fetch(`${apiBase}/teacher/provider-registry/providers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) throw new Error(await readResponseError(res))
      setNewProviderId('')
      setNewProviderName('')
      setNewProviderBaseUrl('')
      setNewProviderApiKey('')
      setNewProviderDefaultModel('')
      await loadData()
      setMessage('模型商已新增。')
    } catch (err) {
      const text = err instanceof Error ? err.message : String(err || '新增失败')
      setError(text)
    } finally {
      setProviderBusy(false)
    }
  }, [
    apiBase,
    loadData,
    newProviderApiKey,
    newProviderBaseUrl,
    newProviderDefaultModel,
    newProviderId,
    newProviderName,
  ])

  const disableProvider = useCallback(
    async (providerId: string) => {
      const id = String(providerId || '').trim()
      if (!id) return
      setProviderBusy(true)
      setError('')
      setMessage('')
      try {
        const res = await fetch(`${apiBase}/teacher/provider-registry/providers/${encodeURIComponent(id)}`, {
          method: 'DELETE',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({}),
        })
        if (!res.ok) throw new Error(await readResponseError(res))
        await loadData()
        setMessage(`模型商 ${id} 已停用。`)
      } catch (err) {
        const text = err instanceof Error ? err.message : String(err || '停用失败')
        setError(text)
      } finally {
        setProviderBusy(false)
      }
    },
    [apiBase, loadData],
  )

  return (
    <div className="grid gap-4">
      <section className="rounded-xl border border-border bg-white p-4 grid gap-3">
        <div className="text-sm font-semibold">连接设置</div>
        <label className="grid gap-1.5">
          <span className="text-xs text-muted">API Base</span>
          <input
            value={apiBase}
            onChange={(event) => onApiBaseChange(event.target.value)}
            placeholder="http://localhost:8000"
            className="w-full"
          />
        </label>
        <div className="flex items-center gap-2">
          <button type="button" className="ghost" onClick={() => void loadData()} disabled={loading}>
            {loading ? '刷新中...' : '刷新配置'}
          </button>
        </div>
      </section>

      <section className="rounded-xl border border-border bg-white p-4 grid gap-3">
        <div className="flex items-center justify-between gap-3">
          <div className="text-sm font-semibold">模型用途配置</div>
          <button type="button" className="ghost" onClick={() => void saveModelConfig()} disabled={saving || loading}>
            {saving ? '保存中...' : '保存模型配置'}
          </button>
        </div>
        <div className="grid gap-3">
          {PURPOSES.map((purpose) => {
            const current = models[purpose.key]
            const modes = getProviderModes(current.provider)
            return (
              <div key={purpose.key} className="rounded-lg border border-border bg-surface-soft p-3 grid gap-2">
                <div className="text-[13px] font-semibold">{purpose.label}</div>
                <div className="text-[12px] text-muted">{purpose.description}</div>
                <div className="grid gap-2 md:grid-cols-3">
                  <label className="grid gap-1">
                    <span className="text-xs text-muted">Provider</span>
                    <select
                      value={current.provider}
                      onChange={(event) => handleProviderChange(purpose.key, event.target.value)}
                    >
                      <option value="">请选择</option>
                      {catalogProviders.map((provider) => (
                        <option key={provider.provider} value={provider.provider}>
                          {provider.provider}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="grid gap-1">
                    <span className="text-xs text-muted">Mode</span>
                    <select value={current.mode} onChange={(event) => handleModeChange(purpose.key, event.target.value)}>
                      <option value="">请选择</option>
                      {modes.map((mode) => (
                        <option key={`${current.provider}:${mode.mode}`} value={mode.mode}>
                          {mode.mode}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="grid gap-1">
                    <span className="text-xs text-muted">Model</span>
                    <input
                      value={current.model}
                      onChange={(event) => updatePurposeModel(purpose.key, { model: event.target.value })}
                      placeholder="例如 gpt-4.1-mini"
                    />
                  </label>
                </div>
              </div>
            )
          })}
        </div>
      </section>

      <section className="rounded-xl border border-border bg-white p-4 grid gap-3">
        <div className="text-sm font-semibold">模型商管理</div>
        <div className="grid gap-2 md:grid-cols-2">
          <label className="grid gap-1">
            <span className="text-xs text-muted">Provider ID（可选）</span>
            <input value={newProviderId} onChange={(event) => setNewProviderId(event.target.value)} placeholder="例如 tprv_openrouter_01" />
          </label>
          <label className="grid gap-1">
            <span className="text-xs text-muted">显示名称</span>
            <input value={newProviderName} onChange={(event) => setNewProviderName(event.target.value)} placeholder="例如 OpenRouter" />
          </label>
          <label className="grid gap-1">
            <span className="text-xs text-muted">Base URL</span>
            <input value={newProviderBaseUrl} onChange={(event) => setNewProviderBaseUrl(event.target.value)} placeholder="https://openrouter.ai/api/v1" />
          </label>
          <label className="grid gap-1">
            <span className="text-xs text-muted">默认模型（可选）</span>
            <input value={newProviderDefaultModel} onChange={(event) => setNewProviderDefaultModel(event.target.value)} placeholder="例如 openai/gpt-4.1-mini" />
          </label>
        </div>
        <label className="grid gap-1">
          <span className="text-xs text-muted">API Key</span>
          <input
            value={newProviderApiKey}
            onChange={(event) => setNewProviderApiKey(event.target.value)}
            placeholder="sk-..."
            type="password"
          />
        </label>
        <div className="flex items-center gap-2">
          <button type="button" className="ghost" onClick={() => void createProvider()} disabled={providerBusy}>
            {providerBusy ? '提交中...' : '新增模型商'}
          </button>
        </div>

        <div className="grid gap-2">
          {privateProviders.length === 0 ? (
            <div className="text-[12px] text-muted">暂无私有模型商。</div>
          ) : (
            privateProviders.map((provider) => {
              const providerId = String(provider.id || provider.provider || '').trim()
              return (
                <div key={providerId} className="rounded-lg border border-border p-2 grid gap-1">
                  <div className="text-[13px] font-semibold">{provider.display_name || providerId}</div>
                  <div className="text-[12px] text-muted break-all">{providerId}</div>
                  <div className="text-[12px] text-muted break-all">{provider.base_url || '-'}</div>
                  <div className="text-[12px] text-muted">
                    key: {provider.api_key_masked || '***'} | 默认模型: {provider.default_model || '-'}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[12px] text-muted">{provider.enabled === false ? '状态：停用' : '状态：启用'}</span>
                    {provider.enabled === false ? null : (
                      <button type="button" className="ghost" onClick={() => void disableProvider(providerId)} disabled={providerBusy}>
                        停用
                      </button>
                    )}
                  </div>
                </div>
              )
            })
          )}
        </div>
      </section>

      {error ? <div className="text-[12px] text-[#b91c1c]">{error}</div> : null}
      {message ? <div className="text-[12px] text-success">{message}</div> : null}
    </div>
  )
}
