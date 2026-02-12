import type { FormEvent, KeyboardEvent, RefObject } from 'react'
import type { RenderedMessage, VerifiedStudent } from '../../appTypes'

type Props = {
  renderedMessages: RenderedMessage[]
  sending: boolean
  pendingChatJobId: string
  verifiedStudent: VerifiedStudent | null
  messagesRef: RefObject<HTMLDivElement | null>
  endRef: RefObject<HTMLDivElement | null>
  isNearBottom: boolean
  scrollToBottom: () => void
  inputRef: RefObject<HTMLTextAreaElement | null>
  input: string
  setInput: (value: string) => void
  handleInputKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void
  handleSend: (event: FormEvent) => void
  composerHint: string
}

export default function StudentChatPanel(props: Props) {
  const {
    renderedMessages,
    sending,
    pendingChatJobId,
    verifiedStudent,
    messagesRef,
    endRef,
    isNearBottom,
    scrollToBottom,
    inputRef,
    input,
    setInput,
    handleInputKeyDown,
    handleSend,
    composerHint,
  } = props

  const composerDisabled = !verifiedStudent || Boolean(pendingChatJobId)

  return (
    <main className="chat-shell min-h-0 flex flex-col overflow-hidden bg-surface relative" data-testid="student-chat-panel">
      <div className="messages flex-1 min-h-0 overflow-auto pt-[18px] pb-2 bg-surface max-[900px]:pt-3.5 max-[900px]:pb-1.5 max-[900px]:[-webkit-overflow-scrolling:touch] max-[900px]:[overscroll-behavior:contain]" ref={messagesRef}>
        <div className="max-w-[860px] mx-auto px-5 pb-3.5 grid gap-3.5 max-[900px]:px-3.5 max-[900px]:pb-3 max-[900px]:gap-3">
          {renderedMessages.map((msg) => (
            <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={
                  msg.role === 'user'
                    ? 'max-w-[min(760px,90%)] rounded-[18px] px-3.5 py-2.5 border border-[#e1e6eb] bg-[#eef1f4] shadow-sm max-[900px]:max-w-[min(100%,92vw)]'
                    : 'max-w-[760px] bg-transparent p-[2px_0]'
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

      <form className={`composer shrink-0 border-t border-border px-5 pt-3.5 pb-[calc(18px+env(safe-area-inset-bottom))] bg-[linear-gradient(180deg,rgba(255,255,255,0)_0%,rgba(255,255,255,0.95)_32%,#fff_60%)] max-[900px]:px-3 max-[900px]:pt-2.5 max-[900px]:pb-[calc(14px+env(safe-area-inset-bottom))] ${composerDisabled ? 'opacity-[0.78]' : ''}`} onSubmit={handleSend}>
        <div className="max-w-[860px] mx-auto border border-border rounded-[20px] bg-white shadow-sm px-3 py-2.5 max-[900px]:max-w-full">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleInputKeyDown}
            placeholder={verifiedStudent ? '输入问题，例如：牛顿第三定律是什么' : '请先填写姓名完成验证'}
            rows={1}
            disabled={composerDisabled}
            className="!border-none !bg-transparent !p-[4px_2px] !shadow-none resize-none min-h-[56px] max-h-[220px] leading-[1.45] focus:!border-none focus:!shadow-none disabled:cursor-not-allowed"
          />
          <div className="flex items-center justify-between gap-2.5 mt-1">
            <span className="composer-hint text-xs text-muted">{composerHint}</span>
            <button type="submit" className="border-none rounded-full px-4 py-2 text-[13px] cursor-pointer bg-accent text-white transition-opacity duration-150 disabled:opacity-55 disabled:cursor-not-allowed" disabled={sending || composerDisabled}>
              发送
            </button>
          </div>
        </div>
      </form>
    </main>
  )
}
