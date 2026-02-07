import type { FormEvent, KeyboardEvent, MutableRefObject } from 'react'

type Props = {
  activeAgentId: string
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
  activeAgentId,
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
    <form className="composer" onSubmit={onSubmit}>
      <div className="composer-inner">
        <div className="composer-context">
          <span className="chip">{`Agent: @${activeAgentId || 'default'}`}</span>
          <span className="chip">
            {skillPinned ? `技能: $${activeSkillId || 'physics-teacher-ops'}` : '技能: 自动路由'}
          </span>
        </div>
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => onInputChange(e.target.value, e.target.selectionStart || e.target.value.length)}
          onClick={(e) => onInputClick((e.target as HTMLTextAreaElement).selectionStart || input.length)}
          onKeyUp={(e) => onInputKeyUp((e.target as HTMLTextAreaElement).selectionStart || input.length)}
          onKeyDown={onInputKeyDown}
          placeholder="输入指令或问题，使用 @ 查看 Agent、$ 查看技能。回车发送，上档键+回车换行"
          rows={3}
          disabled={pendingChatJob}
        />
        <div className="composer-actions">
          <span className="composer-hint">{chatQueueHint || '@ Agent | $ 技能 | 回车发送'}</span>
          <button type="submit" className="send-btn" disabled={sending || pendingChatJob}>
            发送
          </button>
        </div>
        {composerWarning ? <div className="status err">{composerWarning}</div> : null}
      </div>
    </form>
  )
}
