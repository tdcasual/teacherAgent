import type {
  RoutingHistoryItem,
  RoutingHistorySummary,
  RoutingProposalDetail,
  RoutingProposalItem,
} from './routingTypes'

type RoutingHistoryRow = {
  item: RoutingHistoryItem
  summary: RoutingHistorySummary | null
  changes: string[]
}

type Props = {
  isLegacyFlat: boolean
  busy: boolean
  rollbackVersion: string
  rollbackNote: string
  pendingProposals: RoutingProposalItem[]
  showManualReview: boolean
  expandedProposalIds: Record<string, boolean>
  proposalLoadingMap: Record<string, boolean>
  proposalDetails: Record<string, RoutingProposalDetail>
  showHistoryVersions: boolean
  history: RoutingHistoryItem[]
  historyRows: RoutingHistoryRow[]
  formatTargetLabel: (provider?: string, mode?: string, model?: string) => string
  onRollbackVersionChange: (value: string) => void
  onRollbackNoteChange: (value: string) => void
  onRollback: (targetVersion: number) => void
  onToggleManualReview: () => void
  onToggleProposalDetail: (proposalId: string) => void
  onReviewProposal: (proposalId: string, approve: boolean) => void
  onToggleHistoryVersions: () => void
}

export default function RoutingHistorySection({
  isLegacyFlat,
  busy,
  rollbackVersion,
  rollbackNote,
  pendingProposals,
  showManualReview,
  expandedProposalIds,
  proposalLoadingMap,
  proposalDetails,
  showHistoryVersions,
  history,
  historyRows,
  formatTargetLabel,
  onRollbackVersionChange,
  onRollbackNoteChange,
  onRollback,
  onToggleManualReview,
  onToggleProposalDetail,
  onReviewProposal,
  onToggleHistoryVersions,
}: Props) {
  return (
    <div className="settings-section">
      <h3>提案与回滚</h3>
      <div className="grid gap-[10px] grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
        <div className="grid gap-[6px]">
          <label>回滚目标版本</label>
          <input value={rollbackVersion} onChange={(e) => onRollbackVersionChange(e.target.value)} placeholder="例如：3" />
        </div>
        <div className="grid gap-[6px]">
          <label>回滚备注（可选）</label>
          <input value={rollbackNote} onChange={(e) => onRollbackNoteChange(e.target.value)} placeholder="例如：线上效果退化，先回退" />
        </div>
      </div>
      <div className="flex gap-2 flex-wrap">
        <button
          type="button"
          className="secondary-btn"
          onClick={() => {
            const parsed = Number(rollbackVersion)
            onRollback(parsed)
          }}
          disabled={busy}
        >
          回滚到指定版本
        </button>
      </div>

      <div className="routing-subsection grid gap-2">
        <div className="flex items-center justify-between gap-[10px] flex-wrap">
          <h4 className="m-0">待审核提案（高级）</h4>
          {!isLegacyFlat && (
            <button type="button" className="ghost" onClick={onToggleManualReview} disabled={busy}>
              {showManualReview ? '收起' : `展开${pendingProposals.length ? `（${pendingProposals.length}）` : ''}`}
            </button>
          )}
        </div>
        {!showManualReview && !isLegacyFlat ? (
          <div className="muted">
            单管理员模式默认自动生效，仅在需要处理历史遗留提案时再展开手动审核。
            {pendingProposals.length ? ` 当前有 ${pendingProposals.length} 条待审核提案。` : ''}
          </div>
        ) : (
          <>
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
                <div key={proposalId} className="grid gap-2">
                  <div className="border border-border rounded-[12px] bg-white p-[10px] flex justify-between gap-[10px] items-center max-[900px]:flex-col max-[900px]:items-start">
                    <div className="grid gap-1 text-[13px]">
                      <strong>{proposalId}</strong>
                      <span className="muted"> {proposal.created_at}</span>
                      {proposal.note ? <div className="muted">{proposal.note}</div> : null}
                    </div>
                    <div className="flex gap-2 flex-wrap">
                      <button type="button" className="secondary-btn" onClick={() => onToggleProposalDetail(proposalId)} disabled={busy}>
                        {expanded ? '收起详情' : '展开详情'}
                      </button>
                      <button type="button" className="secondary-btn" onClick={() => onReviewProposal(proposalId, true)} disabled={busy}>
                        生效
                      </button>
                      <button type="button" className="secondary-btn" onClick={() => onReviewProposal(proposalId, false)} disabled={busy}>
                        拒绝
                      </button>
                    </div>
                  </div>
                  {expanded ? (
                    <div className="border border-dashed border-border rounded-[12px] bg-white p-[10px] grid gap-2">
                      {loadingDetail ? <div className="muted">正在加载提案详情…</div> : null}
                      {!loadingDetail && detail?.ok ? (
                        <>
                          <div className="text-[12px] text-muted">
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
          </>
        )}
      </div>

      <div className="routing-subsection grid gap-2">
        <div className="flex items-center justify-between gap-[10px] flex-wrap">
          <h4 className="m-0">历史版本（最近10次）</h4>
          <button type="button" className="ghost" onClick={onToggleHistoryVersions} disabled={busy}>
            {showHistoryVersions ? '收起' : `展开${history.length ? `（${history.length}）` : ''}`}
          </button>
        </div>
        {!showHistoryVersions ? (
          <div className="muted">
            默认折叠历史版本以保持界面简洁，按需展开查看或回滚。
            {history.length ? ` 当前有 ${history.length} 条历史记录。` : ''}
          </div>
        ) : (
          <>
            {history.length === 0 ? <div className="muted">暂无历史。</div> : null}
            {historyRows.map(({ item, summary, changes }) => (
              <div key={item.file} className="grid gap-2">
                <div className="border border-border rounded-[12px] bg-white p-[10px] flex justify-between gap-[10px] items-center max-[900px]:flex-col max-[900px]:items-start">
                  <div className="grid gap-1 text-[13px]">
                    <strong>v{item.version}</strong>
                    <span className="muted"> {item.saved_at}</span>
                    <div className="flex gap-3 flex-wrap text-[12px] text-muted">
                      <span>
                        主模型：
                        {formatTargetLabel(summary?.primary_provider, summary?.primary_mode, summary?.primary_model)}
                      </span>
                      <span>规则 {summary?.rule_count ?? '-'} · 渠道 {summary?.channel_count ?? '-'}</span>
                    </div>
                    <div className="text-[12px] text-ink font-semibold">变更摘要</div>
                    <div className="grid gap-1">
                      {changes.map((change, index) => (
                        <div key={`${item.file}_${index}`} className="text-[12px] text-muted">{change}</div>
                      ))}
                    </div>
                    {item.note ? <div className="muted">备注：{item.note}</div> : null}
                  </div>
                  <div className="flex gap-2 flex-wrap">
                    <button type="button" className="secondary-btn" onClick={() => onRollback(item.version)} disabled={busy}>
                      回滚到此版本
                    </button>
                  </div>
                </div>
                <details className="routing-proposal-json">
                  <summary>查看配置 JSON</summary>
                  <pre>{JSON.stringify(item.config || { summary: summary || null, source: item.source, saved_by: item.saved_by }, null, 2)}</pre>
                </details>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  )
}
