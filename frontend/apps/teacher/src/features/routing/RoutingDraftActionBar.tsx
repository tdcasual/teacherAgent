type Props = {
  isLegacyFlat: boolean
  hasLocalEdits: boolean
  busy: boolean
  proposalNote: string
  onProposalNoteChange: (value: string) => void
  onResetDraft: () => void
  onPropose: () => void
}

export default function RoutingDraftActionBar({
  isLegacyFlat,
  hasLocalEdits,
  busy,
  proposalNote,
  onProposalNoteChange,
  onResetDraft,
  onPropose,
}: Props) {
  return (
    <div
      className="sticky bottom-0 flex items-center justify-between gap-3 px-[14px] py-[10px] border-t border-border rounded-[12px] z-[5]"
      style={{ background: 'rgba(255,255,255,0.94)', backdropFilter: 'saturate(180%) blur(8px)' }}
    >
      <div className="flex items-center gap-[10px] flex-1 min-w-0">
        {hasLocalEdits && <span className="text-[12px] text-accent font-semibold whitespace-nowrap">草稿已修改</span>}
        <input
          className="max-w-[280px] px-[10px] py-[7px] text-[13px]"
          value={proposalNote}
          onChange={(e) => onProposalNoteChange(e.target.value)}
          placeholder="变更备注（可选）"
        />
      </div>
      <div className="flex gap-2 flex-shrink-0">
        {!isLegacyFlat && (
          <button type="button" className="secondary-btn" onClick={onResetDraft} disabled={!hasLocalEdits || busy}>
            重置草稿
          </button>
        )}
        <button type="button" className="secondary-btn" onClick={onPropose} disabled={busy}>
          {busy ? '处理中…' : isLegacyFlat ? '提交提案' : '保存并生效'}
        </button>
      </div>
    </div>
  )
}
