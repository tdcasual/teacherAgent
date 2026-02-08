import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  createProviderRegistryItem,
  createRoutingProposal,
  deleteProviderRegistryItem,
  fetchProviderRegistry,
  fetchRoutingProposalDetail,
  fetchRoutingOverview,
  probeProviderRegistryModels,
  reviewRoutingProposal,
  rollbackRoutingConfig,
  simulateRouting,
  updateProviderRegistryItem,
} from './routingApi'
import type {
  RoutingCatalogProvider,
  RoutingChannel,
  RoutingConfig,
  RoutingOverview,
  TeacherProviderItem,
  TeacherProviderRegistryOverview,
  RoutingProposalDetail,
  RoutingRule,
  RoutingSimulateResult,
} from './routingTypes'
import { emptyRoutingConfig } from './routingTypes'
import { safeLocalStorageGetItem, safeLocalStorageSetItem } from '../../utils/storage'

type Props = {
  apiBase: string
}

const makeId = (prefix: string) => `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`

const parseList = (value: string) =>
  value
    .split(/[，,\n]+/)
    .map((item) => item.trim())
    .filter(Boolean)

const formatList = (items: string[]) => items.join('，')

const asNumberOrNull = (value: string): number | null => {
  const text = value.trim()
  if (!text) return null
  const num = Number(text)
  return Number.isFinite(num) ? num : null
}

const cloneConfig = (config: RoutingConfig): RoutingConfig => ({
  schema_version: config.schema_version,
  enabled: Boolean(config.enabled),
  version: Number(config.version || 1),
  updated_at: config.updated_at || '',
  updated_by: config.updated_by || '',
  channels: (config.channels || []).map((channel) => ({
    id: channel.id || '',
    title: channel.title || '',
    target: {
      provider: channel.target?.provider || '',
      mode: channel.target?.mode || '',
      model: channel.target?.model || '',
    },
    params: {
      temperature: channel.params?.temperature ?? null,
      max_tokens: channel.params?.max_tokens ?? null,
    },
    fallback_channels: Array.isArray(channel.fallback_channels) ? [...channel.fallback_channels] : [],
    capabilities: {
      tools: channel.capabilities?.tools ?? true,
      json: channel.capabilities?.json ?? true,
    },
  })),
  rules: (config.rules || []).map((rule) => ({
    id: rule.id || '',
    priority: Number(rule.priority || 0),
    enabled: rule.enabled !== false,
    match: {
      roles: Array.isArray(rule.match?.roles) ? [...rule.match.roles] : [],
      skills: Array.isArray(rule.match?.skills) ? [...rule.match.skills] : [],
      kinds: Array.isArray(rule.match?.kinds) ? [...rule.match.kinds] : [],
      needs_tools: rule.match?.needs_tools ?? undefined,
      needs_json: rule.match?.needs_json ?? undefined,
    },
    route: { channel_id: rule.route?.channel_id || '' },
  })),
})

const boolMatchValue = (value: boolean | null | undefined) => {
  if (value === true) return 'true'
  if (value === false) return 'false'
  return 'any'
}

const boolMatchFromValue = (value: string): boolean | undefined => {
  if (value === 'true') return true
  if (value === 'false') return false
  return undefined
}

export default function RoutingPage({ apiBase }: Props) {
  const [teacherId, setTeacherId] = useState(() => {
    return safeLocalStorageGetItem('teacherRoutingTeacherId') || ''
  })
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')
  const [overview, setOverview] = useState<RoutingOverview | null>(null)
  const [draft, setDraft] = useState<RoutingConfig>(() => emptyRoutingConfig())
  const [hasLocalEdits, setHasLocalEdits] = useState(false)
  const [proposalNote, setProposalNote] = useState('')
  const [rollbackVersion, setRollbackVersion] = useState('')
  const [rollbackNote, setRollbackNote] = useState('')
  const [simRole, setSimRole] = useState('teacher')
  const [simSkillId, setSimSkillId] = useState('physics-teacher-ops')
  const [simKind, setSimKind] = useState('chat.agent')
  const [simNeedsTools, setSimNeedsTools] = useState(true)
  const [simNeedsJson, setSimNeedsJson] = useState(false)
  const [simResult, setSimResult] = useState<RoutingSimulateResult | null>(null)
  const [expandedProposalIds, setExpandedProposalIds] = useState<Record<string, boolean>>({})
  const [proposalDetails, setProposalDetails] = useState<Record<string, RoutingProposalDetail>>({})
  const [proposalLoadingMap, setProposalLoadingMap] = useState<Record<string, boolean>>({})
  const [providerOverview, setProviderOverview] = useState<TeacherProviderRegistryOverview | null>(null)
  const [providerBusy, setProviderBusy] = useState(false)
  const [providerProbeMap, setProviderProbeMap] = useState<Record<string, string>>({})
  const [providerCreateForm, setProviderCreateForm] = useState({
    provider_id: '',
    display_name: '',
    base_url: '',
    api_key: '',
    default_model: '',
    enabled: true,
  })
  const [providerEditMap, setProviderEditMap] = useState<
    Record<string, { display_name: string; base_url: string; default_model: string; enabled: boolean; api_key: string }>
  >({})

  useEffect(() => {
    safeLocalStorageSetItem('teacherRoutingTeacherId', teacherId)
  }, [teacherId])

  useEffect(() => {
    setExpandedProposalIds({})
    setProposalDetails({})
    setProposalLoadingMap({})
  }, [teacherId])

  const loadOverview = useCallback(
    async (options?: { silent?: boolean; forceReplaceDraft?: boolean }) => {
      const silent = Boolean(options?.silent)
      const forceReplaceDraft = Boolean(options?.forceReplaceDraft)
      if (!silent) setLoading(true)
      setError('')
      try {
        const [data, providerData] = await Promise.all([
          fetchRoutingOverview(apiBase, {
            teacher_id: teacherId || undefined,
            history_limit: 40,
            proposal_limit: 40,
          }),
          fetchProviderRegistry(apiBase, { teacher_id: teacherId || undefined }),
        ])
        setOverview(data)
        setProviderOverview(providerData)
        if (forceReplaceDraft || !hasLocalEdits) {
          setDraft(cloneConfig(data.routing || emptyRoutingConfig()))
          setHasLocalEdits(false)
        }
      } catch (err) {
        setError((err as Error).message || '加载模型路由失败')
      } finally {
        if (!silent) setLoading(false)
      }
    },
    [apiBase, hasLocalEdits, teacherId],
  )

  useEffect(() => {
    void loadOverview()
  }, [loadOverview])

  useEffect(() => {
    const timer = window.setInterval(() => {
      void loadOverview({ silent: true })
    }, 30000)
    return () => window.clearInterval(timer)
  }, [loadOverview])

  useEffect(() => {
    const next: Record<string, { display_name: string; base_url: string; default_model: string; enabled: boolean; api_key: string }> = {}
    ;(providerOverview?.providers || []).forEach((item) => {
      next[item.provider] = {
        display_name: item.display_name || '',
        base_url: item.base_url || '',
        default_model: item.default_model || '',
        enabled: item.enabled !== false,
        api_key: '',
      }
    })
    setProviderEditMap(next)
  }, [providerOverview?.providers])

  const providers = useMemo(() => (overview?.catalog?.providers || []) as RoutingCatalogProvider[], [overview?.catalog?.providers])
  const providerModeMap = useMemo(() => {
    const map = new Map<string, string[]>()
    providers.forEach((provider) => {
      map.set(
        provider.provider,
        (provider.modes || []).map((mode) => mode.mode).filter(Boolean),
      )
    })
    return map
  }, [providers])

  const setDraftWithEdit = useCallback((updater: (prev: RoutingConfig) => RoutingConfig) => {
    setDraft((prev) => updater(prev))
    setHasLocalEdits(true)
  }, [])

  const addChannel = () => {
    const defaultProvider = overview?.catalog?.defaults?.provider || providers[0]?.provider || 'siliconflow'
    const defaultModes = providerModeMap.get(defaultProvider) || []
    const defaultMode = overview?.catalog?.defaults?.mode || defaultModes[0] || 'openai-chat'
    const channel: RoutingChannel = {
      id: makeId('channel'),
      title: '新渠道',
      target: {
        provider: defaultProvider,
        mode: defaultMode,
        model: '',
      },
      params: { temperature: null, max_tokens: null },
      fallback_channels: [],
      capabilities: { tools: true, json: true },
    }
    setDraftWithEdit((prev) => ({ ...prev, channels: [...prev.channels, channel] }))
  }

  const removeChannel = (index: number) => {
    setDraftWithEdit((prev) => {
      const removed = prev.channels[index]
      const nextChannels = prev.channels.filter((_, i) => i !== index)
      const fallbackChannelId = nextChannels[0]?.id || ''
      const nextRules = prev.rules.map((rule) => {
        if ((rule.route?.channel_id || '') !== (removed?.id || '')) return rule
        return { ...rule, route: { channel_id: fallbackChannelId } }
      })
      return { ...prev, channels: nextChannels, rules: nextRules }
    })
  }

  const updateChannel = (index: number, updater: (channel: RoutingChannel) => RoutingChannel) => {
    setDraftWithEdit((prev) => ({
      ...prev,
      channels: prev.channels.map((channel, idx) => (idx === index ? updater(channel) : channel)),
    }))
  }

  const addRule = () => {
    const firstChannelId = draft.channels[0]?.id || ''
    const rule: RoutingRule = {
      id: makeId('rule'),
      priority: 100,
      enabled: true,
      match: { roles: ['teacher'], skills: [], kinds: [], needs_tools: undefined, needs_json: undefined },
      route: { channel_id: firstChannelId },
    }
    setDraftWithEdit((prev) => ({ ...prev, rules: [...prev.rules, rule] }))
  }

  const removeRule = (index: number) => {
    setDraftWithEdit((prev) => ({ ...prev, rules: prev.rules.filter((_, idx) => idx !== index) }))
  }

  const updateRule = (index: number, updater: (rule: RoutingRule) => RoutingRule) => {
    setDraftWithEdit((prev) => ({
      ...prev,
      rules: prev.rules.map((rule, idx) => (idx === index ? updater(rule) : rule)),
    }))
  }

  const handleCreateProvider = async () => {
    if (!providerCreateForm.base_url.trim() || !providerCreateForm.api_key.trim()) {
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
        base_url: providerCreateForm.base_url.trim(),
        api_key: providerCreateForm.api_key.trim(),
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
      setStatus('Provider 已新增并即时生效。')
      await loadOverview({ silent: true })
    } catch (err) {
      setError((err as Error).message || '新增 Provider 失败')
    } finally {
      setProviderBusy(false)
    }
  }

  const handleUpdateProvider = async (providerId: string) => {
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
        default_model?: string
        enabled?: boolean
        api_key?: string
      } = {
        teacher_id: teacherId || undefined,
        display_name: draftForm.display_name.trim() || undefined,
        base_url: draftForm.base_url.trim() || undefined,
        default_model: draftForm.default_model.trim() || undefined,
        enabled: Boolean(draftForm.enabled),
      }
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
  }

  const handleDisableProvider = async (providerId: string) => {
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
  }

  const handleProbeProviderModels = async (providerId: string) => {
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
  }

  const handleResetDraft = () => {
    if (!overview) return
    setDraft(cloneConfig(overview.routing || emptyRoutingConfig()))
    setHasLocalEdits(false)
    setStatus('已恢复为线上配置。')
    setError('')
  }

  const handleSimulate = async () => {
    setBusy(true)
    setStatus('')
    setError('')
    try {
      const result = await simulateRouting(apiBase, {
        teacher_id: teacherId || undefined,
        role: simRole || undefined,
        skill_id: simSkillId || undefined,
        kind: simKind || undefined,
        needs_tools: simNeedsTools,
        needs_json: simNeedsJson,
        config: draft as unknown as Record<string, unknown>,
      })
      setSimResult(result)
      setStatus('仿真完成。')
    } catch (err) {
      setError((err as Error).message || '仿真失败')
    } finally {
      setBusy(false)
    }
  }

  const handlePropose = async () => {
    setBusy(true)
    setStatus('')
    setError('')
    try {
      const result = await createRoutingProposal(apiBase, {
        teacher_id: teacherId || undefined,
        note: proposalNote || undefined,
        config: draft as unknown as Record<string, unknown>,
      })
      if (!result.ok) throw new Error(result.error ? JSON.stringify(result.error) : '提案失败')
      setStatus(`提案已创建：${result.proposal_id}`)
      setProposalNote('')
      await loadOverview({ silent: true })
    } catch (err) {
      setError((err as Error).message || '提案提交失败')
    } finally {
      setBusy(false)
    }
  }

  const handleReviewProposal = async (proposalId: string, approve: boolean) => {
    setBusy(true)
    setStatus('')
    setError('')
    try {
      const result = await reviewRoutingProposal(apiBase, proposalId, {
        teacher_id: teacherId || undefined,
        approve,
      })
      if (!result.ok) throw new Error(result.error ? JSON.stringify(result.error) : '审核失败')
      setStatus(approve ? `提案 ${proposalId} 已生效` : `提案 ${proposalId} 已拒绝`)
      setExpandedProposalIds((prev) => ({ ...prev, [proposalId]: false }))
      await loadOverview({ silent: true, forceReplaceDraft: approve })
    } catch (err) {
      setError((err as Error).message || '提案审核失败')
    } finally {
      setBusy(false)
    }
  }

  const handleToggleProposalDetail = async (proposalId: string) => {
    const nextExpanded = !Boolean(expandedProposalIds[proposalId])
    setExpandedProposalIds((prev) => ({ ...prev, [proposalId]: nextExpanded }))
    if (!nextExpanded) return
    if (proposalDetails[proposalId] || proposalLoadingMap[proposalId]) return
    setProposalLoadingMap((prev) => ({ ...prev, [proposalId]: true }))
    setError('')
    try {
      const detail = await fetchRoutingProposalDetail(apiBase, proposalId, teacherId || undefined)
      setProposalDetails((prev) => ({ ...prev, [proposalId]: detail }))
    } catch (err) {
      setError((err as Error).message || '提案详情加载失败')
    } finally {
      setProposalLoadingMap((prev) => ({ ...prev, [proposalId]: false }))
    }
  }

  const handleRollback = async (targetVersion: number) => {
    if (!Number.isFinite(targetVersion) || targetVersion <= 0) {
      setError('回滚版本号无效')
      return
    }
    setBusy(true)
    setStatus('')
    setError('')
    try {
      const result = await rollbackRoutingConfig(apiBase, {
        teacher_id: teacherId || undefined,
        target_version: targetVersion,
        note: rollbackNote || undefined,
      })
      if (!result.ok) throw new Error(result.error || '回滚失败')
      setStatus(`已回滚到版本 ${targetVersion}`)
      setRollbackVersion('')
      setRollbackNote('')
      await loadOverview({ silent: true, forceReplaceDraft: true })
    } catch (err) {
      setError((err as Error).message || '回滚失败')
    } finally {
      setBusy(false)
    }
  }

  const pendingProposals = (overview?.proposals || []).filter((item) => item.status === 'pending')
  const history = overview?.history || []
  const ruleOrderHint = draft.rules
    .slice()
    .sort((a, b) => (b.priority || 0) - (a.priority || 0))
    .map((rule) => `${rule.id || '未命名'}(${rule.priority})`)
    .join(' -> ')

  return (
    <div className="routing-page">
      <section className="routing-card">
        <div className="routing-header">
          <h2>模型路由配置</h2>
          <div className="routing-actions">
            <button type="button" className="secondary-btn" onClick={() => void loadOverview()} disabled={loading || busy}>
              {loading ? '刷新中…' : '刷新'}
            </button>
            <button type="button" className="secondary-btn" onClick={handleResetDraft} disabled={!hasLocalEdits || busy}>
              重置草稿
            </button>
            <button type="button" onClick={handlePropose} disabled={busy}>
              {busy ? '处理中…' : '提交提案'}
            </button>
          </div>
        </div>
        <div className="routing-meta-grid">
          <div className="routing-field">
            <label>教师标识（可选）</label>
            <input value={teacherId} onChange={(e) => setTeacherId(e.target.value)} placeholder="默认 teacher" />
          </div>
          <div className="routing-field">
            <label>启用自定义路由</label>
            <label className="toggle">
              <input
                type="checkbox"
                checked={Boolean(draft.enabled)}
                onChange={(e) => setDraftWithEdit((prev) => ({ ...prev, enabled: e.target.checked }))}
              />
              {draft.enabled ? '已启用' : '已关闭'}
            </label>
          </div>
          <div className="routing-stat">线上版本：{overview?.routing?.version ?? '-'}</div>
          <div className="routing-stat">草稿规则：{draft.rules.length} 条</div>
          <div className="routing-stat">草稿渠道：{draft.channels.length} 个</div>
          <div className="routing-stat">最后更新：{overview?.routing?.updated_at || '—'}</div>
        </div>
        {hasLocalEdits && <div className="status ok">当前为本地草稿，尚未提交提案。</div>}
        {overview?.validation?.errors?.length ? (
          <div className="status err">线上配置校验错误：{overview.validation.errors.join('；')}</div>
        ) : null}
        {overview?.validation?.warnings?.length ? (
          <div className="status ok">线上配置提示：{overview.validation.warnings.join('；')}</div>
        ) : null}
        {status && <div className="status ok">{status}</div>}
        {error && <div className="status err">{error}</div>}
      </section>

      <section className="routing-card">
        <div className="routing-section-header">
          <h3>Provider 管理（共享 + 私有）</h3>
        </div>
        <div className="routing-meta-grid">
          <div className="routing-stat">共享 Provider：{providerOverview?.shared_catalog?.providers?.length ?? 0}</div>
          <div className="routing-stat">私有 Provider：{providerOverview?.providers?.length ?? 0}</div>
          <div className="routing-stat">配置文件：{providerOverview?.config_path || '—'}</div>
        </div>
        <div className="routing-item">
          <div className="routing-item-head">
            <strong>新增私有 Provider（OpenAI-Compatible）</strong>
          </div>
          <div className="routing-grid">
            <div className="routing-field">
              <label>Provider ID（可选）</label>
              <input
                value={providerCreateForm.provider_id}
                onChange={(e) => setProviderCreateForm((prev) => ({ ...prev, provider_id: e.target.value }))}
                placeholder="例如：tprv_proxy_main"
              />
            </div>
            <div className="routing-field">
              <label>显示名称</label>
              <input
                value={providerCreateForm.display_name}
                onChange={(e) => setProviderCreateForm((prev) => ({ ...prev, display_name: e.target.value }))}
                placeholder="例如：主中转"
              />
            </div>
            <div className="routing-field">
              <label>Base URL</label>
              <input
                value={providerCreateForm.base_url}
                onChange={(e) => setProviderCreateForm((prev) => ({ ...prev, base_url: e.target.value }))}
                placeholder="例如：https://proxy.example.com/v1"
              />
            </div>
            <div className="routing-field">
              <label>API Key</label>
                <input
                  type="password"
                  autoComplete="new-password"
                  value={providerCreateForm.api_key}
                  onChange={(e) => setProviderCreateForm((prev) => ({ ...prev, api_key: e.target.value }))}
                  placeholder="仅提交时可见，后续仅显示掩码"
                />
            </div>
            <div className="routing-field">
              <label>默认模型</label>
              <input
                value={providerCreateForm.default_model}
                onChange={(e) => setProviderCreateForm((prev) => ({ ...prev, default_model: e.target.value }))}
                placeholder="例如：gpt-4.1-mini"
              />
            </div>
            <div className="routing-field">
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={providerCreateForm.enabled}
                  onChange={(e) => setProviderCreateForm((prev) => ({ ...prev, enabled: e.target.checked }))}
                />
                启用
              </label>
            </div>
          </div>
          <div className="routing-actions">
            <button type="button" onClick={() => void handleCreateProvider()} disabled={providerBusy || busy}>
              {providerBusy ? '处理中…' : '新增 Provider'}
            </button>
          </div>
        </div>

        <div className="routing-subsection">
          <h4>私有 Provider 列表</h4>
          {(providerOverview?.providers || []).length === 0 ? <div className="muted">暂无私有 Provider。</div> : null}
          {(providerOverview?.providers || []).map((item: TeacherProviderItem) => {
            const edit = providerEditMap[item.provider] || {
              display_name: item.display_name || '',
              base_url: item.base_url || '',
              default_model: item.default_model || '',
              enabled: item.enabled !== false,
              api_key: '',
            }
            return (
              <div key={item.provider} className="routing-item">
                <div className="routing-item-head">
                  <strong>{item.provider}</strong>
                  <span className="muted"> key: {item.api_key_masked || '已隐藏'}</span>
                </div>
                <div className="routing-grid">
                  <div className="routing-field">
                    <label>显示名称</label>
                    <input
                      value={edit.display_name}
                      onChange={(e) =>
                        setProviderEditMap((prev) => ({
                          ...prev,
                          [item.provider]: { ...edit, display_name: e.target.value },
                        }))
                      }
                    />
                  </div>
                  <div className="routing-field">
                    <label>Base URL</label>
                    <input
                      value={edit.base_url}
                      onChange={(e) =>
                        setProviderEditMap((prev) => ({
                          ...prev,
                          [item.provider]: { ...edit, base_url: e.target.value },
                        }))
                      }
                    />
                  </div>
                  <div className="routing-field">
                    <label>默认模型</label>
                    <input
                      value={edit.default_model}
                      onChange={(e) =>
                        setProviderEditMap((prev) => ({
                          ...prev,
                          [item.provider]: { ...edit, default_model: e.target.value },
                        }))
                      }
                    />
                  </div>
                  <div className="routing-field">
                    <label>轮换 API Key（可选）</label>
                    <input
                      type="password"
                      autoComplete="new-password"
                      value={edit.api_key}
                      onChange={(e) =>
                        setProviderEditMap((prev) => ({
                          ...prev,
                          [item.provider]: { ...edit, api_key: e.target.value },
                        }))
                      }
                      placeholder="留空表示不变更"
                    />
                  </div>
                  <div className="routing-field">
                    <label className="toggle">
                      <input
                        type="checkbox"
                        checked={edit.enabled}
                        onChange={(e) =>
                          setProviderEditMap((prev) => ({
                            ...prev,
                            [item.provider]: { ...edit, enabled: e.target.checked },
                          }))
                        }
                      />
                      启用
                    </label>
                  </div>
                </div>
                <div className="routing-actions">
                  <button type="button" onClick={() => void handleUpdateProvider(item.provider)} disabled={providerBusy || busy}>
                    保存
                  </button>
                  <button
                    type="button"
                    className="secondary-btn"
                    onClick={() => void handleProbeProviderModels(item.provider)}
                    disabled={providerBusy || busy}
                  >
                    探测模型
                  </button>
                  <button
                    type="button"
                    className="secondary-btn"
                    onClick={() => void handleDisableProvider(item.provider)}
                    disabled={providerBusy || busy}
                  >
                    禁用
                  </button>
                </div>
                {providerProbeMap[item.provider] ? <div className="muted">探测结果：{providerProbeMap[item.provider]}</div> : null}
              </div>
            )
          })}
        </div>
      </section>

      <section className="routing-card">
        <div className="routing-section-header">
          <h3>渠道配置</h3>
          <button type="button" className="secondary-btn" onClick={addChannel} disabled={busy}>
            新增渠道
          </button>
        </div>
        {draft.channels.length === 0 && <div className="muted">暂无渠道，请先新增。</div>}
        <div className="routing-list">
          {draft.channels.map((channel, index) => {
            const modeOptions = providerModeMap.get(channel.target.provider) || []
            return (
              <div key={`${channel.id}_${index}`} className="routing-item">
                <div className="routing-item-head">
                  <strong>{channel.title || channel.id || `渠道${index + 1}`}</strong>
                  <button type="button" className="ghost" onClick={() => removeChannel(index)} disabled={busy}>
                    删除
                  </button>
                </div>
                <div className="routing-grid">
                  <div className="routing-field">
                    <label>渠道 ID</label>
                    <input
                      value={channel.id}
                      onChange={(e) => updateChannel(index, (prev) => ({ ...prev, id: e.target.value }))}
                      placeholder="例如：teacher_fast"
                    />
                  </div>
                  <div className="routing-field">
                    <label>名称</label>
                    <input
                      value={channel.title}
                      onChange={(e) => updateChannel(index, (prev) => ({ ...prev, title: e.target.value }))}
                      placeholder="例如：教师快速"
                    />
                  </div>
                  <div className="routing-field">
                    <label>Provider</label>
                    <select
                      value={channel.target.provider}
                      onChange={(e) => {
                        const nextProvider = e.target.value
                        const nextModes = providerModeMap.get(nextProvider) || []
                        const nextMode = nextModes.includes(channel.target.mode) ? channel.target.mode : nextModes[0] || ''
                        updateChannel(index, (prev) => ({
                          ...prev,
                          target: { ...prev.target, provider: nextProvider, mode: nextMode },
                        }))
                      }}
                    >
                      <option value="">请选择</option>
                      {providers.map((provider) => (
                        <option key={provider.provider} value={provider.provider}>
                          {provider.provider}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="routing-field">
                    <label>Mode</label>
                    <select
                      value={channel.target.mode}
                      onChange={(e) =>
                        updateChannel(index, (prev) => ({
                          ...prev,
                          target: { ...prev.target, mode: e.target.value },
                        }))
                      }
                    >
                      <option value="">请选择</option>
                      {modeOptions.map((mode) => (
                        <option key={mode} value={mode}>
                          {mode}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="routing-field">
                    <label>模型</label>
                    <input
                      value={channel.target.model}
                      onChange={(e) =>
                        updateChannel(index, (prev) => ({
                          ...prev,
                          target: { ...prev.target, model: e.target.value },
                        }))
                      }
                      placeholder="例如：deepseek-ai/DeepSeek-V3.2"
                    />
                  </div>
                  <div className="routing-field">
                    <label>temperature</label>
                    <input
                      value={channel.params.temperature ?? ''}
                      onChange={(e) =>
                        updateChannel(index, (prev) => ({
                          ...prev,
                          params: { ...prev.params, temperature: asNumberOrNull(e.target.value) },
                        }))
                      }
                      placeholder="留空表示默认"
                    />
                  </div>
                  <div className="routing-field">
                    <label>max_tokens</label>
                    <input
                      value={channel.params.max_tokens ?? ''}
                      onChange={(e) =>
                        updateChannel(index, (prev) => ({
                          ...prev,
                          params: { ...prev.params, max_tokens: asNumberOrNull(e.target.value) },
                        }))
                      }
                      placeholder="留空表示默认"
                    />
                  </div>
                  <div className="routing-field">
                    <label>回退渠道（逗号分隔）</label>
                    <input
                      value={formatList(channel.fallback_channels || [])}
                      onChange={(e) =>
                        updateChannel(index, (prev) => ({
                          ...prev,
                          fallback_channels: parseList(e.target.value),
                        }))
                      }
                      placeholder="例如：teacher_safe,teacher_backup"
                    />
                  </div>
                  <div className="routing-field">
                    <label>能力</label>
                    <div className="routing-switches">
                      <label className="toggle">
                        <input
                          type="checkbox"
                          checked={channel.capabilities.tools}
                          onChange={(e) =>
                            updateChannel(index, (prev) => ({
                              ...prev,
                              capabilities: { ...prev.capabilities, tools: e.target.checked },
                            }))
                          }
                        />
                        支持工具调用
                      </label>
                      <label className="toggle">
                        <input
                          type="checkbox"
                          checked={channel.capabilities.json}
                          onChange={(e) =>
                            updateChannel(index, (prev) => ({
                              ...prev,
                              capabilities: { ...prev.capabilities, json: e.target.checked },
                            }))
                          }
                        />
                        支持 JSON 输出
                      </label>
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </section>

      <section className="routing-card">
        <div className="routing-section-header">
          <h3>规则配置</h3>
          <button type="button" className="secondary-btn" onClick={addRule} disabled={busy}>
            新增规则
          </button>
        </div>
        <div className="routing-order">命中顺序（按优先级）：{ruleOrderHint || '暂无规则'}</div>
        {draft.rules.length === 0 && <div className="muted">暂无规则，请先新增。</div>}
        <div className="routing-list">
          {draft.rules.map((rule, index) => (
            <div key={`${rule.id}_${index}`} className="routing-item">
              <div className="routing-item-head">
                <strong>{rule.id || `规则${index + 1}`}</strong>
                <button type="button" className="ghost" onClick={() => removeRule(index)} disabled={busy}>
                  删除
                </button>
              </div>
              <div className="routing-grid">
                <div className="routing-field">
                  <label>规则 ID</label>
                  <input
                    value={rule.id}
                    onChange={(e) => updateRule(index, (prev) => ({ ...prev, id: e.target.value }))}
                    placeholder="例如：teacher_agent"
                  />
                </div>
                <div className="routing-field">
                  <label>优先级</label>
                  <input
                    value={rule.priority}
                    onChange={(e) =>
                      updateRule(index, (prev) => ({
                        ...prev,
                        priority: Number.isFinite(Number(e.target.value)) ? Number(e.target.value) : 0,
                      }))
                    }
                  />
                </div>
                <div className="routing-field">
                  <label>启用</label>
                  <label className="toggle">
                    <input
                      type="checkbox"
                      checked={rule.enabled !== false}
                      onChange={(e) => updateRule(index, (prev) => ({ ...prev, enabled: e.target.checked }))}
                    />
                    {rule.enabled !== false ? '启用中' : '已停用'}
                  </label>
                </div>
                <div className="routing-field">
                  <label>角色（逗号分隔）</label>
                  <input
                    value={formatList(rule.match.roles || [])}
                    onChange={(e) =>
                      updateRule(index, (prev) => ({
                        ...prev,
                        match: { ...prev.match, roles: parseList(e.target.value) },
                      }))
                    }
                    placeholder="例如：teacher,student"
                  />
                </div>
                <div className="routing-field">
                  <label>技能 ID（逗号分隔）</label>
                  <input
                    value={formatList(rule.match.skills || [])}
                    onChange={(e) =>
                      updateRule(index, (prev) => ({
                        ...prev,
                        match: { ...prev.match, skills: parseList(e.target.value) },
                      }))
                    }
                    placeholder="例如：physics-homework-generator"
                  />
                </div>
                <div className="routing-field">
                  <label>任务类型 kind（逗号分隔）</label>
                  <input
                    value={formatList(rule.match.kinds || [])}
                    onChange={(e) =>
                      updateRule(index, (prev) => ({
                        ...prev,
                        match: { ...prev.match, kinds: parseList(e.target.value) },
                      }))
                    }
                    placeholder="例如：chat.agent,upload.assignment_parse"
                  />
                </div>
                <div className="routing-field">
                  <label>是否必须工具调用</label>
                  <select
                    value={boolMatchValue(rule.match.needs_tools)}
                    onChange={(e) =>
                      updateRule(index, (prev) => ({
                        ...prev,
                        match: { ...prev.match, needs_tools: boolMatchFromValue(e.target.value) },
                      }))
                    }
                  >
                    <option value="any">不限</option>
                    <option value="true">是</option>
                    <option value="false">否</option>
                  </select>
                </div>
                <div className="routing-field">
                  <label>是否必须 JSON</label>
                  <select
                    value={boolMatchValue(rule.match.needs_json)}
                    onChange={(e) =>
                      updateRule(index, (prev) => ({
                        ...prev,
                        match: { ...prev.match, needs_json: boolMatchFromValue(e.target.value) },
                      }))
                    }
                  >
                    <option value="any">不限</option>
                    <option value="true">是</option>
                    <option value="false">否</option>
                  </select>
                </div>
                <div className="routing-field">
                  <label>目标渠道</label>
                  <select
                    value={rule.route.channel_id || ''}
                    onChange={(e) =>
                      updateRule(index, (prev) => ({
                        ...prev,
                        route: { channel_id: e.target.value },
                      }))
                    }
                  >
                    <option value="">请选择</option>
                    {draft.channels.map((channel) => (
                      <option key={channel.id} value={channel.id}>
                        {channel.id}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="routing-card">
        <h3>仿真验证（基于当前草稿）</h3>
        <div className="routing-grid">
          <div className="routing-field">
            <label>角色</label>
            <input value={simRole} onChange={(e) => setSimRole(e.target.value)} placeholder="teacher" />
          </div>
          <div className="routing-field">
            <label>技能 ID</label>
            <input value={simSkillId} onChange={(e) => setSimSkillId(e.target.value)} placeholder="physics-teacher-ops" />
          </div>
          <div className="routing-field">
            <label>任务类型 kind</label>
            <input value={simKind} onChange={(e) => setSimKind(e.target.value)} placeholder="chat.agent" />
          </div>
          <div className="routing-field">
            <label className="toggle">
              <input type="checkbox" checked={simNeedsTools} onChange={(e) => setSimNeedsTools(e.target.checked)} />
              需要工具调用
            </label>
          </div>
          <div className="routing-field">
            <label className="toggle">
              <input type="checkbox" checked={simNeedsJson} onChange={(e) => setSimNeedsJson(e.target.checked)} />
              需要 JSON
            </label>
          </div>
        </div>
        <div className="routing-actions">
          <button type="button" onClick={handleSimulate} disabled={busy}>
            {busy ? '仿真中…' : '运行仿真'}
          </button>
        </div>
        {simResult && (
          <div className="routing-sim-result">
            <div>命中规则：{simResult.decision?.matched_rule_id || '无'}</div>
            <div>决策原因：{simResult.decision?.reason || '无'}</div>
            <div>候选渠道：{(simResult.decision?.candidates || []).map((item) => item.channel_id).join(' -> ') || '无'}</div>
            {simResult.validation?.errors?.length ? (
              <div className="status err">校验错误：{simResult.validation.errors.join('；')}</div>
            ) : null}
            {simResult.override_validation?.warnings?.length ? (
              <div className="status ok">草稿提示：{simResult.override_validation.warnings.join('；')}</div>
            ) : null}
          </div>
        )}
      </section>

      <section className="routing-card">
        <h3>提案与回滚</h3>
        <div className="routing-grid">
          <div className="routing-field">
            <label>提案备注（可选）</label>
            <input
              value={proposalNote}
              onChange={(e) => setProposalNote(e.target.value)}
              placeholder="例如：作业解析走高稳定模型，聊天走高性价比模型"
            />
          </div>
          <div className="routing-field">
            <label>回滚目标版本</label>
            <input value={rollbackVersion} onChange={(e) => setRollbackVersion(e.target.value)} placeholder="例如：3" />
          </div>
          <div className="routing-field">
            <label>回滚备注（可选）</label>
            <input value={rollbackNote} onChange={(e) => setRollbackNote(e.target.value)} placeholder="例如：线上效果退化，先回退" />
          </div>
        </div>
        <div className="routing-actions">
          <button
            type="button"
            className="secondary-btn"
            onClick={() => {
              const parsed = Number(rollbackVersion)
              void handleRollback(parsed)
            }}
            disabled={busy}
          >
            回滚到指定版本
          </button>
        </div>

        <div className="routing-subsection">
          <h4>待审核提案</h4>
          {pendingProposals.length === 0 ? <div className="muted">暂无待审核提案。</div> : null}
          {pendingProposals.map((proposal) => {
            const proposalId = proposal.proposal_id
            const expanded = Boolean(expandedProposalIds[proposalId])
            const loadingDetail = Boolean(proposalLoadingMap[proposalId])
            const detail = proposalDetails[proposalId]
            const validation = detail?.proposal?.validation
            const errors = Array.isArray(validation?.errors) ? validation?.errors : []
            const warnings = Array.isArray(validation?.warnings) ? validation?.warnings : []
            return (
              <div key={proposalId} className="routing-proposal-block">
                <div className="routing-row">
                  <div className="routing-row-main">
                    <strong>{proposalId}</strong>
                    <span className="muted"> {proposal.created_at}</span>
                    {proposal.note ? <div className="muted">{proposal.note}</div> : null}
                  </div>
                  <div className="routing-row-actions">
                    <button type="button" className="secondary-btn" onClick={() => void handleToggleProposalDetail(proposalId)} disabled={busy}>
                      {expanded ? '收起详情' : '展开详情'}
                    </button>
                    <button type="button" onClick={() => void handleReviewProposal(proposalId, true)} disabled={busy}>
                      生效
                    </button>
                    <button type="button" className="secondary-btn" onClick={() => void handleReviewProposal(proposalId, false)} disabled={busy}>
                      拒绝
                    </button>
                  </div>
                </div>
                {expanded ? (
                  <div className="routing-proposal-detail">
                    {loadingDetail ? <div className="muted">正在加载提案详情…</div> : null}
                    {!loadingDetail && detail?.ok ? (
                      <>
                        <div className="routing-proposal-meta">
                          状态：{String(detail.proposal?.status || proposal.status || 'pending')}
                          {detail.proposal?.created_by ? ` ｜ 创建人：${detail.proposal.created_by}` : ''}
                          {detail.proposal?.reviewed_by ? ` ｜ 审核人：${detail.proposal.reviewed_by}` : ''}
                        </div>
                        {errors.length ? <div className="status err">校验错误：{errors.join('；')}</div> : null}
                        {warnings.length ? <div className="status ok">校验提示：{warnings.join('；')}</div> : null}
                        <details className="routing-proposal-json">
                          <summary>候选配置（JSON）</summary>
                          <pre>{JSON.stringify(detail.proposal?.candidate || {}, null, 2)}</pre>
                        </details>
                      </>
                    ) : null}
                  </div>
                ) : null}
              </div>
            )
          })}
        </div>

        <div className="routing-subsection">
          <h4>历史版本</h4>
          {history.length === 0 ? <div className="muted">暂无历史。</div> : null}
          {history.map((item) => (
            <div key={item.file} className="routing-row">
              <div className="routing-row-main">
                <strong>v{item.version}</strong>
                <span className="muted"> {item.saved_at}</span>
                {item.note ? <div className="muted">{item.note}</div> : null}
              </div>
              <div className="routing-row-actions">
                <button type="button" className="secondary-btn" onClick={() => void handleRollback(item.version)} disabled={busy}>
                  回滚到此版本
                </button>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
