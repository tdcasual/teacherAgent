import type { FormEvent, KeyboardEvent, RefObject } from 'react'
import type { VerifiedStudent } from '../../appTypes'

type Props = {
  verifiedStudent: VerifiedStudent | null
  pendingChatJobId: string
  sending: boolean
  inputRef: RefObject<HTMLTextAreaElement | null>
  input: string
  setInput: (value: string) => void
  handleInputKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void
  handleSend: (event: FormEvent) => void
  composerHint: string
}

export default function ChatComposer({ verifiedStudent, pendingChatJobId, sending, inputRef, input, setInput, handleInputKeyDown, handleSend, composerHint }: Props) {
  const composerDisabled = !verifiedStudent || Boolean(pendingChatJobId)

  return (
    <form className={`composer flex-none border-t border-border px-5 pt-3.5 pb-[calc(18px+env(safe-area-inset-bottom))] bg-white max-[900px]:px-3 max-[900px]:pt-2.5 max-[900px]:pb-[calc(14px+env(safe-area-inset-bottom))] ${composerDisabled ? 'opacity-[0.78]' : ''}`} onSubmit={handleSend}>
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
  )
}
