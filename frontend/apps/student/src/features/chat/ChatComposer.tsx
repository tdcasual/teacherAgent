import { useRef, type FormEvent, type KeyboardEvent, type RefObject } from 'react'
import type { VerifiedStudent } from '../../appTypes'
import type { ComposerAttachment } from '../../../../shared/useChatAttachments'

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
  attachments: ComposerAttachment[]
  uploadingAttachments: boolean
  hasSendableAttachments: boolean
  onPickFiles: (files: File[]) => void | Promise<void>
  onRemoveAttachment: (localId: string) => void | Promise<void>
}

export default function ChatComposer({
  verifiedStudent,
  pendingChatJobId,
  sending,
  inputRef,
  input,
  setInput,
  handleInputKeyDown,
  handleSend,
  composerHint,
  attachments,
  uploadingAttachments,
  hasSendableAttachments,
  onPickFiles,
  onRemoveAttachment,
}: Props) {
  const composerDisabled = !verifiedStudent || Boolean(pendingChatJobId)
  const composerBusy = sending || Boolean(pendingChatJobId)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const canSend = Boolean(input.trim()) || hasSendableAttachments

  return (
    <form
      className={`composer flex-none border-t border-border px-5 pt-3.5 pb-[calc(18px+env(safe-area-inset-bottom))] bg-white max-[900px]:px-3 max-[900px]:pt-2.5 max-[900px]:pb-[calc(14px+env(safe-area-inset-bottom))] ${composerDisabled ? 'opacity-[0.78]' : ''}`}
      aria-busy={composerBusy}
      onSubmit={handleSend}
    >
      <div className="max-w-[860px] mx-auto border border-border rounded-[20px] bg-white shadow-sm px-3 py-2.5 max-[900px]:max-w-full">
        {attachments.length ? (
          <div className="flex flex-wrap gap-2 mb-1.5">
            {attachments.map((item) => (
              <span key={item.localId} className="inline-flex items-center gap-2 border border-border rounded-lg px-2 py-1 text-[11px] bg-[#f8fafc] max-w-full">
                <span className="max-w-[180px] truncate" title={item.fileName}>{item.fileName}</span>
                <span className={`${item.status === 'ready' ? 'text-[#0f766e]' : item.status === 'uploading' ? 'text-[#6b7280]' : 'text-danger'}`}>
                  {item.status === 'ready' ? '已就绪' : item.status === 'uploading' ? '上传中' : '失败'}
                </span>
                <button type="button" className="border-0 bg-transparent text-muted cursor-pointer px-0" onClick={() => { void onRemoveAttachment(item.localId) }} title={item.error || '移除附件'}>×</button>
              </span>
            ))}
          </div>
        ) : null}
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
          <div className="flex items-center gap-2 min-w-0">
            <button
              type="button"
              className="border border-border rounded-full px-2.5 py-1 text-[13px] cursor-pointer bg-[#f8fafc] disabled:opacity-60 disabled:cursor-not-allowed"
              disabled={composerDisabled}
              onClick={() => fileInputRef.current?.click()}
            >
              +
            </button>
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              multiple
              accept=".md,.markdown,.xls,.xlsx,application/pdf,image/*"
              onChange={(event) => {
                const files = Array.from(event.target.files || [])
                if (files.length) void onPickFiles(files)
                event.currentTarget.value = ''
              }}
            />
            <span className="composer-hint text-xs text-muted truncate" role="status" aria-live="polite">{composerHint}</span>
          </div>
          <button type="submit" className="border-none rounded-full px-4 py-2 text-[13px] cursor-pointer bg-accent text-white transition-opacity duration-150 disabled:opacity-55 disabled:cursor-not-allowed" disabled={sending || composerDisabled || !canSend || uploadingAttachments}>
            发送
          </button>
        </div>
      </div>
    </form>
  )
}
