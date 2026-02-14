import type { Dispatch, SetStateAction } from 'react'
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

type ProviderAddMode = '' | 'preset' | 'custom'

type Props = {
  isLegacyFlat: boolean
  providerOverview: TeacherProviderRegistryOverview | null
  providerEditMap: Record<string, ProviderEditForm>
  providerProbeMap: Record<string, string>
  providerCreateForm: ProviderCreateForm
  providerAddMode: ProviderAddMode
  providerAddPreset: string
  providerBusy: boolean
  busy: boolean
  setProviderEditMap: Dispatch<SetStateAction<Record<string, ProviderEditForm>>>
  setProviderCreateForm: Dispatch<SetStateAction<ProviderCreateForm>>
  setProviderAddMode: Dispatch<SetStateAction<ProviderAddMode>>
  setProviderAddPreset: Dispatch<SetStateAction<string>>
  onCreateProvider: () => void
  onUpdateProvider: (providerId: string) => void
  onDisableProvider: (providerId: string) => void
  onProbeProviderModels: (providerId: string) => void
}

export default function RoutingProvidersSection({
  isLegacyFlat,
  providerOverview,
  providerEditMap,
  providerProbeMap,
  providerCreateForm,
  providerAddMode,
  providerAddPreset,
  providerBusy,
  busy,
  setProviderEditMap,
  setProviderCreateForm,
  setProviderAddMode,
  setProviderAddPreset,
  onCreateProvider,
  onUpdateProvider,
  onDisableProvider,
  onProbeProviderModels,
}: Props) {
  return (
    <div className="settings-section">
      <div className="flex items-center justify-between gap-[10px] flex-wrap">
        <h3 className="m-0">{isLegacyFlat ? 'Provider 管理（共享 + 私有）' : 'Provider 管理'}</h3>
      </div>

      {isLegacyFlat && (providerOverview?.providers || []).length === 0 && (
        <div className="muted">暂无私有 Provider。</div>
      )}

      <div className="flex flex-col gap-2">
        {(providerOverview?.providers || []).length === 0 && (
          <div className="muted" style={{ padding: '12px 0' }}>尚未配置任何 Provider，请在下方添加。</div>
        )}
        {(providerOverview?.providers || []).map((item) => {
          const cp = (providerOverview?.catalog?.providers || []).find((c) => c.provider === item.provider)
          const edit = providerEditMap[item.provider] || {
            display_name: item.display_name || item.provider,
            base_url: item.base_url || '',
            enabled: item.enabled !== false,
            api_key: '',
            default_model: item.default_model || '',
          }
          return (
            <details key={item.provider} open={isLegacyFlat} className={isLegacyFlat ? 'routing-item border border-border rounded-[12px] p-3 bg-white grid gap-[10px] shadow-sm provider-row' : 'routing-item provider-row'}>
              <summary className="flex items-center gap-2 px-[14px] py-3 cursor-pointer text-[13px] list-none select-none [&::-webkit-details-marker]:hidden">
                <span className="w-2 h-2 rounded-full flex-shrink-0 bg-[#22c55e]" />
                <span className="font-semibold whitespace-nowrap">{item.display_name || item.provider}</span>
                <span className="muted">{item.provider}</span>
                <span className="text-muted text-[12px] flex-1 overflow-hidden text-ellipsis whitespace-nowrap">
                  {(cp?.modes || []).map((m) => m.mode).join(', ')}
                  {cp?.modes?.[0]?.default_model ? ` · ${cp.modes[0].default_model}` : ''}
                </span>
                <span className="text-[11px] px-[6px] py-[1px] rounded bg-[#dcfce7] text-[#166534] whitespace-nowrap">已配置</span>
                {item.api_key_masked && <span className="text-[11px] font-mono whitespace-nowrap text-muted">key: {item.api_key_masked}</span>}
              </summary>
              <div className="px-[14px] pb-[14px] flex flex-col gap-[10px]">
                <div className={isLegacyFlat ? 'border border-border rounded-[12px] p-3 bg-white shadow-sm grid gap-[10px] grid-cols-[repeat(auto-fit,minmax(220px,1fr))]' : 'grid gap-[10px] grid-cols-[repeat(auto-fit,minmax(220px,1fr))]'}>
                  <div className="routing-field grid gap-[6px]">
                    <label>显示名称</label>
                    <input value={edit.display_name} onChange={(e) => setProviderEditMap((prev) => ({ ...prev, [item.provider]: { ...edit, display_name: e.target.value } }))} placeholder={item.provider} />
                  </div>
                  <div className="routing-field grid gap-[6px]">
                    <label>Base URL</label>
                    <input value={edit.base_url} onChange={(e) => setProviderEditMap((prev) => ({ ...prev, [item.provider]: { ...edit, base_url: e.target.value } }))} placeholder="留空使用系统默认" />
                  </div>
                  <div className="routing-field grid gap-[6px]">
                    <label>轮换 API Key（可选）</label>
                    <input type="password" autoComplete="new-password" value={edit.api_key} onChange={(e) => setProviderEditMap((prev) => ({ ...prev, [item.provider]: { ...edit, api_key: e.target.value } }))} placeholder="轮换 API Key（可选）" />
                  </div>
                  <div className="routing-field grid gap-[6px]">
                    <label>默认模型</label>
                    <input
                      value={edit.default_model}
                      onChange={(e) => setProviderEditMap((prev) => ({ ...prev, [item.provider]: { ...edit, default_model: e.target.value } }))}
                      placeholder="例如：gpt-4.1-mini"
                    />
                  </div>
                  <div className="routing-field grid gap-[6px]">
                    <label className="toggle">
                      <input type="checkbox" checked={edit.enabled} onChange={(e) => setProviderEditMap((prev) => ({ ...prev, [item.provider]: { ...edit, enabled: e.target.checked } }))} />
                      启用
                    </label>
                  </div>
                </div>
                <div className="flex gap-[6px] flex-wrap">
                  <button type="button" className="secondary-btn" onClick={() => onUpdateProvider(item.provider)} disabled={providerBusy || busy}>保存</button>
                  <button type="button" className="secondary-btn" onClick={() => onProbeProviderModels(item.provider)} disabled={providerBusy || busy}>探测模型</button>
                  <button type="button" className="ghost" onClick={() => onDisableProvider(item.provider)} disabled={providerBusy || busy}>禁用</button>
                </div>
                {providerProbeMap[item.provider] ? <div className="flex items-baseline gap-[6px] flex-wrap text-[12px]">探测结果：{providerProbeMap[item.provider]}</div> : null}
              </div>
            </details>
          )
        })}
      </div>

      <div className="mt-4 border border-dashed border-[#c9d7d2] rounded-[12px] p-[14px] bg-[#fcfffe]">
        <div className="font-semibold text-[13px] mb-[10px]">添加 Provider</div>
        {providerAddMode === '' && (
          <div className="flex flex-wrap gap-2">
            {(() => {
              const configuredIds = new Set((providerOverview?.providers || []).map((p) => p.provider))
              const presets = (providerOverview?.shared_catalog?.providers || []).filter(
                (p) => !configuredIds.has(p.provider),
              )
              return (
                <>
                  {presets.map((p) => (
                    <button
                      key={p.provider}
                      type="button"
                      className="px-[14px] py-2 border border-border rounded-[12px] bg-white text-[13px] cursor-pointer font-medium transition-all duration-150 hover:border-accent hover:bg-accent-soft hover:text-accent"
                      onClick={() => {
                        setProviderAddMode('preset')
                        setProviderAddPreset(p.provider)
                        setProviderCreateForm({
                          provider_id: p.provider,
                          display_name: p.provider,
                          base_url: '',
                          api_key: '',
                          default_model: '',
                          enabled: true,
                        })
                      }}
                    >
                      {p.provider}
                    </button>
                  ))}
                  {!isLegacyFlat && (
                    <button
                      type="button"
                      className="px-[14px] py-2 border border-dashed border-border rounded-[12px] bg-white text-[13px] cursor-pointer font-medium text-muted transition-all duration-150 hover:border-accent hover:bg-accent-soft hover:text-accent"
                      onClick={() => {
                        setProviderAddMode('custom')
                        setProviderAddPreset('')
                        setProviderCreateForm({
                          provider_id: '',
                          display_name: '',
                          base_url: '',
                          api_key: '',
                          default_model: '',
                          enabled: true,
                        })
                      }}
                    >
                      OpenAI 兼容（自定义）
                    </button>
                  )}
                </>
              )
            })()}
          </div>
        )}

        {isLegacyFlat && providerAddMode === '' && (
          <div className="flex flex-col gap-[10px]">
            <div className="flex items-center justify-between font-semibold text-[13px]">新增私有 Provider</div>
            <div className="grid gap-[10px] grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
              <div className="grid gap-[6px]">
                <label>Provider ID（必填）</label>
                <input value={providerCreateForm.provider_id} onChange={(e) => setProviderCreateForm((prev) => ({ ...prev, provider_id: e.target.value }))} placeholder="例如：tprv_proxy_main" />
              </div>
              <div className="grid gap-[6px]">
                <label>显示名称（可选）</label>
                <input value={providerCreateForm.display_name} onChange={(e) => setProviderCreateForm((prev) => ({ ...prev, display_name: e.target.value }))} placeholder="例如：主中转" />
              </div>
              <div className="grid gap-[6px]">
                <label>Base URL（必填）</label>
                <input value={providerCreateForm.base_url} onChange={(e) => setProviderCreateForm((prev) => ({ ...prev, base_url: e.target.value }))} placeholder="例如：https://proxy.example.com/v1" />
              </div>
              <div className="grid gap-[6px]">
                <label>API Key（必填）</label>
                <input type="password" autoComplete="new-password" value={providerCreateForm.api_key} onChange={(e) => setProviderCreateForm((prev) => ({ ...prev, api_key: e.target.value }))} placeholder="仅提交时可见，后续仅显示掩码" />
              </div>
              <div className="grid gap-[6px]">
                <label>默认模型（可选）</label>
                <input
                  value={providerCreateForm.default_model}
                  onChange={(e) => setProviderCreateForm((prev) => ({ ...prev, default_model: e.target.value }))}
                  placeholder="例如：gpt-4.1-mini"
                />
              </div>
            </div>
            <div className="flex gap-[6px] flex-wrap">
              <button type="button" className="secondary-btn" onClick={onCreateProvider} disabled={providerBusy || busy}>{providerBusy ? '处理中…' : '新增 Provider'}</button>
            </div>
          </div>
        )}

        {providerAddMode === 'preset' && (
          <div className="flex flex-col gap-[10px]">
            <div className="flex items-center justify-between font-semibold text-[13px]">
              配置 {providerAddPreset}
              <button type="button" className="ghost" onClick={() => { setProviderAddMode(''); setProviderAddPreset('') }}>取消</button>
            </div>
            <div className="grid gap-[10px] grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
              <div className="grid gap-[6px]">
                <label>API Key（必填）</label>
                <input type="password" autoComplete="new-password" value={providerCreateForm.api_key} onChange={(e) => setProviderCreateForm((prev) => ({ ...prev, api_key: e.target.value }))} placeholder="输入 API Key" />
              </div>
              <div className="grid gap-[6px]">
                <label>Base URL（可选）</label>
                <input
                  value={providerCreateForm.base_url}
                  onChange={(e) => setProviderCreateForm((prev) => ({ ...prev, base_url: e.target.value }))}
                  placeholder={(() => {
                    const cat = (providerOverview?.shared_catalog?.providers || []).find((p) => p.provider === providerAddPreset)
                    return cat?.base_url || '使用默认地址'
                  })()}
                />
              </div>
              <div className="grid gap-[6px]">
                <label>显示名称（可选）</label>
                <input value={providerCreateForm.display_name} onChange={(e) => setProviderCreateForm((prev) => ({ ...prev, display_name: e.target.value }))} placeholder={providerAddPreset} />
              </div>
              <div className="grid gap-[6px]">
                <label>默认模型（可选）</label>
                <input
                  value={providerCreateForm.default_model}
                  onChange={(e) => setProviderCreateForm((prev) => ({ ...prev, default_model: e.target.value }))}
                  placeholder="例如：gpt-4.1-mini"
                />
              </div>
            </div>
            <div className="flex gap-[6px] flex-wrap">
              <button type="button" className="secondary-btn" onClick={onCreateProvider} disabled={providerBusy || busy}>{providerBusy ? '处理中…' : '新增 Provider'}</button>
            </div>
          </div>
        )}

        {providerAddMode === 'custom' && (
          <div className="flex flex-col gap-[10px]">
            <div className="flex items-center justify-between font-semibold text-[13px]">
              自定义 Provider
              <button type="button" className="ghost" onClick={() => { setProviderAddMode(''); setProviderAddPreset('') }}>取消</button>
            </div>
            <div className="grid gap-[10px] grid-cols-[repeat(auto-fit,minmax(220px,1fr))]">
              <div className="grid gap-[6px]">
                <label>Provider ID（必填）</label>
                <input value={providerCreateForm.provider_id} onChange={(e) => setProviderCreateForm((prev) => ({ ...prev, provider_id: e.target.value }))} placeholder="例如：my_proxy" />
              </div>
              <div className="grid gap-[6px]">
                <label>Base URL（必填）</label>
                <input value={providerCreateForm.base_url} onChange={(e) => setProviderCreateForm((prev) => ({ ...prev, base_url: e.target.value }))} placeholder="https://api.example.com/v1" />
              </div>
              <div className="grid gap-[6px]">
                <label>API Key（必填）</label>
                <input type="password" autoComplete="new-password" value={providerCreateForm.api_key} onChange={(e) => setProviderCreateForm((prev) => ({ ...prev, api_key: e.target.value }))} />
              </div>
              <div className="grid gap-[6px]">
                <label>显示名称（可选）</label>
                <input value={providerCreateForm.display_name} onChange={(e) => setProviderCreateForm((prev) => ({ ...prev, display_name: e.target.value }))} placeholder="例如：主中转" />
              </div>
              <div className="grid gap-[6px]">
                <label>默认模型（可选）</label>
                <input
                  value={providerCreateForm.default_model}
                  onChange={(e) => setProviderCreateForm((prev) => ({ ...prev, default_model: e.target.value }))}
                  placeholder="例如：gpt-4.1-mini"
                />
              </div>
            </div>
            <div className="flex gap-[6px] flex-wrap">
              <button type="button" className="secondary-btn" onClick={onCreateProvider} disabled={providerBusy || busy}>{providerBusy ? '处理中…' : '新增 Provider'}</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
