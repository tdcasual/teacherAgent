import type { FormEvent, KeyboardEvent, RefObject } from 'react'
import type { RenderedMessage, VerifiedStudent } from '../../appTypes'
import type { ComposerAttachment } from '../../../../shared/useChatAttachments'
import ChatMessages from './ChatMessages'
import ChatComposer from './ChatComposer'

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
  attachments: ComposerAttachment[]
  uploadingAttachments: boolean
  hasSendableAttachments: boolean
  onPickFiles: (files: File[]) => void | Promise<void>
  onRemoveAttachment: (localId: string) => void | Promise<void>
}

export default function ChatPanel(props: Props) {
  return (
    <main className="chat-shell flex-1 min-w-0 min-h-0 h-full flex flex-col overflow-hidden bg-surface relative" data-testid="student-chat-panel">
      <ChatMessages
        renderedMessages={props.renderedMessages}
        messagesRef={props.messagesRef}
        endRef={props.endRef}
        isNearBottom={props.isNearBottom}
        scrollToBottom={props.scrollToBottom}
      />
      <ChatComposer
        verifiedStudent={props.verifiedStudent}
        pendingChatJobId={props.pendingChatJobId}
        sending={props.sending}
        inputRef={props.inputRef}
        input={props.input}
        setInput={props.setInput}
        handleInputKeyDown={props.handleInputKeyDown}
        handleSend={props.handleSend}
        composerHint={props.composerHint}
        attachments={props.attachments}
        uploadingAttachments={props.uploadingAttachments}
        hasSendableAttachments={props.hasSendableAttachments}
        onPickFiles={props.onPickFiles}
        onRemoveAttachment={props.onRemoveAttachment}
      />
    </main>
  )
}
