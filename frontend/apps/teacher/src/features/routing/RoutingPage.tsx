import { useEffect, useMemo, useState } from 'react'
import { useRoutingDraftActions } from './useRoutingDraftActions'
import { useRoutingOverviewSync } from './useRoutingOverviewSync'
import { useRoutingProviderMutations } from './useRoutingProviderMutations'
import { useRoutingProposalActions } from './useRoutingProposalActions'
import { useProviderModels } from './useProviderModels'
import RoutingChannelsSection from './RoutingChannelsSection'
import RoutingHistorySection from './RoutingHistorySection'
import RoutingProvidersSection from './RoutingProvidersSection'
import RoutingRulesSection from './RoutingRulesSection'
import RoutingSimulateSection from './RoutingSimulateSection'
import type {
  RoutingCatalogProvider,
  RoutingConfig,
  RoutingHistoryItem,
  RoutingHistorySummary,
  RoutingOverview,
  TeacherProviderRegistryOverview,
  RoutingProposalDetail,
  RoutingSimulateResult,
} from './routingTypes'
import { emptyRoutingConfig } from './routingTypes'
import { safeLocalStorageGetItem, safeLocalStorageSetItem } from '../../utils/storage'

export type RoutingSection = 'general' | 'providers' | 'channels' | 'rules' | 'simulate' | 'history'

type Props = {
  apiBase: string
  onApiBaseChange?: (value: string) => void
  onDirtyChange?: (dirty: boolean) => void
  /** When provided, only render this section (no tab bar, no page chrome) */
  section?: RoutingSection
  /** Legacy compatibility mode: render all routing/provider panels in one page */
  legacyFlat?: boolean
}

const parseList = (value: string) =>
  value
    .split(/[，,\n]+/)
    .map((item) => item.trim())
    .filter(Boolean)

const formatList = (items: string[]) => items.join('，')

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

const formatTargetLabel = (provider?: string, mode?: string, model?: string) => {
  const text = [provider || '', mode || '', model || ''].map((item) => item.trim()).filter(Boolean).join(' / ')
  return text || '未配置'
}

const asRecord = (value: unknown): Record<string, unknown> | null => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  return value as Record<string, unknown>
}

const asPriority = (value: unknown) => {
  const num = Number(value)
  return Number.isFinite(num) ? num : 0
}

const deriveHistorySummary = (item: RoutingHistoryItem): RoutingHistorySummary | null => {
  if (item.summary) return item.summary
  const config = asRecord(item.config)
  if (!config) return null

  const channels = (Array.isArray(config.channels) ? config.channels : [])
    .map((entry) => asRecord(entry))
    .filter((entry): entry is Record<string, unknown> => Boolean(entry))
  const rules = (Array.isArray(config.rules) ? config.rules : [])
    .map((entry) => asRecord(entry))
    .filter((entry): entry is Record<string, unknown> => Boolean(entry))

  const primaryChannel = channels[0] || null
  const primaryTarget = asRecord(primaryChannel?.target) || {}
  const topRule = [...rules].sort((left, right) => asPriority(right.priority) - asPriority(left.priority))[0] || null

  return {
    enabled: Boolean(config.enabled),
    channel_count: channels.length,
    rule_count: rules.length,
    primary_channel_id: String(primaryChannel?.id || ''),
    primary_channel_title: String(primaryChannel?.title || ''),
    primary_provider: String(primaryTarget.provider || ''),
    primary_mode: String(primaryTarget.mode || ''),
    primary_model: String(primaryTarget.model || ''),
    top_rule_id: String(topRule?.id || ''),
  }
}

const buildHistoryChangeSummary = (current: RoutingHistorySummary | null, previous: RoutingHistorySummary | null) => {
  if (!current) return ['无结构化变更数据，请查看配置 JSON。']
  if (!previous) return ['首个保留版本，暂无可对比基线。']

  const changes: string[] = []
  if (current.primary_model !== previous.primary_model) {
    changes.push(`模型切换：${previous.primary_model || '未配置'} → ${current.primary_model || '未配置'}`)
  }
  if (current.primary_channel_id !== previous.primary_channel_id) {
    changes.push(`主渠道变更：${previous.primary_channel_id || '未配置'} → ${current.primary_channel_id || '未配置'}`)
  }
  if (current.top_rule_id !== previous.top_rule_id) {
    changes.push(`主规则变更：${previous.top_rule_id || '未配置'} → ${current.top_rule_id || '未配置'}`)
  }
  if (current.rule_count !== previous.rule_count) {
    changes.push(`规则数量：${previous.rule_count} → ${current.rule_count}`)
  }
  if (current.channel_count !== previous.channel_count) {
    changes.push(`渠道数量：${previous.channel_count} → ${current.channel_count}`)
  }
  if (current.enabled !== previous.enabled) {
    changes.push(`路由状态：${previous.enabled ? '启用' : '关闭'} → ${current.enabled ? '启用' : '关闭'}`)
  }
  if (!changes.length) changes.push('路由结构未变化，主要为备注或时间更新。')
  return changes
}

export default function RoutingPage({ apiBase, onApiBaseChange, onDirtyChange, section, legacyFlat }: Props) {
  const isLegacyFlat = Boolean(legacyFlat)
  const activeTab = section || 'general'
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
  const [showManualReview, setShowManualReview] = useState(() => safeLocalStorageGetItem('teacherRoutingManualReview') === '1')
  const [showHistoryVersions, setShowHistoryVersions] = useState(() => safeLocalStorageGetItem('teacherRoutingHistoryExpanded') === '1')
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
    Record<string, { display_name: string; base_url: string; enabled: boolean; api_key: string; default_model: string }>
  >({})
  const [providerAddMode, setProviderAddMode] = useState<'' | 'preset' | 'custom'>('')
  const [providerAddPreset, setProviderAddPreset] = useState('')

  const { modelsMap, fetchModels } = useProviderModels(apiBase, teacherId)

  useEffect(() => {
    onDirtyChange?.(hasLocalEdits)
  }, [hasLocalEdits, onDirtyChange])

  useEffect(() => {
    safeLocalStorageSetItem('teacherRoutingTeacherId', teacherId)
  }, [teacherId])

  useEffect(() => {
    safeLocalStorageSetItem('teacherRoutingManualReview', showManualReview ? '1' : '0')
  }, [showManualReview])

  useEffect(() => {
    safeLocalStorageSetItem('teacherRoutingHistoryExpanded', showHistoryVersions ? '1' : '0')
  }, [showHistoryVersions])

  useEffect(() => {
    setExpandedProposalIds({})
    setProposalDetails({})
    setProposalLoadingMap({})
  }, [teacherId])

  const { loadOverview } = useRoutingOverviewSync({
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
  })
  const {
    handleCreateProvider,
    handleUpdateProvider,
    handleDisableProvider,
    handleProbeProviderModels,
  } = useRoutingProviderMutations({
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
  })

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
  const {
    setDraftWithEdit,
    handleTeacherIdChange,
    addChannel,
    removeChannel,
    updateChannel,
    addRule,
    removeRule,
    updateRule,
    handleResetDraft,
  } = useRoutingDraftActions({
    teacherId,
    hasLocalEdits,
    draft,
    overview,
    providers,
    providerModeMap,
    cloneConfig,
    setTeacherId,
    setDraft,
    setHasLocalEdits,
    setStatus,
    setError,
  })
  const {
    handleSimulate,
    handlePropose,
    handleReviewProposal,
    handleToggleProposalDetail,
    handleRollback,
  } = useRoutingProposalActions({
    apiBase,
    teacherId,
    isLegacyFlat,
    draft,
    proposalNote,
    rollbackNote,
    simRole,
    simSkillId,
    simKind,
    simNeedsTools,
    simNeedsJson,
    expandedProposalIds,
    proposalDetails,
    proposalLoadingMap,
    loadOverview,
    setBusy,
    setStatus,
    setError,
    setSimResult,
    setProposalNote,
    setShowManualReview,
    setExpandedProposalIds,
    setProposalDetails,
    setProposalLoadingMap,
    setRollbackVersion,
    setRollbackNote,
  })

  // Auto-probe models when channels tab is active (only configured providers)
  useEffect(() => {
    if (activeTab !== 'channels') return
    const configuredProviders = new Set(
      (providerOverview?.providers || []).map((p) => p.provider),
    )
    const seen = new Set<string>()
    for (const ch of draft.channels) {
      const p = ch.target?.provider
      if (p && !seen.has(p) && configuredProviders.has(p)) {
        seen.add(p)
        void fetchModels(p)
      }
    }
  }, [activeTab]) // eslint-disable-line react-hooks/exhaustive-deps

  const pendingProposals = (overview?.proposals || []).filter((item) => item.status === 'pending')
  const history = useMemo(() => overview?.history || [], [overview?.history])

  const liveRouting = overview?.routing || null
  const liveEnabledRules = useMemo(
    () =>
      [...(liveRouting?.rules || [])]
        .filter((rule) => rule.enabled !== false)
        .sort((left, right) => (right.priority || 0) - (left.priority || 0)),
    [liveRouting?.rules],
  )
  const livePrimaryRule = liveEnabledRules[0] || null
  const livePrimaryChannel = useMemo(() => {
    const channels = liveRouting?.channels || []
    const routedChannelId = livePrimaryRule?.route?.channel_id || ''
    if (routedChannelId) {
      const matched = channels.find((channel) => channel.id === routedChannelId)
      if (matched) return matched
    }
    return channels[0] || null
  }, [livePrimaryRule?.route?.channel_id, liveRouting?.channels])

  const liveStatusText = overview?.validation?.errors?.length
    ? '配置异常'
    : hasLocalEdits
      ? '草稿未生效'
      : '已生效'
  const liveStatusTone = overview?.validation?.errors?.length ? 'danger' : hasLocalEdits ? 'warn' : 'ok'

  const historyRows = useMemo(
    () =>
      history.map((item, index) => {
        const currentSummary = deriveHistorySummary(item)
        const previousSummary = history[index + 1] ? deriveHistorySummary(history[index + 1]) : null
        return {
          item,
          summary: currentSummary,
          changes: buildHistoryChangeSummary(currentSummary, previousSummary),
        }
      }),
    [history],
  )

  const ruleOrderHint = draft.rules
    .slice()
    .sort((a, b) => (b.priority || 0) - (a.priority || 0))
    .map((rule) => `${rule.id || '未命名'}(${rule.priority})`)
    .join(' -> ')

  return (
    <div className="routing-page grid gap-3">
      {isLegacyFlat && <h2>模型路由配置</h2>}
      {status && <div className="status ok">{status}</div>}
      {error && <div className="status err">{error}</div>}

      <div className="routing-current-card border border-[#d9e8e2] rounded-[14px] p-3 grid gap-[10px]" style={{ background: 'linear-gradient(135deg, #fcfffe 0%, #f4fbf8 100%)' }}>
        <div className="flex items-start justify-between gap-[10px] flex-wrap">
          <div className="grid gap-[2px]">
            <h3 className="m-0">当前生效配置</h3>
            <span className="text-[12px] text-muted">先看结论：当前实际生效的规则、渠道与模型</span>
          </div>
          <span className={`inline-flex items-center px-2 py-[3px] rounded-full text-[12px] font-semibold border ${liveStatusTone === 'ok' ? 'bg-[#dcfce7] text-[#166534] border-[#bbf7d0]' : liveStatusTone === 'warn' ? 'bg-[#fff7ed] text-[#9a3412] border-[#fed7aa]' : 'bg-[#fef2f2] text-[#b91c1c] border-[#fecaca]'}`}>{loading ? '加载中' : liveStatusText}</span>
        </div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-2">
          <div className="border border-[#dbe7e2] rounded-[10px] bg-white px-[10px] py-[9px] grid gap-1">
            <span className="text-[12px] text-muted">生效规则</span>
            <strong className="text-[13px] leading-[1.35] break-words">{livePrimaryRule?.id || '默认回退'}</strong>
          </div>
          <div className="border border-[#dbe7e2] rounded-[10px] bg-white px-[10px] py-[9px] grid gap-1">
            <span className="text-[12px] text-muted">主渠道</span>
            <strong className="text-[13px] leading-[1.35] break-words">{livePrimaryChannel?.title || livePrimaryChannel?.id || '未配置'}</strong>
          </div>
          <div className="border border-[#dbe7e2] rounded-[10px] bg-white px-[10px] py-[9px] grid gap-1">
            <span className="text-[12px] text-muted">目标模型</span>
            <strong className="text-[13px] leading-[1.35] break-words">
              {formatTargetLabel(
                livePrimaryChannel?.target?.provider,
                livePrimaryChannel?.target?.mode,
                livePrimaryChannel?.target?.model,
              )}
            </strong>
          </div>
          <div className="border border-[#dbe7e2] rounded-[10px] bg-white px-[10px] py-[9px] grid gap-1">
            <span className="text-[12px] text-muted">版本 / 更新时间</span>
            <strong className="text-[13px] leading-[1.35] break-words">
              v{liveRouting?.version || '-'} / {liveRouting?.updated_at || '—'}
            </strong>
          </div>
        </div>
      </div>

      {(activeTab === 'general' || isLegacyFlat) && (
        <div className="settings-section">
          <div className="grid gap-[10px] grid-cols-[repeat(auto-fit,minmax(180px,1fr))]">
            <div className="grid gap-[6px]">
              <label>API Base</label>
              <input
                value={apiBase}
                onChange={(e) => onApiBaseChange?.(e.target.value)}
                placeholder="http://localhost:8000"
              />
            </div>
            <div className="grid gap-[6px]">
              <label>教师标识（可选）</label>
              <input value={teacherId} onChange={(e) => handleTeacherIdChange(e.target.value)} placeholder="默认 teacher" />
            </div>
            <div className="grid gap-[6px]">
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
          </div>
          <div className="flex gap-4 flex-wrap text-[12px] text-muted">
            <span>线上版本：{overview?.routing?.version ?? '-'}</span>
            <span>草稿规则：{draft.rules.length} 条</span>
            <span>草稿渠道：{draft.channels.length} 个</span>
            <span>最后更新：{overview?.routing?.updated_at || '—'}</span>
          </div>
          {hasLocalEdits && <div className="status ok">当前为本地草稿，尚未保存生效。</div>}
          {overview?.validation?.errors?.length ? (
            <div className="status err">线上配置校验错误：{overview.validation.errors.join('；')}</div>
          ) : null}
          {overview?.validation?.warnings?.length ? (
            <div className="status ok">线上配置提示：{overview.validation.warnings.join('；')}</div>
          ) : null}
          <div className="flex gap-2 flex-wrap">
            <button type="button" className="secondary-btn" onClick={() => void loadOverview()} disabled={loading || busy}>
              {loading ? '刷新中…' : '刷新'}
            </button>
          </div>
        </div>
      )}

      {(activeTab === 'providers' || isLegacyFlat) && (
        <RoutingProvidersSection
          isLegacyFlat={isLegacyFlat}
          providerOverview={providerOverview}
          providerEditMap={providerEditMap}
          providerProbeMap={providerProbeMap}
          providerCreateForm={providerCreateForm}
          providerAddMode={providerAddMode}
          providerAddPreset={providerAddPreset}
          providerBusy={providerBusy}
          busy={busy}
          setProviderEditMap={setProviderEditMap}
          setProviderCreateForm={setProviderCreateForm}
          setProviderAddMode={setProviderAddMode}
          setProviderAddPreset={setProviderAddPreset}
          onCreateProvider={() => {
            void handleCreateProvider()
          }}
          onUpdateProvider={(providerId) => {
            void handleUpdateProvider(providerId)
          }}
          onDisableProvider={(providerId) => {
            void handleDisableProvider(providerId)
          }}
          onProbeProviderModels={(providerId) => {
            void handleProbeProviderModels(providerId)
          }}
        />
      )}

      {(activeTab === 'channels' || isLegacyFlat) && (
        <RoutingChannelsSection
          draft={draft}
          busy={busy}
          providers={providers}
          providerModeMap={providerModeMap}
          modelsMap={modelsMap}
          onFetchModels={fetchModels}
          onAddChannel={addChannel}
          onRemoveChannel={removeChannel}
          onUpdateChannel={updateChannel}
          formatList={formatList}
          parseList={parseList}
        />
      )}

      {(activeTab === 'rules' || isLegacyFlat) && (
        <RoutingRulesSection
          draft={draft}
          busy={busy}
          ruleOrderHint={ruleOrderHint}
          onAddRule={addRule}
          onRemoveRule={removeRule}
          onUpdateRule={updateRule}
          formatList={formatList}
          parseList={parseList}
          boolMatchValue={boolMatchValue}
          boolMatchFromValue={boolMatchFromValue}
        />
      )}

      {(activeTab === 'simulate' || isLegacyFlat) && (
        <RoutingSimulateSection
          isLegacyFlat={isLegacyFlat}
          busy={busy}
          simRole={simRole}
          simSkillId={simSkillId}
          simKind={simKind}
          simNeedsTools={simNeedsTools}
          simNeedsJson={simNeedsJson}
          simResult={simResult}
          onSimRoleChange={setSimRole}
          onSimSkillIdChange={setSimSkillId}
          onSimKindChange={setSimKind}
          onSimNeedsToolsChange={setSimNeedsTools}
          onSimNeedsJsonChange={setSimNeedsJson}
          onSimulate={() => {
            void handleSimulate()
          }}
          formatTargetLabel={formatTargetLabel}
        />
      )}

      {(activeTab === 'history' || isLegacyFlat) && (
        <RoutingHistorySection
          isLegacyFlat={isLegacyFlat}
          busy={busy}
          rollbackVersion={rollbackVersion}
          rollbackNote={rollbackNote}
          pendingProposals={pendingProposals}
          showManualReview={showManualReview}
          expandedProposalIds={expandedProposalIds}
          proposalLoadingMap={proposalLoadingMap}
          proposalDetails={proposalDetails}
          showHistoryVersions={showHistoryVersions}
          history={history}
          historyRows={historyRows}
          formatTargetLabel={formatTargetLabel}
          onRollbackVersionChange={setRollbackVersion}
          onRollbackNoteChange={setRollbackNote}
          onRollback={(targetVersion) => {
            void handleRollback(targetVersion)
          }}
          onToggleManualReview={() => setShowManualReview((prev) => !prev)}
          onToggleProposalDetail={(proposalId) => {
            void handleToggleProposalDetail(proposalId)
          }}
          onReviewProposal={(proposalId, approve) => {
            void handleReviewProposal(proposalId, approve)
          }}
          onToggleHistoryVersions={() => setShowHistoryVersions((prev) => !prev)}
        />
      )}

      {(!isLegacyFlat && ['general', 'providers', 'channels', 'rules'].includes(activeTab)) && (
        <div className="sticky bottom-0 flex items-center justify-between gap-3 px-[14px] py-[10px] border-t border-border rounded-[12px] z-[5]" style={{ background: 'rgba(255,255,255,0.94)', backdropFilter: 'saturate(180%) blur(8px)' }}>
          <div className="flex items-center gap-[10px] flex-1 min-w-0">
            {hasLocalEdits && <span className="text-[12px] text-accent font-semibold whitespace-nowrap">草稿已修改</span>}
            <input
              className="max-w-[280px] px-[10px] py-[7px] text-[13px]"
              value={proposalNote}
              onChange={(e) => setProposalNote(e.target.value)}
              placeholder="变更备注（可选）"
            />
          </div>
          <div className="flex gap-2 flex-shrink-0">
            <button type="button" className="secondary-btn" onClick={handleResetDraft} disabled={!hasLocalEdits || busy}>
              重置草稿
            </button>
            <button type="button" className="secondary-btn" onClick={handlePropose} disabled={busy}>
              {busy ? '处理中…' : '保存并生效'}
            </button>
          </div>
        </div>
      )}

      {isLegacyFlat && (
        <div className="sticky bottom-0 flex items-center justify-between gap-3 px-[14px] py-[10px] border-t border-border rounded-[12px] z-[5]" style={{ background: 'rgba(255,255,255,0.94)', backdropFilter: 'saturate(180%) blur(8px)' }}>
          <div className="flex items-center gap-[10px] flex-1 min-w-0">
            {hasLocalEdits && <span className="text-[12px] text-accent font-semibold whitespace-nowrap">草稿已修改</span>}
            <input
              className="max-w-[280px] px-[10px] py-[7px] text-[13px]"
              value={proposalNote}
              onChange={(e) => setProposalNote(e.target.value)}
              placeholder="变更备注（可选）"
            />
          </div>
          <div className="flex gap-2 flex-shrink-0">
            <button type="button" className="secondary-btn" onClick={handlePropose} disabled={busy}>
              {busy ? '处理中…' : '提交提案'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
