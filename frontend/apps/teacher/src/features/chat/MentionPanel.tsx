import type { InvocationTriggerType } from './invocation'

type MentionOption = {
  id: string
  title: string
  desc: string
  type: InvocationTriggerType
}

type MentionState = {
  type: InvocationTriggerType
  items: MentionOption[]
}

type Props = {
  mention: MentionState | null
  mentionIndex: number
  onInsert: (item: MentionOption) => void
}

export default function MentionPanel({ mention, mentionIndex, onInsert }: Props) {
  if (!mention || mention.items.length === 0) return null
  return (
    <div className="mention-panel">
      <div className="mention-title">
        {mention.type === 'agent' ? 'Agent 建议（↑↓ 选择 / 回车插入）' : '技能建议（↑↓ 选择 / 回车插入）'}
      </div>
      <div className="mention-list">
        {mention.items.map((item, index) => (
          <button
            key={`${item.type}:${item.id}`}
            type="button"
            className={index === mentionIndex ? 'active' : ''}
            onClick={() => onInsert(item)}
          >
            <strong>{item.type === 'agent' ? `@${item.id}` : `$${item.id}`}</strong>
            <span>{item.title}</span>
            {item.desc ? <span className="muted">{item.desc}</span> : null}
          </button>
        ))}
      </div>
    </div>
  )
}
