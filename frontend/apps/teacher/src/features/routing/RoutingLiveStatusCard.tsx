type Props = {
  loading: boolean
  liveStatusText: string
  liveStatusTone: 'ok' | 'warn' | 'danger'
  primaryRuleId: string
  primaryChannelLabel: string
  targetModelLabel: string
  versionLabel: string
  updatedAtLabel: string
}

export default function RoutingLiveStatusCard({
  loading,
  liveStatusText,
  liveStatusTone,
  primaryRuleId,
  primaryChannelLabel,
  targetModelLabel,
  versionLabel,
  updatedAtLabel,
}: Props) {
  return (
    <div
      className="routing-current-card border border-[#d9e8e2] rounded-[14px] p-3 grid gap-[10px]"
      style={{ background: 'linear-gradient(135deg, #fcfffe 0%, #f4fbf8 100%)' }}
    >
      <div className="flex items-start justify-between gap-[10px] flex-wrap">
        <div className="grid gap-[2px]">
          <h3 className="m-0">当前生效配置</h3>
          <span className="text-[12px] text-muted">先看结论：当前实际生效的规则、渠道与模型</span>
        </div>
        <span
          className={`inline-flex items-center px-2 py-[3px] rounded-full text-[12px] font-semibold border ${liveStatusTone === 'ok' ? 'bg-[#dcfce7] text-[#166534] border-[#bbf7d0]' : liveStatusTone === 'warn' ? 'bg-[#fff7ed] text-[#9a3412] border-[#fed7aa]' : 'bg-[#fef2f2] text-[#b91c1c] border-[#fecaca]'}`}
        >
          {loading ? '加载中' : liveStatusText}
        </span>
      </div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-2">
        <div className="border border-[#dbe7e2] rounded-[10px] bg-white px-[10px] py-[9px] grid gap-1">
          <span className="text-[12px] text-muted">生效规则</span>
          <strong className="text-[13px] leading-[1.35] break-words">{primaryRuleId || '默认回退'}</strong>
        </div>
        <div className="border border-[#dbe7e2] rounded-[10px] bg-white px-[10px] py-[9px] grid gap-1">
          <span className="text-[12px] text-muted">主渠道</span>
          <strong className="text-[13px] leading-[1.35] break-words">{primaryChannelLabel || '未配置'}</strong>
        </div>
        <div className="border border-[#dbe7e2] rounded-[10px] bg-white px-[10px] py-[9px] grid gap-1">
          <span className="text-[12px] text-muted">目标模型</span>
          <strong className="text-[13px] leading-[1.35] break-words">{targetModelLabel}</strong>
        </div>
        <div className="border border-[#dbe7e2] rounded-[10px] bg-white px-[10px] py-[9px] grid gap-1">
          <span className="text-[12px] text-muted">版本 / 更新时间</span>
          <strong className="text-[13px] leading-[1.35] break-words">
            {versionLabel} / {updatedAtLabel}
          </strong>
        </div>
      </div>
    </div>
  )
}
