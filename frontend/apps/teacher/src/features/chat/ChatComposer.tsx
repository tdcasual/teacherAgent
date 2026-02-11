import type { FormEvent, KeyboardEvent, MutableRefObject } from 'react'

type Props = {
  activeSkillId: string
  skillPinned: boolean
  input: string
  pendingChatJob: boolean
  sending: boolean
  chatQueueHint: string
  composerWarning: string
  inputRef: MutableRefObject<HTMLTextAreaElement | null>
  onSubmit: (event: FormEvent) => void
  onInputChange: (value: string, selectionStart: number) => void
  onInputClick: (selectionStart: number) => void
  onInputKeyUp: (selectionStart: number) => void
  onInputKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void
}

export default function ChatComposer({
  activeSkillId,
  skillPinned,
  input,
  pendingChatJob,
  sending,
  chatQueueHint,
  composerWarning,
  inputRef,
  onSubmit,
  onInputChange,
  onInputClick,
  onInputKeyUp,
  onInputKeyDown,
}: Props) {
  return (
    <form className="relative z-[2] px-4 pt-[10px] pb-[14px] border-t border-border bg-gradient-to-t from-surface from-70% to-transparent" onSubmit={onSubmit}>
      <div className="w-full max-w-[var(--chat-content-max-width)] border border-border bg-white rounded-[12px] px-3 py-[10px] shadow-sm grid gap-[10px]">
        <div className="flex flex-wrap gap-2">
          <span className="inline-flex items-center border border-border rounded-lg px-2 py-[2px] text-[11px] text-[#4b5563] bg-[#f8fafc]">
            {skillPinned ? `技能: $${activeSkillId || 'physics-teacher-ops'}` : '技能: 自动路由'}
          </span>
        </div>
        <textarea
          ref={inputRef}
          className="border-none bg-transparent px-[2px] py-0 shadow-none resize-none min-h-[56px] max-h-[220px] overflow-auto focus:border-none focus:shadow-none focus:outline-none focus:ring-0"
          value={input}
          onChange={(e) => onInputChange(e.target.value, e.target.selectionStart || e.target.value.length)}
          onClick={(e) => onInputClick((e.target as HTMLTextAreaElement).selectionStart || input.length)}
          onKeyUp={(e) => onInputKeyUp((e.target as HTMLTextAreaElement).selectionStart || input.length)}
          onKeyDown={onInputKeyDown}
          placeholder="输入指令或问题，使用 $ 查看技能。回车发送，上档键+回车换行"
          rows={3}
          disabled={pendingChatJob}
        />
        <div className="flex justify-between items-center gap-3">
          <span className="text-[12px] text-muted">{chatQueueHint || '$ 技能 | 回车发送'}</span>
          <button
            type="submit"
            className="border-none rounded-[12px] px-4 py-[10px] text-[14px] cursor-pointer bg-accent text-white disabled:opacity-60 disabled:cursor-not-allowed"
            disabled={sending || pendingChatJob}
          >
            发送
          </button>
        </div>
        {composerWarning ? <div className="status err">{composerWarning}</div> : null}
      </div>
    </form>
  )
}
