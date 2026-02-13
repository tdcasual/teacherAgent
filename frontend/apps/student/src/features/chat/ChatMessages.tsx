import type { RefObject } from 'react'
import type { RenderedMessage } from '../../appTypes'

type Props = {
  renderedMessages: RenderedMessage[]
  messagesRef: RefObject<HTMLDivElement | null>
  endRef: RefObject<HTMLDivElement | null>
  isNearBottom: boolean
  scrollToBottom: () => void
}

export default function ChatMessages({ renderedMessages, messagesRef, endRef, isNearBottom, scrollToBottom }: Props) {
  return (
    <>
      <div className="messages flex-1 min-h-0 overflow-x-hidden overflow-y-auto pt-[18px] pb-2 bg-surface [scrollbar-gutter:stable_both-edges] max-[900px]:pt-3.5 max-[900px]:pb-1.5 max-[900px]:[-webkit-overflow-scrolling:touch] max-[900px]:[overscroll-behavior:contain]" ref={messagesRef}>
        <div className="max-w-[860px] mx-auto px-5 pb-3.5 grid gap-3.5 max-[900px]:px-3.5 max-[900px]:pb-3 max-[900px]:gap-3">
          {renderedMessages.map((msg) => (
            <div key={msg.id} className={`message ${msg.role} flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={
                  msg.role === 'user'
                    ? 'bubble max-w-[min(760px,90%)] rounded-[18px] px-3.5 py-2.5 border border-[#e1e6eb] bg-[#eef1f4] shadow-sm max-[900px]:max-w-[min(100%,92vw)]'
                    : 'bubble max-w-[760px] bg-transparent p-[2px_0]'
                }
              >
                <div className="text-[11px] text-muted mb-1.5">
                  {msg.role === 'user' ? '我' : '助手'} · {msg.time}
                </div>
                <div className="text markdown leading-[1.6] [overflow-wrap:anywhere]" dangerouslySetInnerHTML={{ __html: msg.html }} />
              </div>
            </div>
          ))}
          <div ref={endRef} />
        </div>
      </div>
      {!isNearBottom && (
        <button
          type="button"
          className="absolute bottom-20 left-1/2 -translate-x-1/2 bg-accent text-white border-none rounded-2xl px-4 py-1.5 text-[13px] cursor-pointer shadow-sm z-5 animate-[fadeInUp_0.2s_ease] hover:opacity-90"
          onClick={scrollToBottom}
          aria-label="滚动到最新消息"
        >
          ↓ 新消息
        </button>
      )}
    </>
  )
}
