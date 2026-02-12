import type { FormEvent, KeyboardEvent, RefObject } from 'react'
import { nowTime } from '../../../../shared/time'
import type { RenderedMessage, VerifiedStudent } from '../../appTypes'

type Props = {
  renderedMessages: RenderedMessage[]
  sending: boolean
  pendingChatJobId: string
  verifiedStudent: VerifiedStudent | null
  endRef: RefObject<HTMLDivElement | null>
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
    endRef,
    inputRef,
    input,
    setInput,
    handleInputKeyDown,
    handleSend,
    composerHint,
  } = props

  const composerDisabled = !verifiedStudent || Boolean(pendingChatJobId)

  return (
    <main className="chat-shell" data-testid="student-chat-panel">
      <div className="messages">
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
          {sending && !pendingChatJobId && (
            <div className="message assistant">
              <div className="bubble typing">
                <div className="meta">助手 · {nowTime()}</div>
                <div className="text">正在思考…</div>
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>
      </div>

      <form className={`composer ${composerDisabled ? 'disabled' : ''}`} onSubmit={handleSend}>
        <div className="composer-inner">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleInputKeyDown}
            placeholder={verifiedStudent ? '输入问题，例如：牛顿第三定律是什么' : '请先填写姓名完成验证'}
            rows={1}
            disabled={composerDisabled}
          />
          <div className="composer-actions">
            <span className="composer-hint">{composerHint}</span>
            <button type="submit" className="send-btn" disabled={sending || composerDisabled}>
              发送
            </button>
          </div>
        </div>
      </form>
    </main>
  )
}
