import { useEffect, useRef, type FormEvent, type KeyboardEvent, type MutableRefObject } from 'react'
import RoutingPage from '../routing/RoutingPage'
import ChatComposer from './ChatComposer'
import ChatMessages from './ChatMessages'
import MentionPanel from './MentionPanel'
import type { MentionOption, PendingToolRun } from '../../appTypes'
import type { InvocationTriggerType } from './invocation'
import type { ComposerAttachment } from '../../../../shared/useChatAttachments'

type MentionState = {
  start: number
  query: string
  type: InvocationTriggerType
  items: MentionOption[]
} | null

type RenderedMessage = {
  id: string
  role: 'user' | 'assistant'
  html: string
  time: string
}

type TeacherChatMainContentProps = {
  inlineRoutingOpen: boolean
  apiBase: string
  onApiBaseChange: (value: string) => void
  onDirtyChange: (dirty: boolean) => void
  renderedMessages: RenderedMessage[]
  sending: boolean
  hasPendingChatJob: boolean
  typingTimeLabel: string
  messagesRef: MutableRefObject<HTMLDivElement | null>
  onMessagesScroll: () => void
  showScrollToBottom: boolean
  onScrollToBottom: () => void
  activeSkillId: string
  skillPinned: boolean
  input: string
  chatQueueHint: string
  pendingStreamStage: string
  pendingToolRuns: PendingToolRun[]
  composerWarning: string
  attachments: ComposerAttachment[]
  uploadingAttachments: boolean
  hasSendableAttachments: boolean
  inputRef: MutableRefObject<HTMLTextAreaElement | null>
  onSubmit: (event: FormEvent) => void | Promise<void>
  onInputChange: (value: string, selectionStart: number) => void
  onInputClick: (selectionStart: number) => void
  onInputKeyUp: (selectionStart: number) => void
  onInputKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void
  onPickFiles: (files: File[]) => void | Promise<void>
  onRemoveAttachment: (localId: string) => void | Promise<void>
  mention: MentionState
  mentionIndex: number
  onInsertMention: (item: MentionOption) => void
}

export default function TeacherChatMainContent({
  inlineRoutingOpen,
  apiBase,
  onApiBaseChange,
  onDirtyChange,
  renderedMessages,
  sending,
  hasPendingChatJob,
  typingTimeLabel,
  messagesRef,
  onMessagesScroll,
  showScrollToBottom,
  onScrollToBottom,
  activeSkillId,
  skillPinned,
  input,
  chatQueueHint,
  pendingStreamStage,
  pendingToolRuns,
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
  mention,
  mentionIndex,
  onInsertMention,
}: TeacherChatMainContentProps) {
  const shellRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (inlineRoutingOpen) return
    const shell = shellRef.current
    if (!shell) return
    if (shell.scrollTop !== 0) shell.scrollTop = 0
  }, [inlineRoutingOpen, renderedMessages.length])

  return (
    <main
      ref={shellRef}
      className={`chat-shell flex-auto w-full min-w-0 min-h-0 flex flex-col gap-[10px] p-4 bg-surface ${inlineRoutingOpen ? 'overflow-y-auto overflow-x-hidden' : 'overflow-hidden'}`}
      style={inlineRoutingOpen ? { overscrollBehavior: 'contain' } : undefined}
    >
      {inlineRoutingOpen ? (
        <RoutingPage
          apiBase={apiBase}
          onApiBaseChange={onApiBaseChange}
          onDirtyChange={onDirtyChange}
          section="general"
          legacyFlat
        />
      ) : (
        <>
          <ChatMessages
            renderedMessages={renderedMessages}
            sending={sending}
            hasPendingChatJob={hasPendingChatJob}
            typingTimeLabel={typingTimeLabel}
            messagesRef={messagesRef}
            onMessagesScroll={onMessagesScroll}
            showScrollToBottom={showScrollToBottom}
            onScrollToBottom={onScrollToBottom}
            pendingStreamStage={pendingStreamStage}
            pendingToolRuns={pendingToolRuns}
          />

          <ChatComposer
            activeSkillId={activeSkillId || 'physics-teacher-ops'}
            skillPinned={skillPinned}
            input={input}
            pendingChatJob={hasPendingChatJob}
            sending={sending}
            chatQueueHint={chatQueueHint}
            composerWarning={composerWarning}
            attachments={attachments}
            uploadingAttachments={uploadingAttachments}
            hasSendableAttachments={hasSendableAttachments}
            inputRef={inputRef}
            onSubmit={onSubmit}
            onInputChange={onInputChange}
            onInputClick={onInputClick}
            onInputKeyUp={onInputKeyUp}
            onInputKeyDown={onInputKeyDown}
            onPickFiles={onPickFiles}
            onRemoveAttachment={onRemoveAttachment}
          />

          <MentionPanel mention={mention} mentionIndex={mentionIndex} onInsert={onInsertMention} />
        </>
      )}
    </main>
  )
}
