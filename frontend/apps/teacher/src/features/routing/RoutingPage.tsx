import { useEffect, useMemo, useState } from 'react'
import { useRoutingDraftActions } from './useRoutingDraftActions'
import { useRoutingOverviewSync } from './useRoutingOverviewSync'
import { useRoutingProviderMutations } from './useRoutingProviderMutations'
import { useRoutingProposalActions } from './useRoutingProposalActions'
import { useProviderModels } from './useProviderModels'
import { cloneConfig } from './routingConfigUtils'
import { boolMatchFromValue, boolMatchValue, formatList, formatTargetLabel, parseList } from './routingFormattingUtils'
import { buildHistoryChangeSummary, deriveHistorySummary } from './routingHistoryUtils'
import RoutingChannelsSection from './RoutingChannelsSection'
import RoutingDraftActionBar from './RoutingDraftActionBar'
import RoutingHistorySection from './RoutingHistorySection'
import RoutingLiveStatusCard from './RoutingLiveStatusCard'
import RoutingProvidersSection from './RoutingProvidersSection'
import RoutingRulesSection from './RoutingRulesSection'
import RoutingSimulateSection from './RoutingSimulateSection'
import type {
  RoutingCatalogProvider,
  RoutingConfig,
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

      <RoutingLiveStatusCard
        loading={loading}
        liveStatusText={liveStatusText}
        liveStatusTone={liveStatusTone}
        primaryRuleId={livePrimaryRule?.id || ''}
        primaryChannelLabel={livePrimaryChannel?.title || livePrimaryChannel?.id || ''}
        targetModelLabel={formatTargetLabel(
          livePrimaryChannel?.target?.provider,
          livePrimaryChannel?.target?.mode,
          livePrimaryChannel?.target?.model,
        )}
        versionLabel={`v${liveRouting?.version || '-'}`}
        updatedAtLabel={liveRouting?.updated_at || '—'}
      />

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
        <RoutingDraftActionBar
          isLegacyFlat={false}
          hasLocalEdits={hasLocalEdits}
          busy={busy}
          proposalNote={proposalNote}
          onProposalNoteChange={setProposalNote}
          onResetDraft={handleResetDraft}
          onPropose={handlePropose}
        />
      )}

      {isLegacyFlat && (
        <RoutingDraftActionBar
          isLegacyFlat
          hasLocalEdits={hasLocalEdits}
          busy={busy}
          proposalNote={proposalNote}
          onProposalNoteChange={setProposalNote}
          onResetDraft={handleResetDraft}
          onPropose={handlePropose}
        />
      )}
    </div>
  )
}
