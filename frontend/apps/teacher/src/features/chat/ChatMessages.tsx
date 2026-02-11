import type { MutableRefObject } from 'react'

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
}: Props) {
  return (
    <>
      <div
        className="flex-1 min-h-0 overflow-auto bg-surface pt-[10px] pb-[6px]"
        style={{ overscrollBehavior: 'contain' }}
        ref={messagesRef}
        onScroll={onMessagesScroll}
      >
        <div className="w-full max-w-[var(--chat-content-max-width)] px-5 pb-[14px] grid gap-[14px]">
          {renderedMessages.map((msg) => (
            <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : ''}`}>
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
                <div className="leading-[1.42] whitespace-normal break-words markdown" dangerouslySetInnerHTML={{ __html: msg.html }} />
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
