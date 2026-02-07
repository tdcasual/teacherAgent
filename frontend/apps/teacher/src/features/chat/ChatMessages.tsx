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
      <div className="messages" ref={messagesRef} onScroll={onMessagesScroll}>
        <div className="messages-inner">
          {renderedMessages.map((msg) => (
            <div key={msg.id} className={`message ${msg.role}`}>
              <div className="bubble">
                <div className="meta">
                  {msg.role === 'user' ? '我' : '助手'} · {msg.time}
                </div>
                <div className="text markdown" dangerouslySetInnerHTML={{ __html: msg.html }} />
              </div>
            </div>
          ))}
          {sending && !hasPendingChatJob && (
            <div className="message assistant">
              <div className="bubble typing">
                <div className="meta">助手 · {typingTimeLabel}</div>
                <div className="text">正在思考…</div>
              </div>
            </div>
          )}
        </div>
      </div>
      {showScrollToBottom && (
        <button type="button" className="scroll-to-bottom" onClick={onScrollToBottom}>
          回到底部
        </button>
      )}
    </>
  )
}
