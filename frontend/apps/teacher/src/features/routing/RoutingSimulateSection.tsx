import type { RoutingSimulateResult } from './routingTypes'

type Props = {
  isLegacyFlat: boolean
  busy: boolean
  simRole: string
  simSkillId: string
  simKind: string
  simNeedsTools: boolean
  simNeedsJson: boolean
  simResult: RoutingSimulateResult | null
  onSimRoleChange: (value: string) => void
  onSimSkillIdChange: (value: string) => void
  onSimKindChange: (value: string) => void
  onSimNeedsToolsChange: (value: boolean) => void
  onSimNeedsJsonChange: (value: boolean) => void
  onSimulate: () => void
  formatTargetLabel: (provider?: string, mode?: string, model?: string) => string
}

export default function RoutingSimulateSection({
  isLegacyFlat,
  busy,
  simRole,
  simSkillId,
  simKind,
  simNeedsTools,
  simNeedsJson,
  simResult,
  onSimRoleChange,
  onSimSkillIdChange,
  onSimKindChange,
  onSimNeedsToolsChange,
  onSimNeedsJsonChange,
  onSimulate,
  formatTargetLabel,
}: Props) {
  const simCandidates = simResult?.decision?.candidates || []
  const simPrimaryCandidate = simCandidates[0] || null

  return (
    <div className="settings-section routing-sim-panel">
      <h3>仿真验证（基于当前草稿）</h3>
      <div className="grid gap-[10px] grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
        <div className="grid gap-[6px]">
          <label>角色</label>
          <input value={simRole} onChange={(e) => onSimRoleChange(e.target.value)} placeholder="teacher" />
        </div>
        <div className="grid gap-[6px]">
          <label>技能 ID</label>
          <input value={simSkillId} onChange={(e) => onSimSkillIdChange(e.target.value)} placeholder="physics-teacher-ops" />
        </div>
        <div className="grid gap-[6px]">
          <label>任务类型 kind</label>
          <input value={simKind} onChange={(e) => onSimKindChange(e.target.value)} placeholder="chat.agent" />
        </div>
        <div className="grid gap-[6px]">
          <label className="toggle">
            <input type="checkbox" checked={simNeedsTools} onChange={(e) => onSimNeedsToolsChange(e.target.checked)} />
            需要工具调用
          </label>
        </div>
        <div className="grid gap-[6px]">
          <label className="toggle">
            <input type="checkbox" checked={simNeedsJson} onChange={(e) => onSimNeedsJsonChange(e.target.checked)} />
            需要 JSON
          </label>
        </div>
      </div>
      <div className="flex gap-2 flex-wrap">
        <button type="button" className="secondary-btn" onClick={onSimulate} disabled={busy}>
          {busy ? '仿真中…' : '运行仿真'}
        </button>
      </div>
      {simResult && (
        <div className="grid gap-[10px]">
          <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-[10px]">
            <div className="border border-[#cde5de] rounded-[12px] p-[10px] bg-[#fcfffe] grid gap-2">
              <h4 className="m-0 text-[13px]">仿真结论</h4>
              <div className="flex justify-between items-baseline gap-[10px] text-[13px]">
                <span className="text-muted">命中规则</span>
                <strong className="text-right break-words">{simResult.decision?.matched_rule_id || '未命中，走默认回退'}</strong>
              </div>
              {isLegacyFlat && (
                <div className="flex justify-between items-baseline gap-[10px] text-[13px]">
                  <span className="text-muted">{`命中规则：${simResult.decision?.matched_rule_id || '未命中，走默认回退'}`}</span>
                </div>
              )}
              <div className="flex justify-between items-baseline gap-[10px] text-[13px]">
                <span className="text-muted">目标模型</span>
                <strong className="text-right break-words">
                  {formatTargetLabel(simPrimaryCandidate?.provider, simPrimaryCandidate?.mode, simPrimaryCandidate?.model)}
                </strong>
              </div>
              {isLegacyFlat && (
                <div className="flex justify-between items-baseline gap-[10px] text-[13px]">
                  <span className="text-muted">{`候选渠道：${simPrimaryCandidate?.channel_id || '无'}`}</span>
                </div>
              )}
              <div className="flex justify-between items-baseline gap-[10px] text-[13px]">
                <span className="text-muted">决策状态</span>
                <strong className="text-right break-words">{simResult.decision?.selected ? '已选出候选链路' : '未选出候选链路'}</strong>
              </div>
            </div>
            <div className="border border-border rounded-[12px] p-[10px] bg-white grid gap-2">
              <h4 className="m-0 text-[13px]">决策原因</h4>
              <p className="m-0 text-[13px] text-ink leading-[1.45]">{simResult.decision?.reason || '无可用原因信息'}</p>
            </div>
          </div>

          <details className="border border-border rounded-[12px] p-[10px] bg-white grid gap-2 [&>summary]:cursor-pointer [&>summary]:text-accent [&>summary]:select-none">
            <summary>候选链路（{simCandidates.length}）</summary>
            {simCandidates.length === 0 ? (
              <div className="muted">无候选渠道。</div>
            ) : (
              <div className="grid gap-2">
                {simCandidates.map((candidate, index) => (
                  <div key={`${candidate.channel_id}_${index}`} className="border border-dashed border-border rounded-[10px] p-2 grid gap-1">
                    <div className="text-[12px] text-muted">#{index + 1} · {candidate.channel_id || '未命名渠道'}</div>
                    <div className="text-[13px] text-ink break-words">
                      {formatTargetLabel(candidate.provider, candidate.mode, candidate.model)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </details>

          {simResult.validation?.errors?.length ? (
            <div className="status err">校验错误：{simResult.validation.errors.join('；')}</div>
          ) : null}
          {simResult.validation?.warnings?.length ? (
            <div className="status ok">线上配置提示：{simResult.validation.warnings.join('；')}</div>
          ) : null}
          {simResult.override_validation?.errors?.length ? (
            <div className="status err">草稿校验错误：{simResult.override_validation.errors.join('；')}</div>
          ) : null}
          {simResult.override_validation?.warnings?.length ? (
            <div className="status ok">草稿提示：{simResult.override_validation.warnings.join('；')}</div>
          ) : null}

          <details className="routing-proposal-json">
            <summary>技术详情 JSON</summary>
            <pre>{JSON.stringify(simResult, null, 2)}</pre>
          </details>
        </div>
      )}
    </div>
  )
}
