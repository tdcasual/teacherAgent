import ModelCombobox from './ModelCombobox'
import type { RoutingCatalogProvider, RoutingChannel, RoutingConfig } from './routingTypes'

type ProviderModelsEntry = {
  models: string[]
  loading: boolean
  error: string
}

type Props = {
  draft: RoutingConfig
  busy: boolean
  providers: RoutingCatalogProvider[]
  providerModeMap: Map<string, string[]>
  modelsMap: Record<string, ProviderModelsEntry | undefined>
  onFetchModels: (providerId: string) => Promise<void> | void
  onAddChannel: () => void
  onRemoveChannel: (index: number) => void
  onUpdateChannel: (index: number, updater: (channel: RoutingChannel) => RoutingChannel) => void
  formatList: (items: string[]) => string
  parseList: (value: string) => string[]
}

const asNumberOrNull = (value: string): number | null => {
  const text = value.trim()
  if (!text) return null
  const num = Number(text)
  return Number.isFinite(num) ? num : null
}

export default function RoutingChannelsSection({
  draft,
  busy,
  providers,
  providerModeMap,
  modelsMap,
  onFetchModels,
  onAddChannel,
  onRemoveChannel,
  onUpdateChannel,
  formatList,
  parseList,
}: Props) {
  return (
    <div className="settings-section">
      <div className="flex items-center justify-between gap-[10px] flex-wrap">
        <h3 className="m-0">渠道配置</h3>
        <button type="button" className="secondary-btn" onClick={onAddChannel} disabled={busy}>
          新增渠道
        </button>
      </div>
      {draft.channels.length === 0 && <div className="muted">暂无渠道，请先新增。</div>}
      <div className="grid gap-[10px]">
        {draft.channels.map((channel, index) => {
          const modeOptions = providerModeMap.get(channel.target.provider) || []
          return (
            <div key={`${channel.id}_${index}`} className="routing-item border border-border rounded-[12px] p-3 bg-white grid gap-[10px] shadow-sm">
              <div className="flex justify-between items-center gap-[10px]">
                <strong>{channel.title || channel.id || `渠道${index + 1}`}</strong>
                <button type="button" className="ghost" onClick={() => onRemoveChannel(index)} disabled={busy}>
                  删除
                </button>
              </div>
              <div className="grid gap-[10px] grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
                <div className="routing-field grid gap-[6px]">
                  <label>名称</label>
                  <input
                    value={channel.title}
                    onChange={(e) => onUpdateChannel(index, (prev) => ({ ...prev, title: e.target.value }))}
                    placeholder="例如：教师快速"
                  />
                </div>
                <div className="routing-field grid gap-[6px]">
                  <label>Provider</label>
                  <select
                    value={channel.target.provider}
                    onChange={(e) => {
                      const nextProvider = e.target.value
                      const nextModes = providerModeMap.get(nextProvider) || []
                      const nextMode = nextModes.includes(channel.target.mode) ? channel.target.mode : nextModes[0] || ''
                      onUpdateChannel(index, (prev) => ({
                        ...prev,
                        target: { ...prev.target, provider: nextProvider, mode: nextMode },
                      }))
                      if (nextProvider) void onFetchModels(nextProvider)
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
                <div className="routing-field grid gap-[6px]">
                  <label>模型</label>
                  <ModelCombobox
                    value={channel.target.model}
                    onChange={(value) =>
                      onUpdateChannel(index, (prev) => ({
                        ...prev,
                        target: { ...prev.target, model: value },
                      }))
                    }
                    models={modelsMap[channel.target.provider]?.models || []}
                    loading={modelsMap[channel.target.provider]?.loading}
                    error={modelsMap[channel.target.provider]?.error}
                    onFocus={() => {
                      if (channel.target.provider) void onFetchModels(channel.target.provider)
                    }}
                  />
                </div>
              </div>
              <details>
                <summary>高级设置</summary>
                <div className="grid gap-[10px] grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
                  <div className="routing-field grid gap-[6px]">
                    <label>渠道 ID</label>
                    <input
                      value={channel.id}
                      onChange={(e) => onUpdateChannel(index, (prev) => ({ ...prev, id: e.target.value }))}
                      placeholder="例如：teacher_fast"
                    />
                  </div>
                  <div className="routing-field grid gap-[6px]">
                    <label>Mode</label>
                    <select
                      value={channel.target.mode}
                      onChange={(e) =>
                        onUpdateChannel(index, (prev) => ({
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
                  <div className="routing-field grid gap-[6px]">
                    <label>temperature</label>
                    <input
                      value={channel.params.temperature ?? ''}
                      onChange={(e) =>
                        onUpdateChannel(index, (prev) => ({
                          ...prev,
                          params: { ...prev.params, temperature: asNumberOrNull(e.target.value) },
                        }))
                      }
                      placeholder="留空表示默认"
                    />
                  </div>
                  <div className="routing-field grid gap-[6px]">
                    <label>max_tokens</label>
                    <input
                      value={channel.params.max_tokens ?? ''}
                      onChange={(e) =>
                        onUpdateChannel(index, (prev) => ({
                          ...prev,
                          params: { ...prev.params, max_tokens: asNumberOrNull(e.target.value) },
                        }))
                      }
                      placeholder="留空表示默认"
                    />
                  </div>
                  <div className="routing-field grid gap-[6px]">
                    <label>回退渠道（逗号分隔）</label>
                    <input
                      value={formatList(channel.fallback_channels || [])}
                      onChange={(e) =>
                        onUpdateChannel(index, (prev) => ({
                          ...prev,
                          fallback_channels: parseList(e.target.value),
                        }))
                      }
                      placeholder="例如：teacher_safe,teacher_backup"
                    />
                  </div>
                  <div className="routing-field grid gap-[6px]">
                    <label>能力</label>
                    <div className="flex flex-col gap-[6px]">
                      <label className="toggle">
                        <input
                          type="checkbox"
                          checked={channel.capabilities.tools}
                          onChange={(e) =>
                            onUpdateChannel(index, (prev) => ({
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
                            onUpdateChannel(index, (prev) => ({
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
              </details>
            </div>
          )
        })}
      </div>
    </div>
  )
}
