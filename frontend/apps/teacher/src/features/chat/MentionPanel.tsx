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
    <div className="mention-panel border border-dashed border-border rounded-[14px] px-[10px] py-2 bg-[#fbf6ee]">
      <div className="text-[12px] text-muted mb-2">技能建议（↑↓ 选择 / 回车插入）</div>
      <div className="grid gap-2">
        {mention.items.map((item, index) => (
          <button
            key={`${item.type}:${item.id}`}
            type="button"
            className={`text-left px-[10px] py-2 rounded-[10px] bg-white cursor-pointer flex gap-2 items-baseline border ${
              index === mentionIndex
                ? 'border-accent bg-[#e8f3f1]'
                : 'border-transparent'
            }`}
            onClick={() => onInsert(item)}
          >
            <strong className="text-accent">{`$${item.id}`}</strong>
            <span>{item.title}</span>
            {item.desc ? <span className="text-muted">{item.desc}</span> : null}
          </button>
        ))}
      </div>
    </div>
  )
}
