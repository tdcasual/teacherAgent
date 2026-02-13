import { useRef, type FormEvent, type KeyboardEvent, type MutableRefObject } from 'react'
import type { ComposerAttachment } from '../../../../shared/useChatAttachments'

type Props = {
  activeSkillId: string
  skillPinned: boolean
  input: string
  pendingChatJob: boolean
  sending: boolean
  chatQueueHint: string
  composerWarning: string
  attachments: ComposerAttachment[]
  uploadingAttachments: boolean
  hasSendableAttachments: boolean
  inputRef: MutableRefObject<HTMLTextAreaElement | null>
  onSubmit: (event: FormEvent) => void
  onInputChange: (value: string, selectionStart: number) => void
  onInputClick: (selectionStart: number) => void
  onInputKeyUp: (selectionStart: number) => void
  onInputKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void
  onPickFiles: (files: File[]) => void | Promise<void>
  onRemoveAttachment: (localId: string) => void | Promise<void>
}

export default function ChatComposer({
  activeSkillId,
  skillPinned,
  input,
  pendingChatJob,
  sending,
  chatQueueHint,
  composerWarning,
  attachments,
  uploadingAttachments,
  hasSendableAttachments,
  inputRef,
  onSubmit,
  onInputChange,
  onInputClick,
  onInputKeyUp,
  onInputKeyDown,
  onPickFiles,
  onRemoveAttachment,
}: Props) {
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const canSend = Boolean(input.trim()) || hasSendableAttachments

  return (
    <form className="relative z-[2] px-4 pt-[10px] pb-[14px] border-t border-border bg-gradient-to-t from-surface from-70% to-transparent" onSubmit={onSubmit}>
      <div className="w-full max-w-[var(--chat-content-max-width)] border border-border bg-white rounded-[12px] px-3 py-[10px] shadow-sm grid gap-[10px]">
        <div className="flex flex-wrap gap-2">
          <span className="inline-flex items-center border border-border rounded-lg px-2 py-[2px] text-[11px] text-[#4b5563] bg-[#f8fafc]">
            {skillPinned ? `技能: $${activeSkillId || 'physics-teacher-ops'}` : '技能: 自动路由'}
          </span>
        </div>
        {attachments.length ? (
          <div className="flex flex-wrap gap-2">
            {attachments.map((item) => (
              <span key={item.localId} className="inline-flex items-center gap-2 border border-border rounded-lg px-2 py-1 text-[12px] bg-[#f8fafc] max-w-full">
                <span className="max-w-[220px] truncate" title={item.fileName}>{item.fileName}</span>
                <span className={`text-[11px] ${item.status === 'ready' ? 'text-[#0f766e]' : item.status === 'uploading' ? 'text-[#6b7280]' : 'text-danger'}`}>
                  {item.status === 'ready' ? '已就绪' : item.status === 'uploading' ? '上传中' : '失败'}
                </span>
                <button
                  type="button"
                  className="border-0 bg-transparent text-muted cursor-pointer px-0"
                  onClick={() => { void onRemoveAttachment(item.localId) }}
                  title={item.error || '移除附件'}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        ) : null}
        <textarea
          ref={inputRef}
          className="border-none bg-transparent px-[2px] py-0 shadow-none resize-none min-h-[56px] max-h-[220px] overflow-auto focus:border-none focus:shadow-none focus:outline-none focus:ring-0"
          value={input}
          onChange={(e) => onInputChange(e.target.value, e.target.selectionStart || e.target.value.length)}
          onClick={(e) => onInputClick((e.target as HTMLTextAreaElement).selectionStart || input.length)}
          onKeyUp={(e) => onInputKeyUp((e.target as HTMLTextAreaElement).selectionStart || input.length)}
          onKeyDown={onInputKeyDown}
          placeholder="输入指令或问题，使用 $ 查看技能。回车发送，上档键+回车换行"
          rows={3}
          disabled={pendingChatJob}
        />
        <div className="flex justify-between items-center gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <button
              type="button"
              className="border border-border rounded-[10px] px-2.5 py-1.5 text-[13px] bg-[#f8fafc] cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
              disabled={pendingChatJob}
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
              onChange={(e) => {
                const files = Array.from(e.target.files || [])
                if (files.length) void onPickFiles(files)
                e.currentTarget.value = ''
              }}
            />
            <span className="composer-hint text-[12px] text-muted truncate">{chatQueueHint || '$ 技能 | 回车发送'}</span>
          </div>
          <button
            type="submit"
            className="border-none rounded-[12px] px-4 py-[10px] text-[14px] cursor-pointer bg-accent text-white disabled:opacity-60 disabled:cursor-not-allowed"
            disabled={sending || pendingChatJob || !canSend || uploadingAttachments}
          >
            发送
          </button>
        </div>
        {composerWarning ? <div className="status err">{composerWarning}</div> : null}
      </div>
    </form>
  )
}
