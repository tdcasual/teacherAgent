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
        className="messages flex-1 min-h-0 overflow-auto bg-surface pt-[10px] pb-[6px]"
        style={{ overscrollBehavior: 'contain' }}
        ref={messagesRef}
        onScroll={onMessagesScroll}
      >
        <div className="w-full max-w-[var(--chat-content-max-width)] px-5 pb-[14px] grid gap-[14px]">
          {renderedMessages.map((msg) => (
            <div key={msg.id} className={`message ${msg.role} flex ${msg.role === 'user' ? 'justify-end' : ''}`}>
              <div
                className={
                  msg.role === 'assistant'
                    ? 'max-w-[var(--chat-assistant-bubble-max-width)] py-[2px] px-0'
                    : 'max-w-[var(--chat-bubble-max-width)] px-[14px] py-[10px] rounded-[12px] bg-[#eef1f4] border border-[#e1e6eb] shadow-sm'
                }
              >
                <div className="text-[11px] text-muted mb-1">
                  {msg.role === 'user' ? '我' : '助手'} · {msg.time}
                </div>
                <div className="text leading-[1.42] whitespace-normal break-words markdown" dangerouslySetInnerHTML={{ __html: msg.html }} />
              </div>
            </div>
          ))}
          {sending && !hasPendingChatJob && (
            <div className="flex">
              <div className="max-w-[var(--chat-assistant-bubble-max-width)] bg-[#f4f7fb] border border-dashed border-[#cfd8e3] rounded-[14px] py-2 px-3">
                <div className="text-[11px] text-muted mb-1">助手 · {typingTimeLabel}</div>
                <div className="leading-[1.42] whitespace-normal break-words">正在思考…</div>
              </div>
            </div>
          )}
          {hasPendingChatJob && (pendingStreamStage || pendingToolRuns.length > 0) && (
            <div className="flex">
              <div className="max-w-[var(--chat-assistant-bubble-max-width)] bg-[#f8fafc] border border-[#d7e3ef] rounded-[12px] px-3 py-2 grid gap-2">
                <div className="flex items-start justify-between gap-3">
                  <div className="grid gap-[2px]">
                    <div className="text-[11px] text-muted">执行过程 · {pendingStreamStage || '处理中'}</div>
                    <div className="text-[11px] text-[#64748b]">
                      进行中 {runningCount} · 成功 {okCount} · 失败 {failedCount}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      className="text-[11px] px-2 py-[2px] rounded border border-[#c9d7e5] bg-white text-[#475569]"
                      disabled={failedCount === 0 && !showOnlyFailed}
                      onClick={() => setShowOnlyFailed((prev) => !prev)}
                    >
                      {showOnlyFailed ? '显示全部' : '仅失败'}
                    </button>
                    <button
                      type="button"
                      className="text-[11px] px-2 py-[2px] rounded border border-[#c9d7e5] bg-white text-[#475569]"
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
                            ? 'bg-[#fff7e6] border-[#fcd9a5] text-[#92400e]'
                            : item.status === 'ok'
                              ? 'bg-[#ecfdf5] border-[#bbf7d0] text-[#065f46]'
                              : 'bg-[#fef2f2] border-[#fecaca] text-[#991b1b]'
                        return (
                          <div key={item.key} className={`text-[12px] leading-[1.35] border rounded px-2 py-[6px] ${lineClass}`}>
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
          className="self-center border border-border-strong bg-white text-[#334155] rounded-lg px-3 py-[6px] text-[12px] cursor-pointer shadow-sm"
          onClick={onScrollToBottom}
        >
          回到底部
        </button>
      )}
    </>
  )
}
