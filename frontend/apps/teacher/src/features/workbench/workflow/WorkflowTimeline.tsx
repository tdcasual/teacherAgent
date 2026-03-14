import type { ExecutionTimelineEntry } from '../../../appTypes'

type WorkflowTimelineProps = {
  entries: ExecutionTimelineEntry[]
}

const timelineTone = (entry: ExecutionTimelineEntry): 'error' | 'neutral' => {
  const text = `${entry.type} ${entry.summary}`.toLowerCase()
  return text.includes('failed') || text.includes('error') || text.includes('失败') || text.includes('异常')
    ? 'error'
    : 'neutral'
}

const toTimestampValue = (value?: string) => {
  if (!value) return Number.NEGATIVE_INFINITY
  const parsed = Date.parse(value)
  return Number.isNaN(parsed) ? Number.NEGATIVE_INFINITY : parsed
}

const formatTimelineTimestamp = (value?: string) => {
  if (!value) return ''
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

export default function WorkflowTimeline({ entries }: WorkflowTimelineProps) {
  const sortedEntries = [...entries].sort((left, right) => toTimestampValue(right.ts) - toTimestampValue(left.ts))

  return (
    <section className="rounded-[14px] border border-border bg-surface p-[10px] shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <strong>最近一次执行</strong>
        <span className="text-[12px] text-muted">{sortedEntries.length} 个节点</span>
      </div>

      {sortedEntries.length ? (
        <div className="mt-[8px] grid gap-[6px]">
          {sortedEntries.map((item, index) => {
            const tone = timelineTone(item)
            return (
              <div
                key={`${item.type}-${item.ts || index}`}
                data-testid="workflow-timeline-item"
                data-tone={tone}
                className={`rounded-[10px] border px-[10px] py-[8px] text-[12px] ${
                  tone === 'error'
                    ? 'border-[#f1b8b8] bg-[#fff4f4]'
                    : index === 0
                      ? 'border-[color:var(--color-accent)] bg-[color:var(--color-accent-soft)]'
                      : 'border-border bg-white'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="font-medium text-[#334155]">{item.summary}</div>
                  {item.ts ? <span className="shrink-0 text-[11px] text-muted">{formatTimelineTimestamp(item.ts)}</span> : null}
                </div>
                <div className="mt-[2px] text-muted">{item.type}</div>
              </div>
            )
          })}
        </div>
      ) : (
        <div className="mt-[8px] rounded-[10px] border border-dashed border-border bg-white px-[10px] py-[12px]">
          <div className="text-[12px] font-medium text-[#334155]">暂无执行记录</div>
          <div className="mt-[2px] text-[12px] text-muted">
            先从上传区开始今天流程，系统会在这里持续回显解析与审核节点。
          </div>
        </div>
      )}
    </section>
  )
}
