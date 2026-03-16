import { useEffect, useMemo, useState, type MutableRefObject } from 'react'
import type { PendingToolRun } from '../../appTypes'

type RenderedMessage = {
  id: string
  role: 'user' | 'assistant'
  html: string
  time: string
}

type Props = {
  renderedMessages: RenderedMessage[]
  sending: boolean
  hasPendingChatJob: boolean
  typingTimeLabel: string
  messagesRef: MutableRefObject<HTMLDivElement | null>
  onMessagesScroll: () => void
  showScrollToBottom: boolean
  onScrollToBottom: () => void
  pendingStreamStage: string
  pendingToolRuns: PendingToolRun[]
}

export default function ChatMessages({
  renderedMessages,
  sending,
  hasPendingChatJob,
  typingTimeLabel,
  messagesRef,
  onMessagesScroll,
  showScrollToBottom,
  onScrollToBottom,
  pendingStreamStage,
  pendingToolRuns,
}: Props) {
  const [processCollapsed, setProcessCollapsed] = useState(false)
  const [showOnlyFailed, setShowOnlyFailed] = useState(false)

  const runningCount = pendingToolRuns.filter((item) => item.status === 'running').length
  const okCount = pendingToolRuns.filter((item) => item.status === 'ok').length
  const failedCount = pendingToolRuns.filter((item) => item.status === 'failed').length

  const visibleToolRuns = useMemo(() => {
    if (!showOnlyFailed) return pendingToolRuns
    return pendingToolRuns.filter((item) => item.status === 'failed')
  }, [pendingToolRuns, showOnlyFailed])

  useEffect(() => {
    if (hasPendingChatJob) return
    setProcessCollapsed(false)
    setShowOnlyFailed(false)
  }, [hasPendingChatJob])

  return (
    <>
      <div
        className="messages flex-1 min-h-0 overflow-auto bg-transparent pt-3 pb-[8px]"
        style={{ overscrollBehavior: 'contain' }}
        ref={messagesRef}
        onScroll={onMessagesScroll}
      >
        <div className="w-full max-w-[var(--chat-content-max-width)] px-6 pb-[16px] grid gap-[14px]">
          {renderedMessages.map((msg) => (
            <div key={msg.id} className={`message ${msg.role} flex ${msg.role === 'user' ? 'justify-end' : ''}`}>
              <div
                className={
                  msg.role === 'assistant'
                    ? 'max-w-[var(--chat-assistant-bubble-max-width)] rounded-[18px] border border-[color:color-mix(in_oklab,var(--color-accent)_14%,white)] bg-[color:color-mix(in_oklab,var(--color-panel)_92%,white)] px-[14px] py-[12px] shadow-[0_8px_18px_rgba(15,23,42,0.05)]'
                    : 'max-w-[var(--chat-bubble-max-width)] rounded-[14px] border border-[color:color-mix(in_oklab,var(--color-border)_84%,white)] bg-[color:color-mix(in_oklab,var(--color-surface-soft)_90%,white)] px-[14px] py-[10px] shadow-none'
                }
              >
                <div className="text-[11px] text-muted mb-1">
                  {msg.role === 'user' ? '我的指令' : '执行结果'} · {msg.time}
                </div>
                <div className="text leading-[1.4] max-[900px]:leading-[1.32] whitespace-normal break-words markdown" dangerouslySetInnerHTML={{ __html: msg.html }} />
              </div>
            </div>
          ))}
          {sending && !hasPendingChatJob && (
            <div className="flex">
              <div className="max-w-[var(--chat-assistant-bubble-max-width)] rounded-[16px] border border-dashed border-[color:color-mix(in_oklab,var(--color-accent)_16%,white)] bg-[color:color-mix(in_oklab,var(--color-accent-soft)_34%,white)] py-2.5 px-3">
                <div className="text-[11px] text-muted mb-1">助手 · {typingTimeLabel}</div>
                <div className="leading-[1.4] max-[900px]:leading-[1.32] whitespace-normal break-words">正在思考…</div>
              </div>
            </div>
          )}
          {hasPendingChatJob && (pendingStreamStage || pendingToolRuns.length > 0) && (
            <div className="flex">
              <div className="max-w-[var(--chat-assistant-bubble-max-width)] rounded-[16px] border border-[color:color-mix(in_oklab,var(--color-accent)_14%,white)] bg-[color:color-mix(in_oklab,var(--color-panel)_92%,white)] px-3 py-2.5 grid gap-2">
                <div className="flex items-start justify-between gap-3">
                  <div className="grid gap-[2px]">
                    <div className="text-[11px] text-muted">执行过程 · {pendingStreamStage || '处理中'}</div>
                    <div className="text-[11px] text-muted">
                      进行中 {runningCount} · 成功 {okCount} · 失败 {failedCount}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      className="text-[11px] px-2 py-[2px] rounded border border-[color:color-mix(in_oklab,var(--color-border-strong)_70%,white)] bg-white text-[color:color-mix(in_oklab,var(--color-ink)_76%,white)]"
                      disabled={failedCount === 0 && !showOnlyFailed}
                      onClick={() => setShowOnlyFailed((prev) => !prev)}
                    >
                      {showOnlyFailed ? '显示全部' : '仅失败'}
                    </button>
                    <button
                      type="button"
                      className="text-[11px] px-2 py-[2px] rounded border border-[color:color-mix(in_oklab,var(--color-border-strong)_70%,white)] bg-white text-[color:color-mix(in_oklab,var(--color-ink)_76%,white)]"
                      onClick={() => setProcessCollapsed((prev) => !prev)}
                    >
                      {processCollapsed ? '展开' : '收起'}
                    </button>
                  </div>
                </div>
                {!processCollapsed && (
                  <div className="grid gap-1">
                    {visibleToolRuns.length === 0 ? (
                      <div className="text-[12px] text-muted">当前没有失败工具。</div>
                    ) : (
                      visibleToolRuns.map((item) => {
                        const lineClass =
                          item.status === 'running'
                            ? 'bg-warning-soft border-[color:color-mix(in_oklab,var(--color-warning)_24%,white)] text-warning'
                            : item.status === 'ok'
                              ? 'bg-success-soft border-[color:color-mix(in_oklab,var(--color-success)_22%,white)] text-success'
                              : 'bg-danger-soft border-[color:color-mix(in_oklab,var(--color-danger)_18%,white)] text-danger'
                        return (
                          <div key={item.key} className={`text-[12px] leading-[1.32] max-[900px]:leading-[1.26] border rounded px-2 py-[6px] ${lineClass}`}>
                            <div className="font-medium">{item.name}</div>
                            <div>
                              {item.status === 'running' ? '进行中' : ''}
                              {item.status === 'ok' ? `成功${item.durationMs ? `（${item.durationMs}ms）` : ''}` : ''}
                              {item.status === 'failed' ? `失败${item.error ? `：${item.error}` : ''}` : ''}
                            </div>
                          </div>
                        )
                      })
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
      {showScrollToBottom && (
        <button
          type="button"
          className="self-center rounded-lg border border-border-strong bg-white px-3 py-[6px] text-[12px] text-ink cursor-pointer shadow-sm"
          onClick={onScrollToBottom}
        >
          回到底部
        </button>
      )}
    </>
  )
}
