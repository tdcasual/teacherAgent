import type { RoutingConfig, RoutingRule } from './routingTypes'

type Props = {
  draft: RoutingConfig
  busy: boolean
  ruleOrderHint: string
  onAddRule: () => void
  onRemoveRule: (index: number) => void
  onUpdateRule: (index: number, updater: (rule: RoutingRule) => RoutingRule) => void
  formatList: (items: string[]) => string
  parseList: (value: string) => string[]
  boolMatchValue: (value: boolean | null | undefined) => string
  boolMatchFromValue: (value: string) => boolean | undefined
}

export default function RoutingRulesSection({
  draft,
  busy,
  ruleOrderHint,
  onAddRule,
  onRemoveRule,
  onUpdateRule,
  formatList,
  parseList,
  boolMatchValue,
  boolMatchFromValue,
}: Props) {
  return (
    <div className="settings-section">
      <div className="flex items-center justify-between gap-[10px] flex-wrap">
        <h3 className="m-0">规则配置</h3>
        <button type="button" className="secondary-btn" onClick={onAddRule} disabled={busy}>
          新增规则
        </button>
      </div>
      <div className="text-[12px] text-muted">命中顺序（按优先级）：{ruleOrderHint || '暂无规则'}</div>
      {draft.rules.length === 0 && <div className="muted">暂无规则，请先新增。</div>}
      <div className="grid gap-[10px]">
        {draft.rules.map((rule, index) => {
          const channelTitle = draft.channels.find((c) => c.id === rule.route.channel_id)?.title || rule.route.channel_id || '未指定'
          return (
            <div key={`${rule.id}_${index}`} className={`routing-item rule-card ${rule.enabled !== false ? 'rule-enabled' : 'rule-disabled'}`}>
              <div className="flex items-center gap-2 px-3 py-[10px] text-[13px]">
                <label className="toggle flex-shrink-0">
                  <input
                    type="checkbox"
                    checked={rule.enabled !== false}
                    onChange={(e) => onUpdateRule(index, (prev) => ({ ...prev, enabled: e.target.checked }))}
                  />
                </label>
                <span className="font-semibold text-ink whitespace-nowrap">{rule.id || `规则${index + 1}`}</span>
                <span className="text-muted flex-1 min-w-0 overflow-hidden text-ellipsis whitespace-nowrap">
                  {formatList(rule.match.roles || []) || '所有角色'} → {channelTitle}
                </span>
                <span className="text-[11px] text-muted bg-surface-soft px-[6px] py-[2px] rounded flex-shrink-0">P{rule.priority}</span>
                <button type="button" className="ghost" onClick={() => onRemoveRule(index)} disabled={busy}>
                  删除
                </button>
              </div>
              <details>
                <summary>编辑规则</summary>
                <div className="grid gap-[10px] grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
                  <div className="grid gap-[6px]">
                    <label>规则 ID</label>
                    <input
                      value={rule.id}
                      onChange={(e) => onUpdateRule(index, (prev) => ({ ...prev, id: e.target.value }))}
                      placeholder="例如：teacher_agent"
                    />
                  </div>
                  <div className="grid gap-[6px]">
                    <label>优先级</label>
                    <input
                      value={rule.priority}
                      onChange={(e) =>
                        onUpdateRule(index, (prev) => ({
                          ...prev,
                          priority: Number.isFinite(Number(e.target.value)) ? Number(e.target.value) : 0,
                        }))
                      }
                    />
                  </div>
                  <div className="grid gap-[6px]">
                    <label>角色（逗号分隔）</label>
                    <input
                      value={formatList(rule.match.roles || [])}
                      onChange={(e) =>
                        onUpdateRule(index, (prev) => ({
                          ...prev,
                          match: { ...prev.match, roles: parseList(e.target.value) },
                        }))
                      }
                      placeholder="例如：teacher,student"
                    />
                  </div>
                  <div className="grid gap-[6px]">
                    <label>目标渠道</label>
                    <select
                      value={rule.route.channel_id || ''}
                      onChange={(e) =>
                        onUpdateRule(index, (prev) => ({
                          ...prev,
                          route: { channel_id: e.target.value },
                        }))
                      }
                    >
                      <option value="">请选择</option>
                      {draft.channels.map((channel) => (
                        <option key={channel.id} value={channel.id}>
                          {channel.title || channel.id}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="grid gap-[6px]">
                    <label>技能 ID（逗号分隔）</label>
                    <input
                      value={formatList(rule.match.skills || [])}
                      onChange={(e) =>
                        onUpdateRule(index, (prev) => ({
                          ...prev,
                          match: { ...prev.match, skills: parseList(e.target.value) },
                        }))
                      }
                      placeholder="例如：physics-homework-generator"
                    />
                  </div>
                  <div className="grid gap-[6px]">
                    <label>任务类型 kind（逗号分隔）</label>
                    <input
                      value={formatList(rule.match.kinds || [])}
                      onChange={(e) =>
                        onUpdateRule(index, (prev) => ({
                          ...prev,
                          match: { ...prev.match, kinds: parseList(e.target.value) },
                        }))
                      }
                      placeholder="例如：chat.agent,upload.assignment_parse"
                    />
                  </div>
                  <div className="grid gap-[6px]">
                    <label>是否必须工具调用</label>
                    <select
                      value={boolMatchValue(rule.match.needs_tools)}
                      onChange={(e) =>
                        onUpdateRule(index, (prev) => ({
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
                  <div className="grid gap-[6px]">
                    <label>是否必须 JSON</label>
                    <select
                      value={boolMatchValue(rule.match.needs_json)}
                      onChange={(e) =>
                        onUpdateRule(index, (prev) => ({
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
                </div>
              </details>
            </div>
          )
        })}
      </div>
    </div>
  )
}
